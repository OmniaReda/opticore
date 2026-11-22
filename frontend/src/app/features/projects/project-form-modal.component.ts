import { Component, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { Observable } from 'rxjs';

import { ProjectRead } from '../../api/models/project-read';
import { ProjectStatus } from '../../api/models/project-status';
import { ProjectsService } from '../../api/services/projects.service';
import { apiErrorMessage } from '../../shared/api-error';
import { PROJECT_STATUS_LABEL, PROJECT_STATUSES } from '../../shared/labels';

/** Create a project, or edit one after `edit(project)` is called. Closes with the saved ProjectRead. */
@Component({
  selector: 'app-project-form-modal',
  imports: [ReactiveFormsModule],
  template: `
    <form [formGroup]="form" (ngSubmit)="save()" novalidate>
      <div class="modal-header">
        <h5 class="modal-title">{{ project() ? 'Edit project' : 'New project' }}</h5>
        <button type="button" class="btn-close" aria-label="Close" (click)="modal.dismiss()"></button>
      </div>

      <div class="modal-body">
        @if (error()) {
          <div class="alert alert-danger py-2" dir="auto">{{ error() }}</div>
        }

        <div class="mb-3">
          <label class="form-label" for="name">Name</label>
          <input id="name" class="form-control" formControlName="name" dir="auto" autocomplete="off"
                 [class.is-invalid]="form.controls.name.touched && form.controls.name.invalid" />
          <div class="invalid-feedback">Name is required (max 200 characters).</div>
        </div>

        <div class="mb-3">
          <label class="form-label" for="description">Description</label>
          <textarea id="description" class="form-control" rows="3" formControlName="description" dir="auto"></textarea>
        </div>

        @if (project()) {
          <div class="mb-1">
            <label class="form-label" for="status">Status</label>
            <select id="status" class="form-select" formControlName="status">
              @for (s of statuses; track s) {
                <option [value]="s">{{ statusLabel[s] }}</option>
              }
            </select>
          </div>
        }
      </div>

      <div class="modal-footer">
        <button type="button" class="btn btn-outline-secondary" (click)="modal.dismiss()">Cancel</button>
        <button type="submit" class="btn btn-primary" [disabled]="saving()">
          @if (saving()) {
            <span class="spinner-border spinner-border-sm me-1"></span>
          }
          Save
        </button>
      </div>
    </form>
  `,
})
export class ProjectFormModalComponent {
  readonly modal = inject(NgbActiveModal);
  private readonly projects = inject(ProjectsService);

  readonly project = signal<ProjectRead | undefined>(undefined);

  readonly statuses = PROJECT_STATUSES;
  readonly statusLabel = PROJECT_STATUS_LABEL;
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);

  readonly form = new FormGroup({
    name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(200), Validators.pattern(/\S/)],
    }),
    description: new FormControl('', { nonNullable: true }),
    status: new FormControl<ProjectStatus>('draft', { nonNullable: true }),
  });

  /** Switch to edit mode for an existing project. */
  edit(p: ProjectRead): void {
    this.project.set(p);
    this.form.setValue({ name: p.name, description: p.description ?? '', status: p.status });
  }

  save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { name, description, status } = this.form.getRawValue();
    const body = { name: name.trim(), description: description.trim() || null };
    const p = this.project();
    const request$: Observable<ProjectRead> = p
      ? this.projects.updateProject({ project_id: p.id, body: { ...body, status } })
      : this.projects.createProject({ body });

    this.saving.set(true);
    this.error.set(null);
    request$.subscribe({
      next: (saved) => this.modal.close(saved),
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err));
        this.saving.set(false);
      },
    });
  }
}
