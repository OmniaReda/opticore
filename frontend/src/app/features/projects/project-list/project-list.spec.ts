import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { provideApiConfiguration } from '../../../api/api-configuration';
import { sampleProject } from '../../../testing/fixtures';
import { ProjectList } from './project-list';

describe('ProjectList', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        provideApiConfiguration('/api'),
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  async function render(response: object, status = 200): Promise<HTMLElement> {
    const fixture = TestBed.createComponent(ProjectList);
    fixture.detectChanges();
    http
      .expectOne('/api/projects')
      .flush(response, { status, statusText: status === 200 ? 'OK' : 'Error' });
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  it('lists projects with a link to each', async () => {
    const el = await render([sampleProject({ file_count: 3 })]);
    const link = el.querySelector<HTMLAnchorElement>('tbody a');
    expect(link?.textContent).toContain('مشروع تجريبي');
    expect(link?.getAttribute('href')).toBe(`/projects/${sampleProject().id}`);
    expect(el.querySelector('tbody')?.textContent).toContain('3');
  });

  it('shows the empty state', async () => {
    expect((await render([])).textContent).toContain('No projects yet');
  });

  it('shows the API error with a retry button', async () => {
    const el = await render({ detail: 'Database unavailable' }, 503);
    expect(el.querySelector('.alert-danger')?.textContent).toContain('Database unavailable');
    expect(el.textContent).not.toContain('No projects yet');
  });
});
