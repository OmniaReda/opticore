import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { provideApiConfiguration } from '../../../../api/api-configuration';
import { PROJECT_ID, sampleBoxDesign } from '../../../../testing/fixtures';
import { BoxDesignStore } from './box-design-store';

const REQUEST = sampleBoxDesign().request;
const URL = `/api/projects/${PROJECT_ID}/network-boxes/design`;

describe('BoxDesignStore', () => {
  let store: BoxDesignStore;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        BoxDesignStore,
        provideHttpClient(),
        provideHttpClientTesting(),
        provideApiConfiguration('/api'),
      ],
    });
    store = TestBed.inject(BoxDesignStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('keeps the last design', () => {
    store.run(PROJECT_ID, REQUEST);
    expect(store.busy()).toBe(true);
    const req = http.expectOne(URL);
    expect(req.request.body).toEqual(REQUEST);
    req.flush(sampleBoxDesign());
    expect(store.design()?.summary.boxes).toBe(2);
    expect(store.busy()).toBe(false);
    store.clear();
    expect(store.design()).toBeNull();
  });

  it('shows the API error', () => {
    store.run(PROJECT_ID, REQUEST);
    http
      .expectOne(URL)
      .flush({ detail: 'Upload the survey Excel first' }, { status: 409, statusText: 'Conflict' });
    expect(store.error()).toBe('Upload the survey Excel first');
    expect(store.busy()).toBe(false);
  });
});
