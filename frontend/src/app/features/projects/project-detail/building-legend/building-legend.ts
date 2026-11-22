import { Component, input, model } from '@angular/core';

import { BuildingLayer } from '../../../../api/models/building-layer';
import {
  BUILDING_REVIEW_COLOR,
  BUILDING_REVIEW_KEYS,
  BUILDING_REVIEW_LABEL,
  BuildingReviewKey,
} from '../../../../shared/labels';

/** Building counts per review status, with a checkbox to show/hide each status on the map. */
@Component({
  selector: 'app-building-legend',
  template: `
    @let s = buildings().summary;
    <div class="small d-flex flex-wrap align-items-center gap-3">
      <span class="fw-semibold">Buildings {{ s.total }}</span>
      @for (key of keys; track key) {
        <label class="form-check-label d-flex align-items-center gap-1">
          <input
            type="checkbox"
            class="form-check-input mt-0"
            [checked]="visible().has(key)"
            (change)="toggle(key)"
          />
          <span class="swatch" aria-hidden="true" [style.background]="color[key]"></span>
          {{ label[key] }} <strong>{{ count(key) }}</strong>
        </label>
      }
      @if (s.inside !== null) {
        <span class="text-muted">
          · inside boundary {{ s.inside }}, crossing {{ s.crossing }}, outside {{ s.outside }}
          (dashed)
        </span>
      }
      @if (buildings().provisional) {
        <span
          class="badge text-bg-warning ms-auto"
          title="CAD reading rules (backend/app/rules/cad_layers.yaml) are status TBC"
        >
          Provisional rules
        </span>
      }
    </div>
  `,
  styles: `
    .swatch {
      display: inline-block;
      width: 0.9rem;
      height: 0.9rem;
      border-radius: 0.2rem;
    }
  `,
})
export class BuildingLegend {
  readonly buildings = input.required<BuildingLayer>();
  /** Review categories shown on the map (two-way bound). */
  readonly visible = model.required<ReadonlySet<BuildingReviewKey>>();

  protected readonly keys = BUILDING_REVIEW_KEYS;
  protected readonly label = BUILDING_REVIEW_LABEL;
  protected readonly color = BUILDING_REVIEW_COLOR;

  protected count(key: BuildingReviewKey): number {
    const s = this.buildings().summary;
    return key === 'orphan' ? s.orphan_ids : s[key];
  }

  protected toggle(key: BuildingReviewKey): void {
    this.visible.update((current) => {
      const next = new Set(current);
      if (!next.delete(key)) {
        next.add(key);
      }
      return next;
    });
  }
}
