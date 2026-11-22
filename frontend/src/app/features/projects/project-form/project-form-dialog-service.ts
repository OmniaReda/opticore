import { Injectable, inject } from '@angular/core';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { EMPTY, Observable, catchError, from } from 'rxjs';

import { ProjectRead } from '../../../api/models/project-read';
import { ProjectFormDialog } from './project-form-dialog';

@Injectable({ providedIn: 'root' })
export class ProjectFormDialogService {
  private readonly modals = inject(NgbModal);

  /** Opens the create form, or the edit form for `project`.
   *  Emits the saved project; completes without a value if cancelled. */
  open(project?: ProjectRead): Observable<ProjectRead> {
    const ref = this.modals.open(ProjectFormDialog, { backdrop: 'static' });
    if (project) {
      (ref.componentInstance as ProjectFormDialog).edit(project);
    }
    return from(ref.result as Promise<ProjectRead>).pipe(catchError(() => EMPTY));
  }
}
