import { TestBed } from '@angular/core/testing';

import { ProjectFileRead } from '../../../../api/models/project-file-read';
import { sampleFile } from '../../../../testing/fixtures';
import { ProjectFiles } from './project-files';

function setup(files: ProjectFileRead[]) {
  const fixture = TestBed.createComponent(ProjectFiles);
  fixture.componentRef.setInput('files', files);
  fixture.detectChanges();
  return { fixture, el: fixture.nativeElement as HTMLElement };
}

function buttons(el: HTMLElement, text: string): HTMLButtonElement[] {
  return [...el.querySelectorAll('button')].filter((b) => b.textContent?.trim() === text);
}

describe('ProjectFiles', () => {
  it('shows an empty state', () => {
    expect(setup([]).el.textContent).toContain('No files yet');
  });

  it('offers Re-process only for importable files that are not processing', () => {
    const { el } = setup([
      sampleFile({ id: 'a', kind: 'dxf', status: 'failed', error: 'Bad layers' }),
      sampleFile({ id: 'b', kind: 'dwg', status: 'processing' }),
      sampleFile({ id: 'c', kind: 'other', original_filename: 'plot.pdf' }),
    ]);
    expect(buttons(el, 'Re-process')).toHaveLength(1);
    expect(buttons(el, 'Delete')).toHaveLength(3);
    expect(el.textContent).toContain('Bad layers');
  });

  it('emits the file to re-process or delete', () => {
    const file = sampleFile({ status: 'failed' });
    const { fixture, el } = setup([file]);
    const reprocessed: ProjectFileRead[] = [];
    const removed: ProjectFileRead[] = [];
    fixture.componentInstance.reprocess.subscribe((f) => reprocessed.push(f));
    fixture.componentInstance.remove.subscribe((f) => removed.push(f));

    buttons(el, 'Re-process')[0].click();
    buttons(el, 'Delete')[0].click();
    expect(reprocessed).toEqual([file]);
    expect(removed).toEqual([file]);
  });
});
