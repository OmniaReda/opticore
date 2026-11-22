import { DecimalPipe } from '@angular/common';
import { Component, input } from '@angular/core';

import { SurveyLayer } from '../../../../api/models/survey-layer';

/** How many Building IDs to list before "and N more". */
export const MAX_LISTED_IDS = 30;

/** Survey Excel rows and how they match the Building IDs on the drawing. */
@Component({
  selector: 'app-survey-summary',
  imports: [DecimalPipe],
  templateUrl: './survey-summary.html',
})
export class SurveySummary {
  readonly survey = input.required<SurveyLayer>();

  protected listed(ids: readonly string[]): string {
    const shown = ids.slice(0, MAX_LISTED_IDS).join(', ');
    const more = ids.length - MAX_LISTED_IDS;
    return more > 0 ? `${shown} … and ${more} more` : shown;
  }
}
