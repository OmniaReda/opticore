import { DecimalPipe } from '@angular/common';
import { Component, effect, inject, input, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { filter, switchMap } from 'rxjs';

import { ProjectFileRead } from '../../../api/models/project-file-read';
import { ProjectRead } from '../../../api/models/project-read';
import { ConfirmDialogService } from '../../../shared/confirm-dialog/confirm-dialog-service';
import { BUILDING_REVIEW_KEYS, BuildingReviewKey } from '../../../shared/labels';
import { ProjectFormDialogService } from '../project-form/project-form-dialog-service';
import { BuildingLegend } from './building-legend/building-legend';
import { ProjectDetailStore } from './project-detail-store';
import { ProjectFiles } from './project-files/project-files';
import { ProjectHeader } from './project-header/project-header';
import { ProjectMap } from './project-map/project-map';
import { SurveySummary } from './survey-summary/survey-summary';

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

  /** Review categories shown on the map. */
  protected readonly visible = signal<ReadonlySet<BuildingReviewKey>>(
    new Set(BUILDING_REVIEW_KEYS),
  );

  constructor() {
    effect(() => this.store.load(this.id()));
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
