import {
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  effect,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import OlFeature from 'ol/Feature';
import OlMap from 'ol/Map';
import View from 'ol/View';
import { defaults as defaultControls, ScaleLine } from 'ol/control';
import { createEmpty, extend, isEmpty } from 'ol/extent';
import GeoJSON from 'ol/format/GeoJSON';
import { Geometry, LineString, Point } from 'ol/geom';
import TileLayer from 'ol/layer/Tile';
import VectorLayer from 'ol/layer/Vector';
import OSM from 'ol/source/OSM';
import VectorSource from 'ol/source/Vector';

import { BoxDesign } from '../../../../api/models/box-design';
import { BuildingLayer } from '../../../../api/models/building-layer';
import { GeoJsonGeometry } from '../../../../api/models/geo-json-geometry';
import { ProjectLayers } from '../../../../api/models/project-layers';
import { SurveyRecordRead } from '../../../../api/models/survey-record-read';
import { BUILDING_REVIEW_KEYS, BuildingReviewKey } from '../../../../shared/labels';
import {
  BOUNDARY_STYLE,
  FOCUS_STYLE,
  boxStyle,
  boxTooltip,
  buildingStyle,
  buildingTooltip,
  featureStyle,
} from './map-styles';

const geojson = new GeoJSON({ dataProjection: 'EPSG:4326', featureProjection: 'EPSG:3857' });

function toOl(geometry: GeoJsonGeometry, name: string | null): OlFeature<Geometry> {
  return new OlFeature({ geometry: geojson.readGeometry(geometry) ?? undefined, name });
}

/** Project map: OSM base map + boundary + imported features + buildings, tooltip on hover. */
@Component({
  selector: 'app-project-map',
  template: `
    <div class="position-relative">
      <div #map class="project-map" role="img" aria-label="Project map"></div>
      @if (hoverName(); as name) {
        <div class="map-tooltip shadow-sm" dir="auto">{{ name }}</div>
      }
      @if (isEmptyMap()) {
        <div class="map-empty text-muted">No boundary yet — upload the project KML/KMZ.</div>
      }
    </div>
  `,
  styles: `
    .project-map {
      height: 520px;
      width: 100%;
    }
    .map-tooltip {
      position: absolute;
      top: 0.5rem;
      left: 50%;
      transform: translateX(-50%);
      background: var(--bs-body-bg);
      border-radius: 0.375rem;
      padding: 0.25rem 0.6rem;
      font-size: 0.875rem;
      max-width: 90%;
      pointer-events: none;
    }
    .map-empty {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(255, 255, 255, 0.6);
      pointer-events: none;
    }
  `,
})
export class ProjectMap {
  readonly layers = input<ProjectLayers | null>(null);
  readonly buildings = input<BuildingLayer | null>(null);
  /** Survey row per Building ID, shown in the building tooltip. */
  readonly survey = input<ReadonlyMap<string, SurveyRecordRead>>(new Map());
  /** Review categories to draw; the others are hidden. */
  readonly visible = input<ReadonlySet<BuildingReviewKey>>(new Set(BUILDING_REVIEW_KEYS));
  /** A place to zoom to and mark (e.g. a validation issue). A new object zooms again. */
  readonly focus = input<GeoJsonGeometry | null>(null);
  /** Network Boxes of the last design run, with a line to each building they serve. */
  readonly boxes = input<BoxDesign | null>(null);

  protected readonly hoverName = signal<string | null>(null);
  protected readonly isEmptyMap = signal(true);

  private readonly mapEl = viewChild.required<ElementRef<HTMLDivElement>>('map');
  private readonly boundarySource = new VectorSource<OlFeature<Geometry>>();
  private readonly featureSource = new VectorSource<OlFeature<Geometry>>();
  private readonly buildingSource = new VectorSource<OlFeature<Geometry>>();
  private readonly focusSource = new VectorSource<OlFeature<Geometry>>();
  private readonly boxSource = new VectorSource<OlFeature<Geometry>>();
  private readonly buildingLayer = new VectorLayer({
    source: this.buildingSource,
    style: (f) => buildingStyle(f, this.visible()),
  });
  private readonly map = signal<OlMap | undefined>(undefined);
  private fittedKey: string | null = null;

  constructor() {
    // OpenLayers needs the element in the DOM (and a browser): create it after the first render.
    afterNextRender(() => this.map.set(this.createMap()));
    inject(DestroyRef).onDestroy(() => this.map()?.setTarget(undefined));

    effect(() => {
      const map = this.map();
      if (map) {
        this.render(map, this.layers(), this.buildings(), this.survey());
      }
    });
    effect(() => {
      this.visible();
      this.buildingLayer.changed(); // re-run the style function
    });
    effect(() => {
      if (this.map()) {
        this.showBoxes(this.boxes());
      }
    });
    effect(() => {
      const map = this.map();
      const focus = this.focus();
      if (map) {
        this.showFocus(map, focus);
      }
    });
  }

  private createMap(): OlMap {
    const map = new OlMap({
      target: this.mapEl().nativeElement,
      controls: defaultControls().extend([new ScaleLine()]),
      layers: [
        new TileLayer({ source: new OSM() }),
        new VectorLayer({ source: this.boundarySource, style: BOUNDARY_STYLE }),
        this.buildingLayer,
        new VectorLayer({ source: this.featureSource, style: featureStyle }),
        new VectorLayer({ source: this.boxSource, style: boxStyle }),
        new VectorLayer({ source: this.focusSource, style: FOCUS_STYLE }),
      ],
      view: new View({ center: [0, 0], zoom: 2 }),
    });
    map.on('pointermove', (e) => {
      const hit = map.forEachFeatureAtPixel(e.pixel, (f) => f, { hitTolerance: 4 });
      const name: unknown = hit?.get('name');
      this.hoverName.set(typeof name === 'string' ? name : null);
    });
    return map;
  }

  private showBoxes(design: BoxDesign | null): void {
    this.boxSource.clear();
    for (const box of design?.boxes ?? []) {
      const at = geojson.readGeometry(box.geometry);
      for (const s of box.served) {
        const to = geojson.readGeometry(s.geometry);
        if (s.distance_m > 0 && at instanceof Point && to instanceof Point) {
          const line = new LineString([at.getCoordinates(), to.getCoordinates()]);
          this.boxSource.addFeature(new OlFeature({ geometry: line }));
        }
      }
      this.boxSource.addFeature(toOl(box.geometry, boxTooltip(box)));
    }
  }

  private showFocus(map: OlMap, focus: GeoJsonGeometry | null): void {
    this.focusSource.clear();
    if (!focus) {
      return;
    }
    const feature = toOl(focus, null);
    this.focusSource.addFeature(feature);
    const extent = feature.getGeometry()?.getExtent();
    if (extent) {
      map.getView().fit(extent, { padding: [80, 80, 80, 80], maxZoom: 19, duration: 400 });
    }
  }

  private render(
    map: OlMap,
    layers: ProjectLayers | null,
    buildings: BuildingLayer | null,
    survey: ReadonlyMap<string, SurveyRecordRead>,
  ): void {
    map.updateSize(); // the card may have changed size since the map was created
    this.boundarySource.clear();
    this.featureSource.clear();
    this.buildingSource.clear();
    if (layers?.boundary) {
      this.boundarySource.addFeature(toOl(layers.boundary.geometry, null));
    }
    this.featureSource.addFeatures((layers?.features ?? []).map((f) => toOl(f.geometry, f.name)));
    for (const b of buildings?.buildings ?? []) {
      const f = toOl(b.geometry, buildingTooltip(b, survey));
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
      map.getView().fit(extent, { padding: [40, 40, 40, 40], maxZoom: 18 });
      this.fittedKey = key;
    }
  }
}
