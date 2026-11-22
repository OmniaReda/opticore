import { DatePipe } from '@angular/common';
import { Component, input, output } from '@angular/core';

import { ProjectFileRead } from '../../../../api/models/project-file-read';
import { FileSizePipe } from '../../../../shared/file-size-pipe';
import {
  ACCEPTED_FILE_TYPES,
  FILE_KIND_LABEL,
  FILE_STATUS_BADGE,
  FILE_STATUS_LABEL,
} from '../../../../shared/labels';
import { IMPORTABLE_KINDS, UploadError } from '../project-detail-store';

/** Uploaded files of a project, with upload / re-process / delete. */
@Component({
  selector: 'app-project-files',
  imports: [DatePipe, FileSizePipe],
  templateUrl: './project-files.html',
})
export class ProjectFiles {
  readonly files = input.required<readonly ProjectFileRead[]>();
  readonly uploading = input(false);
  readonly uploadErrors = input<readonly UploadError[]>([]);

  readonly upload = output<File[]>();
  readonly reprocess = output<ProjectFileRead>();
  readonly remove = output<ProjectFileRead>();

  protected readonly accept = ACCEPTED_FILE_TYPES;
  protected readonly kindLabel = FILE_KIND_LABEL;
  protected readonly statusLabel = FILE_STATUS_LABEL;
  protected readonly statusBadge = FILE_STATUS_BADGE;

  protected canReprocess(f: ProjectFileRead): boolean {
    return IMPORTABLE_KINDS.includes(f.kind) && f.status !== 'processing';
  }

  protected onFilesSelected(event: Event): void {
    const inputEl = event.target as HTMLInputElement;
    const selected = Array.from(inputEl.files ?? []);
    inputEl.value = ''; // allow re-selecting the same file
    if (selected.length > 0) {
      this.upload.emit(selected);
    }
  }
}
