import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { provideApiConfiguration } from '../../../api/api-configuration';
import { ProjectFileRead } from '../../../api/models/project-file-read';
import {
  EMPTY_LAYERS,
  PROJECT_ID,
  sampleBuildings,
  sampleFile,
  sampleProject,
  sampleSurvey,
} from '../../../testing/fixtures';
import { POLL_MS, ProjectDetailStore } from './project-detail-store';

const BASE = `/api/projects/${PROJECT_ID}`;

describe('ProjectDetailStore', () => {
  let store: ProjectDetailStore;
  let http: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      providers: [
        ProjectDetailStore,
        provideHttpClient(),
        provideHttpClientTesting(),
        provideApiConfiguration('/api'),
      ],
    });
    store = TestBed.inject(ProjectDetailStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    vi.useRealTimers();
  });

  /** Lets the resource and effects settle (resource values arrive in a microtask). */
  async function settle(): Promise<void> {
    await vi.advanceTimersByTimeAsync(0);
    TestBed.tick();
  }

  /** Answers the five requests of one page load. */
  async function respond(files: ProjectFileRead[]): Promise<void> {
    await settle();
    http.expectOne(BASE).flush(sampleProject());
    http.expectOne(`${BASE}/files`).flush(files);
    http.expectOne(`${BASE}/layers`).flush(EMPTY_LAYERS);
    http.expectOne(`${BASE}/buildings`).flush(sampleBuildings());
    http.expectOne(`${BASE}/survey`).flush(sampleSurvey());
    await settle();
  }

  it('loads project, files, layers, buildings and survey together', async () => {
    store.load(PROJECT_ID);
    await respond([sampleFile()]);
    expect(store.project()?.name).toBe('مشروع تجريبي');
    expect(store.files()).toHaveLength(1);
    expect(store.buildings()?.summary.total).toBe(6);
    expect(store.surveyByCode().get('1')?.total_users).toBe(10);
    expect(store.error()).toBeNull();
  });

  it('polls while a file is processing, and stops when done', async () => {
    store.load(PROJECT_ID);
    await respond([sampleFile({ status: 'processing' })]);

    await vi.advanceTimersByTimeAsync(POLL_MS);
    await respond([sampleFile({ status: 'processed', note: 'done' })]);
    expect(store.files()[0].note).toBe('done');

    await vi.advanceTimersByTimeAsync(POLL_MS * 3);
    await settle();
    http.expectNone(`${BASE}/files`); // no more polling
  });

  it('shows the API error message when loading fails', async () => {
    store.load(PROJECT_ID);
    await settle();
    http.expectOne(BASE).flush({ detail: 'Project not found' }, { status: 404, statusText: 'NF' });
    // forkJoin cancels the other requests once one fails.
    for (const url of [`${BASE}/files`, `${BASE}/layers`, `${BASE}/buildings`, `${BASE}/survey`]) {
      expect(http.match(url).every((r) => r.cancelled)).toBe(true);
    }
    await settle();
    expect(store.error()).toBe('Project not found');
  });

  it('re-processes a file, then reloads', async () => {
    const file = sampleFile({ status: 'failed' });
    store.load(PROJECT_ID);
    await respond([file]);

    store.reprocess(file);
    const req = http.expectOne(`${BASE}/files/${file.id}/process`);
    expect(req.request.method).toBe('POST');
    req.flush({ ...file, status: 'processing' });
    await respond([{ ...file, status: 'processed' }]);
    expect(store.files()[0].status).toBe('processed');
  });

  it('uploads files one by one and collects per-file errors', async () => {
    store.load(PROJECT_ID);
    await respond([]);

    store.upload([new File(['a'], 'a.kml'), new File(['b'], 'b.exe')]);
    expect(store.uploading()).toBe(true);
    http.expectOne(`${BASE}/files`).flush(sampleFile({ kind: 'kml' }));
    http
      .expectOne(`${BASE}/files`)
      .flush({ detail: 'Unsupported file type' }, { status: 415, statusText: 'Unsupported' });
    await respond([sampleFile({ kind: 'kml' })]);

    expect(store.uploading()).toBe(false);
    expect(store.uploadErrors()).toEqual([{ name: 'b.exe', error: 'Unsupported file type' }]);
  });
});
