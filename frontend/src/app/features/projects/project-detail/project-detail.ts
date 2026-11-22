import { DecimalPipe } from '@angular/common';
import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { filter, switchMap } from 'rxjs';

import { ApiConfiguration } from '../../../api/api-configuration';
import { GeoJsonGeometry } from '../../../api/models/geo-json-geometry';
import { ProjectFileRead } from '../../../api/models/project-file-read';
import { ProjectRead } from '../../../api/models/project-read';
import { ValidationIssue } from '../../../api/models/validation-issue';
import { ConfirmDialogService } from '../../../shared/confirm-dialog/confirm-dialog-service';
import { BUILDING_REVIEW_KEYS, BuildingReviewKey } from '../../../shared/labels';
import { ProjectFormDialogService } from '../project-form/project-form-dialog-service';
import { BuildingLegend } from './building-legend/building-legend';
import { ProjectDetailStore } from './project-detail-store';
import { ProjectFiles } from './project-files/project-files';
import { ProjectHeader } from './project-header/project-header';
import { ProjectMap } from './project-map/project-map';
import { SurveySummary } from './survey-summary/survey-summary';
import { ValidationReport } from './validation-report/validation-report';

/** Project page: header, map with buildings, uploaded files. State lives in ProjectDetailStore. */
@Component({
  selector: 'app-project-detail',
  imports: [
    RouterLink,
    DecimalPipe,
    ProjectHeader,
    ProjectMap,
    BuildingLegend,
    SurveySummary,
    ValidationReport,
    ProjectFiles,
  ],
  providers: [ProjectDetailStore],
  templateUrl: './project-detail.html',
})
export class ProjectDetail {
  protected readonly store = inject(ProjectDetailStore);
  private readonly projectForm = inject(ProjectFormDialogService);
  private readonly confirmDialog = inject(ConfirmDialogService);
  private readonly router = inject(Router);

  /** Bound from the `:id` route param. */
  readonly id = input.required<string>();

  private readonly rootUrl = inject(ApiConfiguration).rootUrl;
  /** Download links (boundary + buildings + IDs + survey users). */
  protected readonly exports = computed(() => {
    const base = `${this.rootUrl}/projects/${this.id()}/export`;
    return [
      { label: 'KMZ', url: `${base}/kmz`, title: 'Google Earth' },
      { label: 'Excel', url: `${base}/xlsx`, title: 'One row per building' },
      { label: 'DXF', url: `${base}/dxf`, title: 'AutoCAD, UTM 36N metres' },
    ];
  });

  /** Review categories shown on the map. */
  protected readonly visible = signal<ReadonlySet<BuildingReviewKey>>(
    new Set(BUILDING_REVIEW_KEYS),
  );
  /** Place marked on the map (validation issue). */
  protected readonly focus = signal<GeoJsonGeometry | null>(null);

  constructor() {
    effect(() => this.store.load(this.id()));
  }

  protected showIssue(issue: ValidationIssue, mapCard: HTMLElement): void {
    // Copy: picking the same issue again zooms again.
    this.focus.set(issue.geometry ? { ...issue.geometry } : null);
    mapCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  protected edit(project: ProjectRead): void {
    this.projectForm.open(project).subscribe((saved) => this.store.projectSaved(saved));
  }

  protected removeProject(project: ProjectRead): void {
    this.confirmDialog
      .confirm({
        title: 'Delete project',
        message: `Delete "${project.name}" and all its files? This cannot be undone.`,
      })
      .pipe(
        filter(Boolean),
        switchMap(() => this.store.deleteProject(project)),
      )
      .subscribe(() => this.router.navigate(['/projects']));
  }

  protected removeFile(file: ProjectFileRead): void {
    this.confirmDialog
      .confirm({ title: 'Delete file', message: `Delete "${file.original_filename}"?` })
      .pipe(filter(Boolean))
      .subscribe(() => this.store.deleteFile(file));
  }
}
