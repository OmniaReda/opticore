import { ComponentFixture, TestBed } from '@angular/core/testing';

import { BoxDesignRequest } from '../../../../api/models/box-design-request';
import { sampleBoxDesign } from '../../../../testing/fixtures';
import { BoxDesignPanel, STORAGE_KEY } from './box-design-panel';

function setup(inputs: Record<string, unknown> = {}): ComponentFixture<BoxDesignPanel> {
  const fixture = TestBed.createComponent(BoxDesignPanel);
  for (const [name, value] of Object.entries(inputs)) {
    fixture.componentRef.setInput(name, value);
  }
  fixture.detectChanges();
  return fixture;
}

function type(el: HTMLElement, selector: string, value: string): void {
  const input = el.querySelector<HTMLInputElement>(selector);
  if (!input) {
    throw new Error(`no ${selector}`);
  }
  input.value = value;
  input.dispatchEvent(new Event('input'));
}

describe('BoxDesignPanel', () => {
  beforeEach(() => localStorage.removeItem(STORAGE_KEY));

  it('sends the entered box types and limits', () => {
    const fixture = setup();
    const el = fixture.nativeElement as HTMLElement;
    const sent: BoxDesignRequest[] = [];
    fixture.componentInstance.run.subscribe((r) => sent.push(r));

    type(el, '#box-name-0', '  Test box ');
    type(el, '#box-capacity-0', '12');
    type(el, '#max-drop', '40');
    el.querySelector('form')?.dispatchEvent(new Event('submit'));

    expect(sent).toEqual([
      {
        box_types: [{ name: 'Test box', capacity: 12 }],
        max_drop_m: 40,
        spare_percent: 0,
        include_outside: false,
      },
    ]);
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}')).toEqual(sent[0]); // remembered
  });

  it('does not send an incomplete box type', () => {
    const fixture = setup();
    const el = fixture.nativeElement as HTMLElement;
    const sent: BoxDesignRequest[] = [];
    fixture.componentInstance.run.subscribe((r) => sent.push(r));
    type(el, '#box-name-0', 'No capacity');
    el.querySelector('form')?.dispatchEvent(new Event('submit'));
    expect(sent).toEqual([]);
  });

  it('starts from the last values entered', () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        box_types: [
          { name: 'A', capacity: 8 },
          { name: 'B', capacity: 16 },
        ],
        max_drop_m: null,
        spare_percent: 10,
        include_outside: false,
      }),
    );
    const el = setup().nativeElement as HTMLElement;
    expect(el.querySelector<HTMLInputElement>('#box-name-1')?.value).toBe('B');
    expect(el.querySelector<HTMLInputElement>('#spare')?.value).toBe('10');
  });

  it('explains what is missing instead of the form', () => {
    const el = setup({ blocked: 'Upload the survey Excel' }).nativeElement as HTMLElement;
    expect(el.textContent).toContain('Upload the survey Excel');
    expect(el.querySelector('form')).toBeNull();
  });

  it('shows the result summary', () => {
    const text = (setup({ design: sampleBoxDesign() }).nativeElement as HTMLElement).textContent;
    expect(text).toMatch(/Boxes\s*2/);
    expect(text).toContain('Test-16 (16): 2');
    expect(text).toMatch(/18 in 2 buildings/);
    expect(text).toContain('2, 5');
    expect(text).toContain('Provisional');
  });
});
