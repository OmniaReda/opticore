import { DecimalPipe } from '@angular/common';
import { Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
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
import { BoxDesignPanel } from './box-design/box-design-panel';
import { BoxDesignStore } from './box-design/box-design-store';
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
    BoxDesignPanel,
    ProjectFiles,
  ],
  providers: [ProjectDetailStore, BoxDesignStore],
  templateUrl: './project-detail.html',
})
export class ProjectDetail {
  protected readonly store = inject(ProjectDetailStore);
  protected readonly boxes = inject(BoxDesignStore);
  private readonly projectForm = inject(ProjectFormDialogService);
  private readonly confirmDialog = inject(ConfirmDialogService);
  private readonly router = inject(Router);

  /** Bound from the `:id` route param. */
  readonly id = input.required<string>();

  private readonly rootUrl = inject(ApiConfiguration).rootUrl;
  /** Download links (boundary + buildings + IDs + survey users). */
  protected readonly exports = computed(() => {
    const base = `${this.rootUrl}/projects/${this.id()}/export`;
    const all = [
      { label: 'KMZ', url: `${base}/kmz`, title: 'Google Earth' },
      { label: 'Excel', url: `${base}/xlsx`, title: 'One row per building' },
      { label: 'DXF', url: `${base}/dxf`, title: 'AutoCAD, UTM 36N metres' },
    ];
    const buildings = this.store.buildings();
    if (buildings && (buildings.summary.total || buildings.summary.orphan_ids)) {
      // The whole map in the survey template: one row per Building ID, street names filled in.
      all.unshift({
        label: 'Survey sheet (Excel)',
        url: `${base}/survey-sheet`,
        title:
          'One row per Building ID in the survey template, with street names and all known data',
      });
    }
    // Street names come from OpenStreetMap inside the boundary: available right after the first KML.
    if (this.store.layers()?.boundary) {
      all.push({
        label: 'Streets & numbers (Excel)',
        url: `${base}/streets`,
        title: 'House numbers and street names inside the boundary, from OpenStreetMap',
      });
    }
    return all;
  });

  /** Why boxes cannot be placed yet, or null. */
  protected readonly boxesBlocked = computed(() => {
    const buildings = this.store.buildings();
    if (!buildings?.summary.total) {
      return 'Upload the drawing (DXF/DWG) and the survey Excel: boxes are placed on the buildings and sized by their Total Users.';
    }
    if (!this.store.survey()?.summary.total_users) {
      return "Upload the survey Excel: boxes are sized by each building's Total Users.";
    }
    return null;
  });

  /** Changes when a file is added, removed or processed. */
  private readonly filesKey = computed(() =>
    this.store
      .files()
      .map((f) => `${f.id}:${f.status}`)
      .join('|'),
  );

  /** Review categories shown on the map. */
  protected readonly visible = signal<ReadonlySet<BuildingReviewKey>>(
    new Set(BUILDING_REVIEW_KEYS),
  );
  /** Place marked on the map (validation issue). */
  protected readonly focus = signal<GeoJsonGeometry | null>(null);

  constructor() {
    effect(() => this.store.load(this.id()));
    // A design made before the drawing or survey changed no longer matches the map.
    effect(() => {
      this.filesKey();
      untracked(() => this.boxes.clear());
    });
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
