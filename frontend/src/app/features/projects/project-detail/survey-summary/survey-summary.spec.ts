import { TestBed } from '@angular/core/testing';

import { SurveyLayer } from '../../../../api/models/survey-layer';
import { sampleSurvey } from '../../../../testing/fixtures';
import { MAX_LISTED_IDS, SurveySummary } from './survey-summary';

function render(survey: SurveyLayer): HTMLElement {
  const fixture = TestBed.createComponent(SurveySummary);
  fixture.componentRef.setInput('survey', survey);
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('SurveySummary', () => {
  it('shows how survey rows match the drawing', () => {
    const text = render(sampleSurvey()).textContent ?? '';
    expect(text).toMatch(/Survey rows\s*6/);
    expect(text).toMatch(/Total users\s*20/);
    expect(text).toMatch(/5 of 6 rows/);
    expect(text).toMatch(/Survey IDs not on the drawing\s*1\s*7/);
    expect(text).toMatch(/Drawing IDs without a survey row\s*2\s*2, 9/);
    expect(text).toContain('Provisional rules');
  });

  it('asks for the drawing before linking', () => {
    const text = render(sampleSurvey({ has_drawing: false })).textContent ?? '';
    expect(text).toContain('Upload the drawing');
    expect(text).not.toContain('not on the drawing');
  });

  it('shortens long ID lists', () => {
    const ids = Array.from({ length: MAX_LISTED_IDS + 5 }, (_, i) => String(i + 1));
    const text = render(sampleSurvey({ not_in_drawing: ids })).textContent ?? '';
    expect(text).toContain(`${MAX_LISTED_IDS} … and 5 more`);
    expect(text).not.toContain(`${MAX_LISTED_IDS + 1},`);
  });
});
