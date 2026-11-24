import { DecimalPipe } from '@angular/common';
import { Component, effect, input, output } from '@angular/core';
import { FormArray, FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';

import { BoxDesign } from '../../../../api/models/box-design';
import { BoxDesignDefaults } from '../../../../api/models/box-design-defaults';
import { BoxDesignRequest } from '../../../../api/models/box-design-request';
import { BoxTypeIn } from '../../../../api/models/box-type-in';
import { BoxFileFormat } from './box-design-store';

/** Last values entered, so box types are not typed again on every project (this browser only). */
export const STORAGE_KEY = 'opticore.box-design';

type BoxTypeForm = FormGroup<{
  name: FormControl<string>;
  capacity: FormControl<number | null>;
}>;

function boxTypeForm(t?: BoxTypeIn): BoxTypeForm {
  return new FormGroup({
    name: new FormControl(t?.name ?? '', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(50), Validators.pattern(/\S/)],
    }),
    capacity: new FormControl<number | null>(t?.capacity ?? null, [
      Validators.required,
      Validators.min(1),
      Validators.max(10000),
    ]),
  });
}

function remembered(): BoxDesignRequest | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as BoxDesignRequest) : null;
  } catch {
    return null;
  }
}

/** Form for box types / drop limit / spare, and the summary of the last design. */
@Component({
  selector: 'app-box-design-panel',
  imports: [ReactiveFormsModule, DecimalPipe],
  templateUrl: './box-design-panel.html',
})
export class BoxDesignPanel {
  readonly defaults = input<BoxDesignDefaults | undefined>(undefined);
  readonly design = input<BoxDesign | null>(null);
  readonly busy = input(false);
  readonly error = input<string | null>(null);
  /** Why a design cannot run yet (no drawing / no survey users), or null when it can. */
  readonly blocked = input<string | null>(null);
  readonly hasBoundary = input(false);

  readonly run = output<BoxDesignRequest>();
  readonly download = output<{ request: BoxDesignRequest; format: BoxFileFormat }>();

  protected readonly form = new FormGroup({
    types: new FormArray<BoxTypeForm>([]),
    maxDrop: new FormControl<number | null>(null, [Validators.min(0.1), Validators.max(5000)]),
    spare: new FormControl<number | null>(null, [Validators.min(0), Validators.max(99)]),
    includeOutside: new FormControl(false, { nonNullable: true }),
  });

  private filled = false;

  constructor() {
    // Fill once: last values entered in this browser, else the rules file, else one empty row.
    effect(() => {
      const defaults = this.defaults();
      const last = remembered();
      if (this.filled || (!defaults && !last)) {
        return;
      }
      this.filled = true;
      const source = last ?? {
        box_types: defaults?.box_types ?? [],
        max_drop_m: defaults?.max_drop_m ?? null,
        spare_percent: defaults?.spare_percent ?? 0,
        include_outside: false,
      };
      this.setValues(source);
    });
    if (remembered() === null) {
      this.addType();
    }
  }

  protected get types(): FormArray<BoxTypeForm> {
    return this.form.controls.types;
  }

  protected addType(): void {
    this.types.push(boxTypeForm());
  }

  protected removeType(index: number): void {
    this.types.removeAt(index);
    if (this.types.length === 0) {
      this.addType();
    }
  }

  protected submit(kind: 'run' | BoxFileFormat): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const request = this.request();
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(request));
    } catch {
      // storage blocked: the values are simply not remembered
    }
    if (kind === 'run') {
      this.run.emit(request);
    } else {
      this.download.emit({ request, format: kind });
    }
  }

  protected listed(ids: readonly string[]): string {
    const shown = ids.slice(0, 30).join(', ');
    return ids.length > 30 ? `${shown} … and ${ids.length - 30} more` : shown;
  }

  private request(): BoxDesignRequest {
    const v = this.form.getRawValue();
    return {
      box_types: v.types.map((t) => ({ name: t.name.trim(), capacity: t.capacity ?? 0 })),
      max_drop_m: v.maxDrop,
      spare_percent: v.spare ?? 0,
      include_outside: v.includeOutside,
    };
  }

  private setValues(r: BoxDesignRequest): void {
    this.types.clear();
    for (const t of r.box_types) {
      this.types.push(boxTypeForm(t));
    }
    if (this.types.length === 0) {
      this.addType();
    }
    this.form.patchValue({
      maxDrop: r.max_drop_m ?? null,
      spare: r.spare_percent ?? null,
      includeOutside: r.include_outside ?? false,
    });
  }
}
