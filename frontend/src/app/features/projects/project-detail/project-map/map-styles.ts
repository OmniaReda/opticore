import { FeatureLike } from 'ol/Feature';
import { Circle, Fill, Stroke, Style } from 'ol/style';

import { BuildingRead } from '../../../../api/models/building-read';
import { SurveyRecordRead } from '../../../../api/models/survey-record-read';
import {
  BUILDING_REVIEW_COLOR,
  BUILDING_REVIEW_LABEL,
  BuildingReviewKey,
} from '../../../../shared/labels';

export const BOUNDARY_STYLE = new Style({
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

/** Imported KML features: points red, lines grey. */
export function featureStyle(feature: FeatureLike): Style {
  return feature.getGeometry()?.getType() === 'Point' ? POINT_STYLE : LINE_STYLE;
}

const ORPHAN_STYLE = new Style({
  image: new Circle({
    radius: 5,
    fill: new Fill({ color: BUILDING_REVIEW_COLOR.orphan }),
    stroke: new Stroke({ color: '#fff', width: 1.5 }),
  }),
});
const buildingStyles = new Map<string, Style>();

/** Building colour by review status; dashed outline when not fully inside the project boundary.
 *  Returns undefined (not drawn, not hoverable) for statuses that are switched off. */
export function buildingStyle(
  feature: FeatureLike,
  visible: ReadonlySet<BuildingReviewKey>,
): Style | undefined {
  const key = feature.get('review') as BuildingReviewKey;
  if (!visible.has(key)) {
    return undefined;
  }
  if (key === 'orphan') {
    return ORPHAN_STYLE;
  }
  const position: unknown = feature.get('position');
  const dashed = position === 'crossing' || position === 'outside';
  const cacheKey = `${key}|${dashed}`;
  let style = buildingStyles.get(cacheKey);
  if (!style) {
    const color = BUILDING_REVIEW_COLOR[key];
    style = new Style({
      stroke: new Stroke({ color, width: 1.5, lineDash: dashed ? [4, 3] : undefined }),
      fill: new Fill({ color: `${color}40` }),
    });
    buildingStyles.set(cacheKey, style);
  }
  return style;
}

const POSITION_TEXT: Partial<Record<string, string>> = {
  crossing: ' · crosses the boundary',
  outside: ' · outside the boundary',
};

/** Survey part of the tooltip: users (summed over the building's IDs) and floors of a single ID. */
function surveyText(
  codes: readonly string[],
  survey: ReadonlyMap<string, SurveyRecordRead>,
): string {
  const rows = codes.map((c) => survey.get(c)).filter((r) => r !== undefined);
  if (rows.length === 0) {
    return '';
  }
  const users = rows.reduce((sum, r) => sum + (r.total_users ?? 0), 0);
  const floors =
    rows.length === 1 && rows[0].floors !== null ? `, ${rows[0].floors} floors + GF` : '';
  return ` · ${users} users${floors}`;
}

export function buildingTooltip(
  b: BuildingRead,
  survey: ReadonlyMap<string, SurveyRecordRead> = new Map(),
): string {
  const ids = b.codes.length ? `ID ${b.codes.join(', ')}` : 'No ID';
  const position = b.boundary_position ? (POSITION_TEXT[b.boundary_position] ?? '') : '';
  const status = BUILDING_REVIEW_LABEL[b.status];
  return `${ids} · ${Math.round(b.area_m2)} m² · ${status}${surveyText(b.codes, survey)}${position}`;
}
