import { Component, inject, signal } from '@angular/core';
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap';

/** Modal content; open it through ConfirmDialogService. */
@Component({
  selector: 'app-confirm-dialog',
  template: `
    <div class="modal-header">
      <h5 class="modal-title">{{ title() }}</h5>
      <button type="button" class="btn-close" aria-label="Close" (click)="modal.dismiss()"></button>
    </div>
    <div class="modal-body" dir="auto">{{ message() }}</div>
    <div class="modal-footer">
      <button type="button" class="btn btn-outline-secondary" (click)="modal.dismiss()">
        Cancel
      </button>
      <button type="button" class="btn btn-danger" (click)="modal.close(true)">
        {{ confirmLabel() }}
      </button>
    </div>
  `,
})
export class ConfirmDialog {
  protected readonly modal = inject(NgbActiveModal);
  readonly title = signal('Are you sure?');
  readonly message = signal('');
  readonly confirmLabel = signal('Delete');
}
