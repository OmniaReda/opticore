import { Component, inject, signal } from '@angular/core';
import { NgbActiveModal, NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { Observable, from, map, catchError, of } from 'rxjs';

@Component({
  selector: 'app-confirm-dialog',
  template: `
    <div class="modal-header">
      <h5 class="modal-title">{{ title() }}</h5>
      <button type="button" class="btn-close" aria-label="Close" (click)="modal.dismiss()"></button>
    </div>
    <div class="modal-body" dir="auto">{{ message() }}</div>
    <div class="modal-footer">
      <button type="button" class="btn btn-outline-secondary" (click)="modal.dismiss()">Cancel</button>
      <button type="button" class="btn btn-danger" (click)="modal.close(true)">{{ confirmLabel() }}</button>
    </div>
  `,
})
export class ConfirmDialogComponent {
  readonly modal = inject(NgbActiveModal);
  readonly title = signal('Are you sure?');
  readonly message = signal('');
  readonly confirmLabel = signal('Delete');
}

/** Opens a confirm dialog; emits true on confirm, false on cancel. */
export function confirmDialog(
  modals: NgbModal,
  opts: { title: string; message: string; confirmLabel?: string },
): Observable<boolean> {
  const ref = modals.open(ConfirmDialogComponent);
  const dialog = ref.componentInstance as ConfirmDialogComponent;
  dialog.title.set(opts.title);
  dialog.message.set(opts.message);
  if (opts.confirmLabel) {
    dialog.confirmLabel.set(opts.confirmLabel);
  }
  return from(ref.result as Promise<boolean>).pipe(
    map(Boolean),
    catchError(() => of(false)),
  );
}
