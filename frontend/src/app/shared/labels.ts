import { BuildingStatus } from '../api/models/building-status';
import { FileKind } from '../api/models/file-kind';
import { FileStatus } from '../api/models/file-status';
import { ProjectStatus } from '../api/models/project-status';

export const PROJECT_STATUSES: readonly ProjectStatus[] = ['draft', 'active', 'archived'];

export const PROJECT_STATUS_LABEL: Record<ProjectStatus, string> = {
  draft: 'Draft',
  active: 'Active',
  archived: 'Archived',
};

export const PROJECT_STATUS_BADGE: Record<ProjectStatus, string> = {
  draft: 'text-bg-secondary',
  active: 'text-bg-success',
  archived: 'text-bg-light border',
};

export const FILE_KIND_LABEL: Record<FileKind, string> = {
  kml: 'KML',
  kmz: 'KMZ',
  dxf: 'DXF (CAD)',
  dwg: 'DWG (CAD)',
  survey_xlsx: 'Survey Excel',
  other: 'Other (PDF)',
};

export const FILE_STATUS_LABEL: Record<FileStatus, string> = {
  uploaded: 'Uploaded',
  processing: 'Processing',
  processed: 'Processed',
  failed: 'Failed',
};

export const FILE_STATUS_BADGE: Record<FileStatus, string> = {
  uploaded: 'text-bg-info',
  processing: 'text-bg-warning',
  processed: 'text-bg-success',
  failed: 'text-bg-danger',
};

/** Must match backend/app/storage.py EXTENSION_KIND. */
export const ACCEPTED_FILE_TYPES = '.kml,.kmz,.dxf,.dwg,.xlsx,.pdf';

/** Review status of a building polygon, plus IDs whose label is not inside any building. */
export type BuildingReviewKey = BuildingStatus | 'orphan';

export const BUILDING_REVIEW_KEYS: readonly BuildingReviewKey[] = [
  'ok',
  'multiple_ids',
  'no_id',
  'orphan',
];

export const BUILDING_REVIEW_LABEL: Record<BuildingReviewKey, string> = {
  ok: 'One ID',
  multiple_ids: 'Several IDs',
  no_id: 'No ID',
  orphan: 'ID outside any building',
};

/** Map colours (also used for the legend swatches). */
export const BUILDING_REVIEW_COLOR: Record<BuildingReviewKey, string> = {
  ok: '#198754',
  multiple_ids: '#fd7e14',
  no_id: '#6c757d',
  orphan: '#d63384',
};
