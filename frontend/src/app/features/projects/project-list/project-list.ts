import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { filter, switchMap } from 'rxjs';

import { ProjectRead } from '../../../api/models/project-read';
import { ProjectsService } from '../../../api/services/projects.service';
import { apiErrorMessage } from '../../../shared/api-error';
import { ConfirmDialogService } from '../../../shared/confirm-dialog/confirm-dialog-service';
import { PROJECT_STATUS_BADGE, PROJECT_STATUS_LABEL } from '../../../shared/labels';
import { ProjectFormDialogService } from '../project-form/project-form-dialog-service';

@Component({
  selector: 'app-project-list',
  imports: [RouterLink, DatePipe],
  templateUrl: './project-list.html',
  styleUrl: './project-list.scss',
})
export class ProjectList {
  private readonly api = inject(ProjectsService);
  private readonly projectForm = inject(ProjectFormDialogService);
  private readonly confirmDialog = inject(ConfirmDialogService);
  private readonly router = inject(Router);

  protected readonly projectsResource = rxResource({ stream: () => this.api.listProjects() });
  protected readonly projects = computed<ProjectRead[]>(() =>
    this.projectsResource.hasValue() ? this.projectsResource.value() : [],
  );
  private readonly actionError = signal<string | null>(null);
  protected readonly error = computed(() => {
    const loadError = this.projectsResource.error();
    return loadError ? apiErrorMessage(loadError) : this.actionError();
  });

  protected readonly statusLabel = PROJECT_STATUS_LABEL;
  protected readonly statusBadge = PROJECT_STATUS_BADGE;

  protected reload(): void {
    this.actionError.set(null);
    this.projectsResource.reload();
  }

  protected create(): void {
    this.projectForm.open().subscribe((p) => this.router.navigate(['/projects', p.id]));
  }

  protected edit(project: ProjectRead): void {
    this.projectForm.open(project).subscribe(() => this.reload());
  }

  protected remove(project: ProjectRead): void {
    this.confirmDialog
      .confirm({
        title: 'Delete project',
        message: `Delete "${project.name}" and its ${project.file_count} uploaded file(s)? This cannot be undone.`,
      })
      .pipe(
        filter(Boolean),
        switchMap(() => this.api.deleteProject({ project_id: project.id })),
      )
      .subscribe({
        next: () => this.reload(),
        error: (err: unknown) => this.actionError.set(apiErrorMessage(err)),
      });
  }
}
