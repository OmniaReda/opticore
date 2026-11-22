import { TestBed } from '@angular/core/testing';

import { BUILDING_REVIEW_KEYS, BuildingReviewKey } from '../../../../shared/labels';
import { sampleBuildings } from '../../../../testing/fixtures';
import { BuildingLegend } from './building-legend';

function setup(provisional = true) {
  const fixture = TestBed.createComponent(BuildingLegend);
  fixture.componentRef.setInput('buildings', sampleBuildings({ provisional }));
  fixture.componentRef.setInput('visible', new Set<BuildingReviewKey>(BUILDING_REVIEW_KEYS));
  fixture.detectChanges();
  return { fixture, el: fixture.nativeElement as HTMLElement };
}

describe('BuildingLegend', () => {
  it('shows the count of each review status and the boundary position', () => {
    const { el } = setup();
    const text = el.textContent ?? '';
    expect(text).toContain('Buildings 6');
    expect(text).toMatch(/One ID\s*4/);
    expect(text).toMatch(/Several IDs\s*1/);
    expect(text).toMatch(/ID outside any building\s*1/);
    expect(text).toContain('inside boundary 4, crossing 1, outside 1');
  });

  it('marks provisional rules', () => {
    expect(setup(true).el.textContent).toContain('Provisional rules');
    expect(setup(false).el.textContent).not.toContain('Provisional rules');
  });

  it('toggles a status in the two-way bound set', () => {
    const { fixture, el } = setup();
    const checkboxes = el.querySelectorAll<HTMLInputElement>('input[type=checkbox]');
    expect(checkboxes).toHaveLength(BUILDING_REVIEW_KEYS.length);

    checkboxes[1].click(); // multiple_ids off
    expect([...fixture.componentInstance.visible()]).toEqual(['ok', 'no_id', 'orphan']);
    checkboxes[1].click(); // and on again
    expect(fixture.componentInstance.visible().has('multiple_ids')).toBe(true);
  });
});
