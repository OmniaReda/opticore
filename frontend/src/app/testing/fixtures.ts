/** SAMPLE API objects for unit tests — not real project data. */
import { AddressLayer } from '../api/models/address-layer';
import { BoxDesign } from '../api/models/box-design';
import { BuildingLayer } from '../api/models/building-layer';
import { ProjectFileRead } from '../api/models/project-file-read';
import { ProjectLayers } from '../api/models/project-layers';
import { ProjectRead } from '../api/models/project-read';
import { SurveyLayer } from '../api/models/survey-layer';
import { SurveyRecordRead } from '../api/models/survey-record-read';
import { ValidationReport } from '../api/models/validation-report';

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

export function sampleValidation(overrides: Partial<ValidationReport> = {}): ValidationReport {
  const point = { type: 'Point', coordinates: [31.3, 30.1] };
  return {
    provisional: true,
    gps_max_distance_m: 25,
    has_drawing: true,
    has_survey: true,
    rules: [
      {
        rule: 'id_outside_building',
        severity: 'error',
        title: 'Building ID not inside any building',
        count: 1,
      },
      { rule: 'duplicate_drawing_id', severity: 'error', title: 'Duplicate', count: 0 },
      {
        rule: 'gps_far_from_building',
        severity: 'warning',
        title: 'Survey GPS far from its building',
        count: 2,
      },
      { rule: 'building_without_id', severity: 'info', title: 'Building without ID', count: 1 },
    ],
    issues: [
      {
        rule: 'id_outside_building',
        severity: 'error',
        code: '9',
        row_number: null,
        message: 'ID 9 is outside',
        geometry: point,
      },
      {
        rule: 'gps_far_from_building',
        severity: 'warning',
        code: '3',
        row_number: 4,
        message: 'GPS is 50 m',
        geometry: point,
      },
      {
        rule: 'gps_far_from_building',
        severity: 'warning',
        code: '6',
        row_number: 7,
        message: 'GPS is 233 m',
        geometry: null,
      },
      {
        rule: 'building_without_id',
        severity: 'info',
        code: null,
        row_number: null,
        message: 'Outline of 200 m²',
        geometry: point,
      },
    ],
    ...overrides,
  };
}

/** SAMPLE box design (test box types, not real ones). */
export function sampleBoxDesign(overrides: Partial<BoxDesign> = {}): BoxDesign {
  const at = { type: 'Point', coordinates: [31.2, 30.1] };
  return {
    provisional: true,
    source: 'buildings',
    request: {
      box_types: [{ name: 'Test-16', capacity: 16 }],
      max_drop_m: 50,
      spare_percent: 0,
      include_outside: false,
    },
    summary: {
      boxes: 2,
      by_type: [{ box_type: 'Test-16', capacity: 16, count: 2, users: 18 }],
      users: 18,
      buildings_served: 2,
      longest_drop_m: 0,
      without_users: ['2', '5'],
      without_id: 1,
      outside_skipped: 1,
    },
    boxes: [
      {
        label: 'NB-001',
        box_type: 'Test-16',
        capacity: 16,
        usable: 16,
        users: 10,
        host_codes: ['1'],
        dedicated: false,
        geometry: at,
        served: [{ codes: ['1'], users: 10, distance_m: 0, geometry: at }],
      },
      {
        label: 'NB-002',
        box_type: 'Test-16',
        capacity: 16,
        usable: 16,
        users: 8,
        host_codes: ['3', '3-2'],
        dedicated: false,
        geometry: at,
        served: [{ codes: ['3', '3-2'], users: 8, distance_m: 0, geometry: at }],
      },
    ],
    ...overrides,
  };
}

/** SAMPLE filled Streets & numbers rows (synthetic). */
export function sampleAddresses(overrides: Partial<AddressLayer> = {}): AddressLayer {
  return {
    source_file_id: 'f-addr',
    summary: { rows: 2, total_users: 22, without_users: 1 },
    points: [
      {
        id: 'a1',
        row_number: 2,
        street_ar: 'شارع تجريبي',
        street_en: null,
        house_number: '12',
        floors: 10,
        total_users: 22,
        geometry: { type: 'Point', coordinates: [31.2, 30.1] },
      },
      {
        id: 'a2',
        row_number: 3,
        street_ar: null,
        street_en: 'Test St.',
        house_number: '3',
        floors: 2,
        total_users: null,
        geometry: { type: 'Point', coordinates: [31.2, 30.1] },
      },
    ],
    ...overrides,
  };
}
