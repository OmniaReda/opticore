import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  effect,
  input,
  signal,
  viewChild,
} from '@angular/core';
import OlFeature, { FeatureLike } from 'ol/Feature';
import OlMap from 'ol/Map';
import View from 'ol/View';
import { defaults as defaultControls, ScaleLine } from 'ol/control';
import { createEmpty, extend, isEmpty } from 'ol/extent';
import GeoJSON from 'ol/format/GeoJSON';
import { Geometry } from 'ol/geom';
import TileLayer from 'ol/layer/Tile';
import VectorLayer from 'ol/layer/Vector';
import OSM from 'ol/source/OSM';
import VectorSource from 'ol/source/Vector';
import { Circle, Fill, Stroke, Style } from 'ol/style';

import { BuildingLayer } from '../../api/models/building-layer';
import { BuildingRead } from '../../api/models/building-read';
import { GeoJsonGeometry } from '../../api/models/geo-json-geometry';
import { ProjectLayers } from '../../api/models/project-layers';
import { BUILDING_REVIEW_COLOR, BUILDING_REVIEW_LABEL, BuildingReviewKey } from '../../shared/labels';

const geojson = new GeoJSON({ dataProjection: 'EPSG:4326', featureProjection: 'EPSG:3857' });

const BOUNDARY_STYLE = new Style({
  stroke: new Stroke({ color: '#0d6efd', width: 3 }),
  fill: new Fill({ color: 'rgba(13, 110, 253, 0.08)' }),
});
const POINT_STYLE = new Style({
  image: new Circle({
    radius: 6,
    fill: new Fill({ color: '#dc3545' }),
    stroke: new Stroke({ color: '#fff', width: 2 }),
  }),
});
const LINE_STYLE = new Style({ stroke: new Stroke({ color: '#6c757d', width: 1.5 }) });

/** Building fill/outline by review status; dashed outline when the building is not fully inside the boundary. */
function buildingStyle(key: BuildingReviewKey, dashed: boolean): Style {
  const color = BUILDING_REVIEW_COLOR[key];
  return new Style({
    stroke: new Stroke({ color, width: 1.5, lineDash: dashed ? [4, 3] : undefined }),
    fill: new Fill({ color: `${color}40` }),
  });
}
const BUILDING_STYLES = new Map<string, Style>();
const ORPHAN_STYLE = new Style({
  image: new Circle({
    radius: 5,
    fill: new Fill({ color: BUILDING_REVIEW_COLOR.orphan }),
    stroke: new Stroke({ color: '#fff', width: 1.5 }),
  }),
});

function toOl(geometry: GeoJsonGeometry, name: string | null): OlFeature<Geometry> {
  return new OlFeature({ geometry: geojson.readGeometry(geometry) ?? undefined, name });
}

const POSITION_TEXT: Record<string, string> = { crossing: ' · crosses the boundary', outside: ' · outside the boundary' };

function buildingTooltip(b: BuildingRead): string {
  const ids = b.codes.length ? `ID ${b.codes.join(', ')}` : 'No ID';
  const position = b.boundary_position ? (POSITION_TEXT[b.boundary_position] ?? '') : '';
  return `${ids} · ${Math.round(b.area_m2)} m² · ${BUILDING_REVIEW_LABEL[b.status]}${position}`;
}

/** Project map: OSM base map + boundary + imported features + buildings, with a tooltip on hover. */
@Component({
  selector: 'app-project-map',
  template: `
    <div class="position-relative">
      <div #map class="project-map"></div>
      @if (hoverName(); as name) {
        <div class="map-tooltip shadow-sm" dir="auto">{{ name }}</div>
      }
      @if (isEmptyMap()) {
        <div class="map-empty text-muted">No boundary yet — upload the project KML/KMZ.</div>
      }
    </div>
  `,
  styles: `
    .project-map { height: 520px; width: 100%; }
    .map-tooltip {
      position: absolute; top: .5rem; left: 50%; transform: translateX(-50%);
      background: var(--bs-body-bg); border-radius: .375rem; padding: .25rem .6rem; font-size: .875rem;
      max-width: 90%; pointer-events: none;
    }
    .map-empty {
      position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
      background: rgba(255, 255, 255, .6); pointer-events: none;
    }
  `,
})
export class ProjectMapComponent implements AfterViewInit, OnDestroy {
  readonly layers = input<ProjectLayers | null>(null);
  readonly buildings = input<BuildingLayer | null>(null);
  /** Review categories to draw; the others are hidden. */
  readonly visible = input<ReadonlySet<BuildingReviewKey>>(new Set(['ok', 'multiple_ids', 'no_id', 'orphan']));

  readonly hoverName = signal<string | null>(null);
  readonly isEmptyMap = signal(true);

  private readonly mapEl = viewChild.required<ElementRef<HTMLDivElement>>('map');
  private readonly boundarySource = new VectorSource<OlFeature<Geometry>>();
  private readonly featureSource = new VectorSource<OlFeature<Geometry>>();
  private readonly buildingSource = new VectorSource<OlFeature<Geometry>>();
  private buildingLayer?: VectorLayer<VectorSource<OlFeature<Geometry>>>;
  private map?: OlMap;
  private fittedKey: string | null = null;

  constructor() {
    effect(() => this.render(this.layers(), this.buildings()));
    effect(() => {
      this.visible();
      this.buildingLayer?.changed(); // re-run the style function
    });
  }

  ngAfterViewInit(): void {
    this.buildingLayer = new VectorLayer({
      source: this.buildingSource,
      style: (f) => this.styleBuilding(f),
    });
    this.map = new OlMap({
      target: this.mapEl().nativeElement,
      controls: defaultControls().extend([new ScaleLine()]),
      layers: [
        new TileLayer({ source: new OSM() }),
        new VectorLayer({ source: this.boundarySource, style: BOUNDARY_STYLE }),
        this.buildingLayer,
        new VectorLayer({
          source: this.featureSource,
          style: (f) => (f.getGeometry()?.getType() === 'Point' ? POINT_STYLE : LINE_STYLE),
        }),
      ],
      view: new View({ center: [0, 0], zoom: 2 }),
    });
    this.map.on('pointermove', (e) => {
      const hit = this.map?.forEachFeatureAtPixel(e.pixel, (f) => f, { hitTolerance: 4 });
      const name: unknown = hit?.get('name');
      this.hoverName.set(typeof name === 'string' ? name : null);
    });
    this.render(this.layers(), this.buildings());
  }

  ngOnDestroy(): void {
    this.map?.setTarget(undefined);
  }

  private styleBuilding(f: FeatureLike): Style | undefined {
    const key = f.get('review') as BuildingReviewKey;
    if (!this.visible().has(key)) {
      return undefined; // hidden (also not hit by hover)
    }
    if (key === 'orphan') {
      return ORPHAN_STYLE;
    }
    const dashed = f.get('position') === 'crossing' || f.get('position') === 'outside';
    const cacheKey = `${key}|${dashed}`;
    let style = BUILDING_STYLES.get(cacheKey);
    if (!style) {
      style = buildingStyle(key, dashed);
      BUILDING_STYLES.set(cacheKey, style);
    }
    return style;
  }

  private render(layers: ProjectLayers | null, buildings: BuildingLayer | null): void {
    if (!this.map) {
      return; // first render happens in ngAfterViewInit
    }
    this.boundarySource.clear();
    this.featureSource.clear();
    this.buildingSource.clear();
    if (layers?.boundary) {
      this.boundarySource.addFeature(toOl(layers.boundary.geometry, null));
    }
    this.featureSource.addFeatures((layers?.features ?? []).map((f) => toOl(f.geometry, f.name)));
    for (const b of buildings?.buildings ?? []) {
      const f = toOl(b.geometry, buildingTooltip(b));
      f.setProperties({ review: b.status, position: b.boundary_position });
      this.buildingSource.addFeature(f);
    }
    for (const o of buildings?.orphan_labels ?? []) {
      const f = toOl(o.geometry, `ID ${o.code} · not inside any building`);
      f.set('review', 'orphan');
      this.buildingSource.addFeature(f);
    }

    const extent = createEmpty();
    for (const source of [this.boundarySource, this.featureSource, this.buildingSource]) {
      const sourceExtent = source.getExtent();
      if (sourceExtent && !isEmpty(sourceExtent)) {
        extend(extent, sourceExtent);
      }
    }
    this.isEmptyMap.set(isEmpty(extent));
    // Zoom to the data only when it changes (not on every refresh, so the user's pan/zoom is kept).
    const key = [
      layers?.boundary?.source_file_id ?? '',
      layers?.features.length ?? 0,
      buildings?.source_file_id ?? '',
    ].join('|');
    if (!isEmpty(extent) && key !== this.fittedKey) {
      this.map.getView().fit(extent, { padding: [40, 40, 40, 40], maxZoom: 18 });
      this.fittedKey = key;
    }
  }
}
