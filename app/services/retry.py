from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

_DEFAULT_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
_NON_RETRYABLE_HTTP_CODES = {400, 401, 403, 404, 422}


def retry_with_backoff(
    max_attempts: int = 5,
    base_delay: float = 1.0,
    retryable_codes: set[int] | None = None,
) -> Callable[[F], F]:
    """Exponential backoff decorator for external API calls.

    Retries on network errors and transient HTTP failures (429, 5xx).
    Never retries on auth failures (401/403) or client errors (400/404).
    """
    codes = retryable_codes if retryable_codes is not None else _DEFAULT_RETRYABLE_HTTP_CODES

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except HTTPError as exc:
                    if exc.code in _NON_RETRYABLE_HTTP_CODES:
                        raise
                    if exc.code not in codes:
                        raise
                    last_exc = exc
                    _log_retry(func.__name__, attempt, max_attempts, exc.code, exc)
                except (URLError, OSError, TimeoutError, ConnectionError) as exc:
                    last_exc = exc
                    _log_retry(func.__name__, attempt, max_attempts, None, exc)

                if attempt < max_attempts:
                    delay = base_delay * (2 ** (attempt - 1))
                    time.sleep(delay)

            raise RuntimeError(
                f"{func.__name__} failed after {max_attempts} attempts"
            ) from last_exc

        return wrapper  # type: ignore[return-value]

    return decorator


def _log_retry(
    fn_name: str,
    attempt: int,
    max_attempts: int,
    http_code: int | None,
    exc: Exception,
) -> None:
    code_str = f" HTTP {http_code}" if http_code else ""
    logger.warning(
        "Retry %d/%d for %s after%s error: %s",
        attempt,
        max_attempts,
        fn_name,
        code_str,
        exc,
    )
