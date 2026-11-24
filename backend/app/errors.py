"""Domain errors. Services raise these; one exception handler turns them into HTTP responses
shaped like FastAPI's own errors ({"detail": "..."}), so routers and services never build HTTP errors."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class: the message is shown to the user as-is."""

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT


class InvalidInputError(AppError):
    """Input that passes the schema but cannot be used (e.g. no usable box capacity)."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class UnsupportedFileTypeError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


class FileTooLargeError(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE


class EmptyFileError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST


class ExternalServiceError(AppError):
    """A service we depend on (e.g. OpenStreetMap) did not answer."""

    status_code = status.HTTP_502_BAD_GATEWAY


def _handle_app_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
