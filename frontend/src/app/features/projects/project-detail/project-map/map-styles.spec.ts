import { BuildingRead } from '../../../../api/models/building-read';
import { SurveyRecordRead } from '../../../../api/models/survey-record-read';
import { sampleBoxDesign, sampleSurveyRecord } from '../../../../testing/fixtures';
import { boxTooltip, buildingTooltip } from './map-styles';

function building(overrides: Partial<BuildingRead>): BuildingRead {
  return {
    id: 'b1',
    codes: ['1'],
    status: 'ok',
    boundary_position: 'inside',
    area_m2: 120.4,
    geometry: { type: 'Polygon', coordinates: [] },
    ...overrides,
  };
}

describe('buildingTooltip', () => {
  const survey = new Map<string, SurveyRecordRead>([
    ['1', sampleSurveyRecord({ code: '1', total_users: 10, floors: 4 })],
    ['1-2', sampleSurveyRecord({ code: '1-2', total_users: 26, floors: 11 })],
  ]);

  it('describes ID, area and review status', () => {
    expect(buildingTooltip(building({}))).toBe('ID 1 · 120 m² · One ID');
  });

  it('adds survey users and floors of a single ID', () => {
    expect(buildingTooltip(building({}), survey)).toBe(
      'ID 1 · 120 m² · One ID · 10 users, 4 floors + GF',
    );
  });

  it('sums users over several IDs and marks the boundary position', () => {
    const b = building({
      codes: ['1', '1-2'],
      status: 'multiple_ids',
      boundary_position: 'crossing',
    });
    expect(buildingTooltip(b, survey)).toBe(
      'ID 1, 1-2 · 120 m² · Several IDs · 36 users · crosses the boundary',
    );
  });

  it('handles buildings without ID or survey row', () => {
    expect(buildingTooltip(building({ codes: [], status: 'no_id' }), survey)).toBe(
      'No ID · 120 m² · No ID',
    );
  });
});

describe('boxTooltip', () => {
  it('names the box, its type, load and buildings', () => {
    const box = sampleBoxDesign().boxes[1];
    expect(boxTooltip(box)).toBe('NB-002 · Test-16 · 8/16 users · on ID 3, 3-2 · serves 3, 3-2');
  });
});
