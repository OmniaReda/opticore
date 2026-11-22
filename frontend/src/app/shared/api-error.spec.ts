import { HttpErrorResponse } from '@angular/common/http';

import { apiErrorMessage } from './api-error';

describe('apiErrorMessage', () => {
  it('uses the FastAPI detail string', () => {
    const err = new HttpErrorResponse({ status: 404, error: { detail: 'Project not found' } });
    expect(apiErrorMessage(err)).toBe('Project not found');
  });

  it('joins FastAPI validation errors', () => {
    const err = new HttpErrorResponse({
      status: 422,
      error: { detail: [{ loc: ['body', 'name'], msg: 'Field required' }] },
    });
    expect(apiErrorMessage(err)).toBe('name: Field required');
  });

  it('explains when the API cannot be reached', () => {
    expect(apiErrorMessage(new HttpErrorResponse({ status: 0 }))).toContain('Cannot reach the API');
  });

  it('unwraps errors wrapped by resources', () => {
    const cause = new HttpErrorResponse({ status: 409, error: { detail: 'Already processing' } });
    expect(apiErrorMessage(new Error('wrapped', { cause }))).toBe('Already processing');
  });

  it('falls back for unknown errors', () => {
    expect(apiErrorMessage('boom')).toBe('Unexpected error.');
    expect(apiErrorMessage(new HttpErrorResponse({ status: 500, error: 'x' }))).toBe(
      'Request failed (500).',
    );
  });
});
