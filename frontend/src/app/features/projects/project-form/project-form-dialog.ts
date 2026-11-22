import { Component, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';
import { Observable } from 'rxjs';

import { ProjectRead } from '../../../api/models/project-read';
import { ProjectStatus } from '../../../api/models/project-status';
import { ProjectsService } from '../../../api/services/projects.service';
import { apiErrorMessage } from '../../../shared/api-error';
import { PROJECT_STATUS_LABEL, PROJECT_STATUSES } from '../../../shared/labels';

/** Create a project, or edit one after `edit(project)`. Closes with the saved ProjectRead.
 *  Open it through ProjectFormDialogService. */
@Component({
  selector: 'app-project-form-dialog',
  imports: [ReactiveFormsModule],
  templateUrl: './project-form-dialog.html',
})
export class ProjectFormDialog {
  protected readonly modal = inject(NgbActiveModal);
  private readonly projects = inject(ProjectsService);

  protected readonly project = signal<ProjectRead | undefined>(undefined);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly statuses = PROJECT_STATUSES;
  protected readonly statusLabel = PROJECT_STATUS_LABEL;

  protected readonly form = new FormGroup({
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

  protected save(): void {
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
