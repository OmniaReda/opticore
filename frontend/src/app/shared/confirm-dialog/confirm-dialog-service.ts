import { Injectable, inject } from '@angular/core';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { Observable, catchError, from, map, of } from 'rxjs';

import { ConfirmDialog } from './confirm-dialog';

export interface ConfirmOptions {
  title: string;
  message: string;
  confirmLabel?: string;
}

@Injectable({ providedIn: 'root' })
export class ConfirmDialogService {
  private readonly modals = inject(NgbModal);

  /** Emits true on confirm, false on cancel / dismiss, then completes. */
  confirm(options: ConfirmOptions): Observable<boolean> {
    const ref = this.modals.open(ConfirmDialog);
    const dialog = ref.componentInstance as ConfirmDialog;
    dialog.title.set(options.title);
    dialog.message.set(options.message);
    if (options.confirmLabel) {
      dialog.confirmLabel.set(options.confirmLabel);
    }
    return from(ref.result as Promise<unknown>).pipe(
      map((result) => result === true),
      catchError(() => of(false)),
    );
  }
}
