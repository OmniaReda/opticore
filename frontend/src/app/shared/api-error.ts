import { HttpErrorResponse } from '@angular/common/http';

interface FastApiValidationItem {
  loc: (string | number)[];
  msg: string;
}

function isValidationList(detail: unknown): detail is FastApiValidationItem[] {
  return (
    Array.isArray(detail) && detail.every((d) => typeof d === 'object' && d !== null && 'msg' in d)
  );
}

/** Resources wrap non-Error failures (like HttpErrorResponse) in an Error whose `cause` is the original. */
function unwrap(err: unknown): unknown {
  return err instanceof Error && err.cause instanceof HttpErrorResponse ? err.cause : err;
}

/** Turns a FastAPI error response into one readable line. */
export function apiErrorMessage(error: unknown): string {
  const err = unwrap(error);
  if (!(err instanceof HttpErrorResponse)) {
    return 'Unexpected error.';
  }
  if (err.status === 0) {
    return 'Cannot reach the API. Is the backend running on :8000?';
  }
  const body: unknown = err.error;
  const detail =
    typeof body === 'object' && body !== null && 'detail' in body ? body.detail : undefined;
  if (typeof detail === 'string') {
    return detail;
  }
  if (isValidationList(detail)) {
    return detail.map((d) => `${d.loc.slice(1).join('.')}: ${d.msg}`).join('; ');
  }
  return `Request failed (${err.status}).`;
}
