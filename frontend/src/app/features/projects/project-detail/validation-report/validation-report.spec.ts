import { TestBed } from '@angular/core/testing';

import { provideApiConfiguration } from '../../../../api/api-configuration';
import { ValidationIssue } from '../../../../api/models/validation-issue';
import { ValidationReport as Report } from '../../../../api/models/validation-report';
import { PROJECT_ID, sampleValidation } from '../../../../testing/fixtures';
import { PAGE_SIZE, ValidationReport } from './validation-report';

function setup(report: Report = sampleValidation()) {
  TestBed.configureTestingModule({ providers: [provideApiConfiguration('/api')] });
  const fixture = TestBed.createComponent(ValidationReport);
  fixture.componentRef.setInput('report', report);
  fixture.componentRef.setInput('projectId', PROJECT_ID);
  fixture.detectChanges();
  const el = fixture.nativeElement as HTMLElement;
  const checks = () => [...el.querySelectorAll<HTMLButtonElement>('[role=option]')];
  const rows = () => [...el.querySelectorAll('tbody tr')].map((r) => r.textContent ?? '');
  return { fixture, el, checks, rows };
}

describe('ValidationReport', () => {
  it('shows totals, checks and an Excel download link', () => {
    const { el, checks } = setup();
    const header = el.querySelector('.card-header')?.textContent ?? '';
    expect(header).toContain('1 errors');
    expect(header).toContain('2 warnings');
    expect(header).toContain('1 info');
    expect(header).toContain('GPS limit 25 m');
    expect(el.querySelector('a[download]')?.getAttribute('href')).toBe(
      `/api/projects/${PROJECT_ID}/validation/export`,
    );
    // Badge, title and count are separate elements (spaced by CSS gap).
    const texts = checks().map((b) => [...b.children].map((c) => c.textContent?.trim()).join(' '));
    expect(texts).toEqual([
      'error Building ID not inside any building 1',
      'error Duplicate 0',
      'warning Survey GPS far from its building 2',
      'info Building without ID 1',
    ]);
    expect(checks()[1].disabled).toBe(true); // nothing to show
  });

  it('lists the issues of the selected check (first check with issues by default)', () => {
    const { fixture, checks, rows } = setup();
    expect(rows()).toHaveLength(1);
    expect(rows()[0]).toContain('ID 9 is outside');

    checks()[2].click();
    fixture.detectChanges();
    expect(rows()).toHaveLength(2);
    expect(rows()[0]).toContain('GPS is 50 m');
  });

  it('emits the issue to show on the map (only when it has a location)', () => {
    const { fixture, el, checks } = setup();
    const shown: ValidationIssue[] = [];
    fixture.componentInstance.show.subscribe((i) => shown.push(i));
    checks()[2].click();
    fixture.detectChanges();

    const showButtons = [...el.querySelectorAll<HTMLButtonElement>('tbody button')];
    expect(showButtons).toHaveLength(1); // second issue has no geometry
    showButtons[0].click();
    expect(shown.map((i) => i.code)).toEqual(['3']);
  });

  it('pages long issue lists', () => {
    const many = Array.from({ length: PAGE_SIZE + 3 }, (_, n) => ({
      ...sampleValidation().issues[0],
      code: String(n),
    }));
    const report = sampleValidation({
      rules: [{ ...sampleValidation().rules[0], count: many.length }],
      issues: many,
    });
    const { fixture, el, rows } = setup(report);
    expect(rows()).toHaveLength(PAGE_SIZE);
    const more = [...el.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('Show more'),
    );
    expect(more?.textContent).toContain('3 left');
    more?.click();
    fixture.detectChanges();
    expect(rows()).toHaveLength(PAGE_SIZE + 3);
  });
});
