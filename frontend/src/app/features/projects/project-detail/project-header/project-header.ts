import { DatePipe } from '@angular/common';
import { Component, input, output } from '@angular/core';

import { ProjectRead } from '../../../../api/models/project-read';
import { PROJECT_STATUS_BADGE, PROJECT_STATUS_LABEL } from '../../../../shared/labels';

@Component({
  selector: 'app-project-header',
  imports: [DatePipe],
  template: `
    @let p = project();
    <div class="d-flex align-items-start mb-4">
      <div class="me-auto">
        <h1 class="h3 mb-1" dir="auto">
          {{ p.name }}
          <span class="badge fs-6 align-middle" [class]="statusBadge[p.status]">
            {{ statusLabel[p.status] }}
          </span>
        </h1>
        @if (p.description) {
          <p class="text-muted mb-1" dir="auto">{{ p.description }}</p>
        }
        <div class="small text-muted">Created {{ p.created_at | date: 'medium' }}</div>
      </div>
      <button type="button" class="btn btn-outline-secondary me-2" (click)="edit.emit(p)">
        Edit
      </button>
      <button type="button" class="btn btn-outline-danger" (click)="remove.emit(p)">Delete</button>
    </div>
  `,
})
export class ProjectHeader {
  readonly project = input.required<ProjectRead>();
  readonly edit = output<ProjectRead>();
  readonly remove = output<ProjectRead>();

  protected readonly statusLabel = PROJECT_STATUS_LABEL;
  protected readonly statusBadge = PROJECT_STATUS_BADGE;
}
