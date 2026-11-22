import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { EMPTY, Observable, catchError, from } from 'rxjs';

import { ProjectRead } from '../../api/models/project-read';
import { ProjectFormModalComponent } from './project-form-modal.component';

/** Opens the project form. Emits the saved project; completes without a value if cancelled. */
export function openProjectForm(modals: NgbModal, project?: ProjectRead): Observable<ProjectRead> {
  const ref = modals.open(ProjectFormModalComponent, { backdrop: 'static' });
  if (project) {
    (ref.componentInstance as ProjectFormModalComponent).edit(project);
  }
  return from(ref.result as Promise<ProjectRead>).pipe(catchError(() => EMPTY));
}
