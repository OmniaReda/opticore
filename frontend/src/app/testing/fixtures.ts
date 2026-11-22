/** SAMPLE API objects for unit tests — not real project data. */
import { BuildingLayer } from '../api/models/building-layer';
import { ProjectFileRead } from '../api/models/project-file-read';
import { ProjectLayers } from '../api/models/project-layers';
import { ProjectRead } from '../api/models/project-read';
import { SurveyLayer } from '../api/models/survey-layer';
import { SurveyRecordRead } from '../api/models/survey-record-read';

export const PROJECT_ID = '00000000-0000-4000-8000-000000000001';

export function sampleProject(overrides: Partial<ProjectRead> = {}): ProjectRead {
  return {
    id: PROJECT_ID,
    name: 'مشروع تجريبي',
    description: null,
    status: 'draft',
    file_count: 0,
    has_boundary: false,
    created_at: '2026-01-01T10:00:00Z',
    updated_at: '2026-01-01T10:00:00Z',
    ...overrides,
  };
}

export function sampleFile(overrides: Partial<ProjectFileRead> = {}): ProjectFileRead {
  return {
    id: '00000000-0000-4000-8000-0000000000f1',
    project_id: PROJECT_ID,
    kind: 'dxf',
    original_filename: 'drawing.dxf',
    size_bytes: 2048,
    sha256: 'a'.repeat(64),
    status: 'processed',
    error: null,
    note: null,
    uploaded_at: '2026-01-01T10:00:00Z',
    ...overrides,
  };
}

export const EMPTY_LAYERS: ProjectLayers = { boundary: null, features: [] };

export function sampleBuildings(overrides: Partial<BuildingLayer> = {}): BuildingLayer {
  return {
    source_file_id: null,
    provisional: true,
    summary: {
      total: 6,
      ok: 4,
      multiple_ids: 1,
      no_id: 1,
      orphan_ids: 1,
      inside: 4,
      crossing: 1,
      outside: 1,
    },
    buildings: [],
    orphan_labels: [],
    ...overrides,
  };
}

export function sampleSurveyRecord(overrides: Partial<SurveyRecordRead> = {}): SurveyRecordRead {
  return {
    id: '00000000-0000-4000-8000-0000000000a1',
    row_number: 2,
    code: '1',
    in_drawing: true,
    visit_date: null,
    street_name: 'شارع تجريبي',
    building_name: null,
    building_number: null,
    latitude: 30.1,
    longitude: 31.3,
    floors: 4,
    users_per_floor: 2,
    gf_users: 2,
    total_users: 10,
    hp_te_required: null,
    comments: null,
    sub_category: null,
    final_category: null,
    placemark_id: null,
    entrance_length_m: null,
    entrance_marked: null,
    msan_note: null,
    void_core: null,
    hp_count: null,
    qty_home_pass: null,
    te_comment: null,
    ...overrides,
  };
}

export function sampleSurvey(overrides: Partial<SurveyLayer> = {}): SurveyLayer {
  return {
    source_file_id: null,
    provisional: true,
    has_drawing: true,
    summary: {
      rows: 6,
      in_drawing: 5,
      not_in_drawing: 1,
      drawing_ids_without_survey: 2,
      missing_gps: 2,
      total_users: 20,
    },
    records: [sampleSurveyRecord()],
    not_in_drawing: ['7'],
    drawing_ids_without_survey: ['2', '9'],
    ...overrides,
  };
}
