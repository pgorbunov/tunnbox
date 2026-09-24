"""Application error hierarchy rendered as JSON `{"detail": str, "code": str}`."""

from __future__ import annotations


class AppError(Exception):
    """Base class for errors that map to an HTTP response."""

    status_code = 400
    code = "bad_request"

    def __init__(self, detail: str | None = None, *, code: str | None = None, headers: dict[str, str] | None = None):
        self.detail = detail or self.__class__.__name__
        if code:
            self.code = code
        self.headers = headers or {}
        super().__init__(self.detail)


class BadRequest(AppError):
    status_code = 400
    code = "bad_request"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"

    def __init__(self, detail: str = "Not authenticated", **kwargs: object) -> None:
        headers = kwargs.pop("headers", None) or {}
        headers.setdefault("WWW-Authenticate", "Bearer")
        super().__init__(detail, headers=headers, **kwargs)  # type: ignore[arg-type]


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"

    def __init__(self, detail: str = "Insufficient permissions", **kwargs: object) -> None:
        super().__init__(detail, **kwargs)  # type: ignore[arg-type]


class NotFound(AppError):
    status_code = 404
    code = "not_found"

    def __init__(self, detail: str = "Not found", **kwargs: object) -> None:
        super().__init__(detail, **kwargs)  # type: ignore[arg-type]


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class Gone(AppError):
    status_code = 410
    code = "gone"


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_error"


class Locked(AppError):
    status_code = 423
    code = "locked"

    def __init__(self, detail: str = "Account temporarily locked", **kwargs: object) -> None:
        super().__init__(detail, **kwargs)  # type: ignore[arg-type]


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, retry_after: int, detail: str = "Too many requests") -> None:
        super().__init__(detail, headers={"Retry-After": str(max(1, retry_after))})


class BackendError(AppError):
    """A WireGuard backend command failed."""

    status_code = 502
    code = "backend_error"
