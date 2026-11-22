import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, DestroyRef, OnInit, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import {
  Subscription,
  catchError,
  concatMap,
  filter,
  finalize,
  forkJoin,
  from,
  map,
  of,
  switchMap,
  timer,
} from 'rxjs';

import { BuildingLayer } from '../../api/models/building-layer';
import { FileKind } from '../../api/models/file-kind';
import { ProjectFileRead } from '../../api/models/project-file-read';
import { ProjectLayers } from '../../api/models/project-layers';
import { ProjectRead } from '../../api/models/project-read';
import { BuildingsService } from '../../api/services/buildings.service';
import { FilesService } from '../../api/services/files.service';
import { LayersService } from '../../api/services/layers.service';
import { ProjectsService } from '../../api/services/projects.service';
import { apiErrorMessage } from '../../shared/api-error';
import { confirmDialog } from '../../shared/confirm-dialog.component';
import { FileSizePipe } from '../../shared/file-size.pipe';
import {
  ACCEPTED_FILE_TYPES,
  BUILDING_REVIEW_COLOR,
  BUILDING_REVIEW_KEYS,
  BUILDING_REVIEW_LABEL,
  BuildingReviewKey,
  FILE_KIND_LABEL,
  FILE_STATUS_BADGE,
  FILE_STATUS_LABEL,
  PROJECT_STATUS_BADGE,
  PROJECT_STATUS_LABEL,
} from '../../shared/labels';
import { openProjectForm } from './open-project-form';
import { ProjectMapComponent } from './project-map.component';

/** File kinds the backend processes automatically (see backend/app/services). */
const IMPORTABLE_KINDS: readonly FileKind[] = ['kml', 'kmz', 'dxf', 'dwg'];
const POLL_MS = 1500;

interface UploadResult {
  name: string;
  error: string | null;
}

@Component({
  selector: 'app-project-detail',
  imports: [RouterLink, DatePipe, DecimalPipe, FileSizePipe, ProjectMapComponent],
  styles: `.swatch { display: inline-block; width: .9rem; height: .9rem; border-radius: .2rem; }`,
  template: `
    <nav aria-label="breadcrumb">
      <ol class="breadcrumb">
        <li class="breadcrumb-item"><a routerLink="/projects">Projects</a></li>
        <li class="breadcrumb-item active" dir="auto">{{ project()?.name ?? '…' }}</li>
      </ol>
    </nav>

    @if (error()) {
      <div class="alert alert-danger" dir="auto">{{ error() }}</div>
    }

    @if (project(); as p) {
      <div class="d-flex align-items-start mb-4">
        <div class="me-auto">
          <h1 class="h3 mb-1" dir="auto">
            {{ p.name }}
            <span class="badge fs-6 align-middle" [class]="projectBadge[p.status]">{{ projectLabel[p.status] }}</span>
          </h1>
          @if (p.description) {
            <p class="text-muted mb-1" dir="auto">{{ p.description }}</p>
          }
          <div class="small text-muted">Created {{ p.created_at | date: 'medium' }}</div>
        </div>
        <button type="button" class="btn btn-outline-secondary me-2" (click)="edit(p)">Edit</button>
        <button type="button" class="btn btn-outline-danger" (click)="removeProject(p)">Delete</button>
      </div>

      <div class="card mb-4">
        <div class="card-header d-flex align-items-center flex-wrap gap-2">
          <span class="fw-semibold me-auto">Map</span>
          @if (layers()?.boundary; as b) {
            <span class="small text-muted">
              Boundary area <strong>{{ b.area_m2 / 10000 | number: '1.1-1' }} ha</strong> ·
              perimeter <strong>{{ b.perimeter_m / 1000 | number: '1.2-2' }} km</strong>
            </span>
          }
          @if (layers()?.features?.length) {
            <span class="small text-muted">· {{ layers()?.features?.length }} imported features</span>
          }
        </div>
        <app-project-map [layers]="layers()" [buildings]="buildings()" [visible]="visible()" />
        @if (buildings(); as bl) {
          @if (bl.summary.total || bl.summary.orphan_ids) {
            <div class="card-footer small d-flex flex-wrap align-items-center gap-3">
              <span class="fw-semibold">Buildings {{ bl.summary.total }}</span>
              @for (key of reviewKeys; track key) {
                <label class="form-check-label d-flex align-items-center gap-1">
                  <input type="checkbox" class="form-check-input mt-0" [checked]="visible().has(key)"
                         (change)="toggle(key)" />
                  <span class="swatch" [style.background]="reviewColor[key]"></span>
                  {{ reviewLabel[key] }} <strong>{{ reviewCount(bl, key) }}</strong>
                </label>
              }
              @if (bl.summary.inside !== null) {
                <span class="text-muted">
                  · inside boundary {{ bl.summary.inside }}, crossing {{ bl.summary.crossing }},
                  outside {{ bl.summary.outside }} (dashed)
                </span>
              }
              @if (bl.provisional) {
                <span class="badge text-bg-warning ms-auto" title="CAD reading rules (backend/app/rules/cad_layers.yaml) are status TBC">
                  Provisional rules
                </span>
              }
            </div>
          }
        }
      </div>

      <div class="card">
        <div class="card-header d-flex align-items-center">
          <span class="fw-semibold me-auto">Project files</span>
          <label class="btn btn-sm btn-primary mb-0" [class.disabled]="uploading()">
            @if (uploading()) {
              <span class="spinner-border spinner-border-sm me-1"></span> Uploading…
            } @else {
              Upload files
            }
            <input type="file" class="d-none" multiple [accept]="accept" [disabled]="uploading()"
                   (change)="onFilesSelected($event)" />
          </label>
        </div>

        @for (r of uploadErrors(); track $index) {
          <div class="alert alert-warning rounded-0 border-0 border-bottom mb-0 py-2 small" dir="auto">
            <strong>{{ r.name }}</strong>: {{ r.error }}
          </div>
        }

        @if (files().length === 0) {
          <div class="card-body text-muted text-center py-4">
            No files yet. Accepted: KML, KMZ, DXF, DWG, survey Excel (.xlsx), PDF.
          </div>
        } @else {
          <table class="table align-middle mb-0">
            <thead class="table-light">
              <tr>
                <th>File</th>
                <th>Type</th>
                <th class="text-end">Size</th>
                <th>Status</th>
                <th>Uploaded</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              @for (f of files(); track f.id) {
                <tr>
                  <td dir="auto" [title]="'SHA-256 ' + f.sha256">{{ f.original_filename }}</td>
                  <td>{{ kindLabel[f.kind] }}</td>
                  <td class="text-end text-nowrap">{{ f.size_bytes | fileSize }}</td>
                  <td>
                    <span class="badge" [class]="fileBadge[f.status]">{{ fileLabel[f.status] }}</span>
                    @if (f.error) {
                      <div class="small text-danger" dir="auto">{{ f.error }}</div>
                    }
                    @if (f.note) {
                      <div class="small text-muted" dir="auto">{{ f.note }}</div>
                    }
                  </td>
                  <td class="text-nowrap">{{ f.uploaded_at | date: 'short' }}</td>
                  <td class="text-end text-nowrap">
                    @if (isImportable(f) && f.status !== 'processing') {
                      <button type="button" class="btn btn-sm btn-outline-secondary me-1" (click)="reprocess(f)">
                        Re-process
                      </button>
                    }
                    <button type="button" class="btn btn-sm btn-outline-danger" (click)="removeFile(f)">Delete</button>
                  </td>
                </tr>
              }
            </tbody>
          </table>
        }
      </div>
    } @else if (!error()) {
      <div class="text-center py-5"><span class="spinner-border"></span></div>
    }
  `,
})
export class ProjectDetailComponent implements OnInit {
  private readonly projectsApi = inject(ProjectsService);
  private readonly filesApi = inject(FilesService);
  private readonly layersApi = inject(LayersService);
  private readonly buildingsApi = inject(BuildingsService);
  private readonly modals = inject(NgbModal);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private pollSub?: Subscription;

  /** Bound from the `:id` route param. */
  readonly id = input.required<string>();

  readonly project = signal<ProjectRead | null>(null);
  readonly files = signal<ProjectFileRead[]>([]);
  readonly layers = signal<ProjectLayers | null>(null);
  readonly buildings = signal<BuildingLayer | null>(null);
  readonly visible = signal<ReadonlySet<BuildingReviewKey>>(new Set(BUILDING_REVIEW_KEYS));
  readonly error = signal<string | null>(null);
  readonly uploading = signal(false);
  readonly uploadErrors = signal<UploadResult[]>([]);

  readonly accept = ACCEPTED_FILE_TYPES;
  readonly projectLabel = PROJECT_STATUS_LABEL;
  readonly projectBadge = PROJECT_STATUS_BADGE;
  readonly kindLabel = FILE_KIND_LABEL;
  readonly fileLabel = FILE_STATUS_LABEL;
  readonly fileBadge = FILE_STATUS_BADGE;
  readonly reviewKeys = BUILDING_REVIEW_KEYS;
  readonly reviewLabel = BUILDING_REVIEW_LABEL;
  readonly reviewColor = BUILDING_REVIEW_COLOR;

  ngOnInit(): void {
    this.load();
  }

  reviewCount(layer: BuildingLayer, key: BuildingReviewKey): number {
    return key === 'orphan' ? layer.summary.orphan_ids : layer.summary[key];
  }

  toggle(key: BuildingReviewKey): void {
    this.visible.update((current) => {
      const next = new Set(current);
      if (!next.delete(key)) {
        next.add(key);
      }
      return next;
    });
  }

  isImportable(f: ProjectFileRead): boolean {
    return IMPORTABLE_KINDS.includes(f.kind);
  }

  load(): void {
    this.pollSub?.unsubscribe();
    const project_id = this.id();
    forkJoin({
      project: this.projectsApi.getProject({ project_id }),
      files: this.filesApi.listFiles({ project_id }),
      layers: this.layersApi.getLayers({ project_id }),
      buildings: this.buildingsApi.getBuildings({ project_id }),
    }).subscribe({
      next: ({ project, files, layers, buildings }) => {
        this.project.set(project);
        this.files.set(files);
        this.layers.set(layers);
        this.buildings.set(buildings);
        this.error.set(null);
        // Processing runs in the background on the server: refresh until it finishes.
        if (files.some((f) => f.status === 'processing')) {
          this.pollSub = timer(POLL_MS)
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe(() => this.load());
        }
      },
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  reprocess(file: ProjectFileRead): void {
    this.filesApi.processFile({ project_id: this.id(), file_id: file.id }).subscribe({
      next: () => this.load(),
      error: (err: unknown) => this.error.set(apiErrorMessage(err)),
    });
  }

  onFilesSelected(event: Event): void {
    const inputEl = event.target as HTMLInputElement;
    const selected = Array.from(inputEl.files ?? []);
    inputEl.value = ''; // allow re-selecting the same file
    if (selected.length === 0) {
      return;
    }
    const project_id = this.id();
    this.uploading.set(true);
    this.uploadErrors.set([]);

    // One request at a time: large CAD files, and a clear per-file error.
    from(selected)
      .pipe(
        concatMap((file) =>
          this.filesApi.uploadFile({ project_id, body: { file } }).pipe(
            map((): UploadResult => ({ name: file.name, error: null })),
            catchError((err: unknown) => of<UploadResult>({ name: file.name, error: apiErrorMessage(err) })),
          ),
        ),
        finalize(() => {
          this.uploading.set(false);
          this.load();
        }),
      )
      .subscribe((r) => {
        if (r.error) {
          this.uploadErrors.update((list) => [...list, r]);
        }
      });
  }

  removeFile(file: ProjectFileRead): void {
    confirmDialog(this.modals, { title: 'Delete file', message: `Delete "${file.original_filename}"?` })
      .pipe(
        filter(Boolean),
        switchMap(() => this.filesApi.deleteFile({ project_id: this.id(), file_id: file.id })),
      )
      .subscribe({
        next: () => this.load(),
        error: (err: unknown) => this.error.set(apiErrorMessage(err)),
      });
  }

  edit(project: ProjectRead): void {
    openProjectForm(this.modals, project).subscribe((saved) => this.project.set(saved));
  }

  removeProject(project: ProjectRead): void {
    confirmDialog(this.modals, {
      title: 'Delete project',
      message: `Delete "${project.name}" and all its files? This cannot be undone.`,
    })
      .pipe(
        filter(Boolean),
        switchMap(() => this.projectsApi.deleteProject({ project_id: project.id })),
      )
      .subscribe({
        next: () => this.router.navigate(['/projects']),
        error: (err: unknown) => this.error.set(apiErrorMessage(err)),
      });
  }
}
