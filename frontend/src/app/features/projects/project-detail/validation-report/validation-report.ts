import { Component, computed, inject, input, linkedSignal, output, signal } from '@angular/core';

import { ApiConfiguration } from '../../../../api/api-configuration';
import { ValidationIssue } from '../../../../api/models/validation-issue';
import { ValidationReport as Report } from '../../../../api/models/validation-report';
import { ValidationRule } from '../../../../api/models/validation-rule';
import { ISSUE_SEVERITY_BADGE } from '../../../../shared/labels';

/** Issues shown at once for the selected check (the Excel export has all of them). */
export const PAGE_SIZE = 50;

/** Stage 03 consistency report: checks with their issue counts; click a check to list its issues. */
@Component({
  selector: 'app-validation-report',
  templateUrl: './validation-report.html',
  styles: `
    .issues {
      max-height: 26rem;
      overflow-y: auto;
    }
  `,
})
export class ValidationReport {
  private readonly api = inject(ApiConfiguration);

  readonly report = input.required<Report>();
  readonly projectId = input.required<string>();
  /** The user wants to see an issue on the map. */
  readonly show = output<ValidationIssue>();

  protected readonly badge = ISSUE_SEVERITY_BADGE;

  /** Selected check: the first one with issues, until the user picks another. */
  protected readonly selected = linkedSignal<Report, ValidationRule | null>({
    source: this.report,
    computation: (report, previous) =>
      previous?.value ?? report.rules.find((r) => r.count > 0)?.rule ?? null,
  });
  protected readonly limit = signal(PAGE_SIZE);

  protected readonly selectedIssues = computed(() =>
    this.report().issues.filter((i) => i.rule === this.selected()),
  );
  protected readonly visibleIssues = computed(() => this.selectedIssues().slice(0, this.limit()));
  protected readonly totals = computed(() => {
    const issues = this.report().issues;
    return {
      error: issues.filter((i) => i.severity === 'error').length,
      warning: issues.filter((i) => i.severity === 'warning').length,
      info: issues.filter((i) => i.severity === 'info').length,
    };
  });
  protected readonly exportUrl = computed(
    () => `${this.api.rootUrl}/projects/${this.projectId()}/validation/export`,
  );

  protected select(rule: ValidationRule): void {
    this.selected.set(rule);
    this.limit.set(PAGE_SIZE);
  }

  protected showMore(): void {
    this.limit.update((n) => n + PAGE_SIZE);
  }
}
