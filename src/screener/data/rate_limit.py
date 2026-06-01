"""Shared networking policy: a cached HTTP session + a retry/backoff decorator.

Every live fetch goes through here so the rate-limit behaviour lives in exactly
one place. On a scheduled runner the IP *will* get throttled by Yahoo; the goal
is to degrade gracefully (return empty / raise a caught error) rather than crash.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, TypeVar

log = logging.getLogger("screener.rate_limit")

T = TypeVar("T")

# A sentinel exception type so callers can distinguish "throttled / unavailable"
# from genuine logic errors and degrade gracefully.
class DataUnavailable(Exception):
    pass


_SESSION = None


def get_session(cache_path: str | Path = "data/cache/http_cache"):
    """Return a process-wide requests-cache session, if requests-cache is present.

    Falls back to a plain requests session, and to None if requests itself is
    unavailable (tests / offline). Callers must tolerate None.
    """
    global _SESSION
    if _SESSION is not None:
        return _SESSION
    try:
        import requests_cache  # type: ignore

        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        _SESSION = requests_cache.CachedSession(
            str(cache_path),
            expire_after=60 * 60 * 6,  # 6h — prices fetched incrementally anyway
            allowable_codes=(200,),
            stale_if_error=True,
        )
    except Exception:  # pragma: no cover - environment dependent
        try:
            import requests  # type: ignore

            _SESSION = requests.Session()
        except Exception:
            _SESSION = None
    return _SESSION


def with_backoff(fn: Callable[..., T]) -> Callable[..., T]:
    """Decorator: exponential backoff via tenacity if available, else passthrough.

    Caught/raised failures surface as DataUnavailable so the pipeline can skip a
    single bad ticker without aborting the whole run.
    """
    try:
        from tenacity import (  # type: ignore
            retry,
            stop_after_attempt,
            wait_exponential,
            retry_if_exception_type,
        )

        wrapped = retry(
            reraise=True,
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type((DataUnavailable, ConnectionError, TimeoutError)),
        )(fn)
        return wrapped
    except Exception:  # tenacity not installed
        return fn
