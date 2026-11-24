import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { rxResource, takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { BoxDesign } from '../../../../api/models/box-design';
import { BoxDesignRequest } from '../../../../api/models/box-design-request';
import { NetworkBoxesService } from '../../../../api/services/network-boxes.service';
import { apiErrorMessage } from '../../../../shared/api-error';
import { saveBlob } from '../../../../shared/save-blob';

export type BoxFileFormat = 'xlsx' | 'dxf';

/** Network Box design of one project page: form defaults, last result, Excel download. */
@Injectable()
export class BoxDesignStore {
  private readonly api = inject(NetworkBoxesService);
  private readonly destroyRef = inject(DestroyRef);

  /** Values from backend/app/rules/network_boxes.yaml (empty until the Design Team confirms them). */
  readonly defaults = rxResource({ stream: () => this.api.getBoxDefaults() });

  readonly design = signal<BoxDesign | null>(null);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);

  run(projectId: string, request: BoxDesignRequest): void {
    this.start();
    this.api
      .designBoxes({ project_id: projectId, body: request })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (design) => {
          this.design.set(design);
          this.busy.set(false);
        },
        error: (err: unknown) => this.fail(err),
      });
  }

  /** Excel (boxes, buildings, settings) or AutoCAD (boxes and drop lines over the street map). */
  download(projectId: string, request: BoxDesignRequest, format: BoxFileFormat = 'xlsx'): void {
    this.start();
    const params = { project_id: projectId, body: request };
    const file$ =
      format === 'xlsx'
        ? this.api.exportBoxDesign$Response(params)
        : this.api.exportBoxDesignDxf$Response(params);
    file$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (response) => {
        saveBlob(response.body as Blob, `network-boxes.${format}`);
        this.busy.set(false);
      },
      error: (err: unknown) => this.fail(err),
    });
  }

  /** The drawing or survey changed: the last design no longer matches it. */
  clear(): void {
    this.design.set(null);
    this.error.set(null);
  }

  private start(): void {
    this.busy.set(true);
    this.error.set(null);
  }

  private fail(err: unknown): void {
    this.error.set(apiErrorMessage(err));
    this.busy.set(false);
  }
}
