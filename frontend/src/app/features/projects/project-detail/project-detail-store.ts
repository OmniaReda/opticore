import { DestroyRef, Injectable, computed, effect, inject, signal } from '@angular/core';
import { rxResource, takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Observable, catchError, concatMap, finalize, forkJoin, from, map, of } from 'rxjs';

import { FileKind } from '../../../api/models/file-kind';
import { ProjectFileRead } from '../../../api/models/project-file-read';
import { ProjectRead } from '../../../api/models/project-read';
import { SurveyRecordRead } from '../../../api/models/survey-record-read';
import { AddressesService } from '../../../api/services/addresses.service';
import { BuildingsService } from '../../../api/services/buildings.service';
import { FilesService } from '../../../api/services/files.service';
import { LayersService } from '../../../api/services/layers.service';
import { ProjectsService } from '../../../api/services/projects.service';
import { SurveyService } from '../../../api/services/survey.service';
import { ValidationService } from '../../../api/services/validation.service';
import { apiErrorMessage } from '../../../shared/api-error';

/** File kinds the backend processes automatically (see backend/app/services/processing.py). */
export const IMPORTABLE_KINDS: readonly FileKind[] = ['kml', 'kmz', 'dxf', 'dwg', 'survey_xlsx'];

/** How often to refresh while a file is processed in the background. */
export const POLL_MS = 1500;

export interface UploadError {
  name: string;
  error: string;
}

/** State and actions of one project page. Provided by ProjectDetail (one instance per page). */
@Injectable()
export class ProjectDetailStore {
  private readonly projectsApi = inject(ProjectsService);
  private readonly filesApi = inject(FilesService);
  private readonly layersApi = inject(LayersService);
  private readonly buildingsApi = inject(BuildingsService);
  private readonly addressesApi = inject(AddressesService);
  private readonly surveyApi = inject(SurveyService);
  private readonly validationApi = inject(ValidationService);
  private readonly destroyRef = inject(DestroyRef);

  private readonly projectId = signal<string | undefined>(undefined);

  private readonly resource = rxResource({
    params: () => this.projectId(),
    stream: ({ params: project_id }) =>
      forkJoin({
        project: this.projectsApi.getProject({ project_id }),
        files: this.filesApi.listFiles({ project_id }),
        layers: this.layersApi.getLayers({ project_id }),
        buildings: this.buildingsApi.getBuildings({ project_id }),
        survey: this.surveyApi.getSurvey({ project_id }),
        addresses: this.addressesApi.getAddresses({ project_id }),
        validation: this.validationApi.getValidation({ project_id }),
      }),
  });

  /** Last loaded data; kept while reloading so the map does not flicker. */
  private readonly data = computed(() =>
    this.resource.hasValue() ? this.resource.value() : undefined,
  );
  readonly project = computed(() => this.data()?.project);
  readonly files = computed(() => this.data()?.files ?? []);
  readonly layers = computed(() => this.data()?.layers ?? null);
  readonly buildings = computed(() => this.data()?.buildings ?? null);
  readonly survey = computed(() => this.data()?.survey ?? null);
  /** House numbers with Floors / Total Users from the filled Streets & numbers Excel. */
  readonly addresses = computed(() => this.data()?.addresses ?? null);
  readonly validation = computed(() => this.data()?.validation ?? null);
  /** Survey row per Building ID (for the map tooltip). */
  readonly surveyByCode = computed(
    () => new Map<string, SurveyRecordRead>((this.survey()?.records ?? []).map((r) => [r.code, r])),
  );

  private readonly actionError = signal<string | null>(null);
  readonly error = computed(() => {
    const loadError = this.resource.error();
    return loadError ? apiErrorMessage(loadError) : this.actionError();
  });

  readonly uploading = signal(false);
  readonly uploadErrors = signal<UploadError[]>([]);

  constructor() {
    // Files are processed in the background on the server: refresh until none is processing.
    effect((onCleanup) => {
      if (this.files().some((f) => f.status === 'processing')) {
        const timer = setTimeout(() => this.resource.reload(), POLL_MS);
        onCleanup(() => clearTimeout(timer));
      }
    });
  }

  load(projectId: string): void {
    this.projectId.set(projectId);
  }

  reload(): void {
    this.actionError.set(null);
    this.resource.reload();
  }

  /** Uploads one file at a time (large CAD files, and a clear error per file), then reloads. */
  upload(files: readonly File[]): void {
    const project_id = this.projectId();
    if (!project_id || files.length === 0) {
      return;
    }
    this.uploading.set(true);
    this.uploadErrors.set([]);
    from(files)
      .pipe(
        concatMap((file) =>
          this.filesApi.uploadFile({ project_id, body: { file } }).pipe(
            map(() => null),
            catchError((err: unknown) =>
              of<UploadError>({ name: file.name, error: apiErrorMessage(err) }),
            ),
          ),
        ),
        finalize(() => {
          this.uploading.set(false);
          this.reload();
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((failed) => {
        if (failed) {
          this.uploadErrors.update((list) => [...list, failed]);
        }
      });
  }

  reprocess(file: ProjectFileRead): void {
    this.run(this.filesApi.processFile({ project_id: file.project_id, file_id: file.id }));
  }

  deleteFile(file: ProjectFileRead): void {
    this.run(this.filesApi.deleteFile({ project_id: file.project_id, file_id: file.id }));
  }

  /** Emits once the project is deleted (errors are shown on the page). */
  deleteProject(project: ProjectRead): Observable<void> {
    return this.projectsApi.deleteProject({ project_id: project.id }).pipe(
      catchError((err: unknown) => {
        this.actionError.set(apiErrorMessage(err));
        return of();
      }),
    );
  }

  /** Shows a project saved elsewhere (edit dialog) without a round trip. */
  projectSaved(project: ProjectRead): void {
    this.resource.update((d) => d && { ...d, project });
  }

  private run(request$: Observable<unknown>): void {
    request$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => this.reload(),
      error: (err: unknown) => this.actionError.set(apiErrorMessage(err)),
    });
  }
}
