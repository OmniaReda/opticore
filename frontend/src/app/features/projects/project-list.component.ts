import { DatePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { filter, finalize, switchMap } from 'rxjs';

import { ProjectRead } from '../../api/models/project-read';
import { ProjectsService } from '../../api/services/projects.service';
import { apiErrorMessage } from '../../shared/api-error';
import { confirmDialog } from '../../shared/confirm-dialog.component';
import { PROJECT_STATUS_BADGE, PROJECT_STATUS_LABEL } from '../../shared/labels';
import { openProjectForm } from './open-project-form';

@Component({
  selector: 'app-project-list',
  imports: [RouterLink, DatePipe],
  template: `
    <div class="d-flex align-items-center mb-3">
      <h1 class="h3 mb-0 me-auto">Projects</h1>
      <button type="button" class="btn btn-primary" (click)="create()">+ New project</button>
    </div>

    @if (error()) {
      <div class="alert alert-danger d-flex align-items-center">
        <span class="me-auto" dir="auto">{{ error() }}</span>
        <button type="button" class="btn btn-sm btn-outline-danger" (click)="load()">Retry</button>
      </div>
    }

    @if (loading()) {
      <div class="text-center py-5"><span class="spinner-border"></span></div>
    } @else if (projects().length === 0 && !error()) {
      <div class="card card-body text-center text-muted py-5">
        No projects yet. Create one to start importing files.
      </div>
    } @else if (projects().length > 0) {
      <div class="card">
        <table class="table table-hover align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th class="text-end">Files</th>
              <th>Last updated</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (p of projects(); track p.id) {
              <tr>
                <td>
                  <a [routerLink]="['/projects', p.id]" class="fw-semibold" dir="auto">{{ p.name }}</a>
                  @if (p.description) {
                    <div class="small text-muted text-truncate" style="max-width: 32rem" dir="auto">
                      {{ p.description }}
                    </div>
                  }
                </td>
                <td><span class="badge" [class]="statusBadge[p.status]">{{ statusLabel[p.status] }}</span></td>
                <td class="text-end">{{ p.file_count }}</td>
                <td class="text-nowrap">{{ p.updated_at | date: 'medium' }}</td>
                <td class="text-end text-nowrap">
                  <button type="button" class="btn btn-sm btn-outline-secondary me-1" (click)="edit(p)">Edit</button>
                  <button type="button" class="btn btn-sm btn-outline-danger" (click)="remove(p)">Delete</button>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    }
  `,
})
export class ProjectListComponent implements OnInit {
  private readonly api = inject(ProjectsService);
  private readonly modals = inject(NgbModal);
  private readonly router = inject(Router);

  readonly projects = signal<ProjectRead[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  readonly statusLabel = PROJECT_STATUS_LABEL;
  readonly statusBadge = PROJECT_STATUS_BADGE;

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api
      .listProjects()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (list) => this.projects.set(list),
        error: (err: unknown) => this.error.set(apiErrorMessage(err)),
      });
  }

  create(): void {
    openProjectForm(this.modals).subscribe((p) => this.router.navigate(['/projects', p.id]));
  }

  edit(project: ProjectRead): void {
    openProjectForm(this.modals, project).subscribe(() => this.load());
  }

  remove(project: ProjectRead): void {
    confirmDialog(this.modals, {
      title: 'Delete project',
      message: `Delete "${project.name}" and its ${project.file_count} uploaded file(s)? This cannot be undone.`,
    })
      .pipe(
        filter(Boolean),
        switchMap(() => this.api.deleteProject({ project_id: project.id })),
      )
      .subscribe({
        next: () => this.load(),
        error: (err: unknown) => this.error.set(apiErrorMessage(err)),
      });
  }
}
