"""Shared networking policy: a cached HTTP session + a throttle/backoff decorator.

Every live fetch goes through `with_backoff` so the rate-limit behaviour lives in
exactly one place. On a scheduled runner the IP *will* get throttled by Yahoo, so
we defend proactively:

  * a process-wide minimum delay between network calls (`request_delay_seconds`),
  * a concurrency cap (`max_concurrency`) so we never fan out faster than Yahoo
    tolerates,
  * on a 429 ("Too Many Requests") we wait `rate_limit_backoff_seconds` (default
    60s) before retrying instead of burning through retries immediately.

The throttle is configured once per run via `configure_throttle()` (wired from
`config.yaml`'s `fetch:` section in `pipeline.py`). Defaults are conservative so
even an unconfigured caller behaves politely.
"""
from __future__ import annotations

import functools
import logging
import threading
import time
from pathlib import Path
from typing import Callable, TypeVar

log = logging.getLogger("screener.rate_limit")

T = TypeVar("T")

# A sentinel exception type so callers can distinguish "throttled / unavailable"
# from genuine logic errors and degrade gracefully.
class DataUnavailable(Exception):
    pass


# --- throttle configuration (set once per run via configure_throttle) ---------
_CONFIG = {
    "request_delay_seconds": 0.5,      # min spacing between network calls
    "max_concurrency": 1,              # simultaneous in-flight requests
    "rate_limit_backoff_seconds": 60.0,  # wait this long after a 429 before retry
    "max_attempts": 4,                 # total tries per call before giving up
}

_gate_lock = threading.Lock()
_last_call_ts = 0.0
_semaphore = threading.Semaphore(_CONFIG["max_concurrency"])


def configure_throttle(*, request_delay_seconds=None, max_concurrency=None,
                       rate_limit_backoff_seconds=None, max_attempts=None) -> None:
    """Set the process-wide throttle. None args leave the current value unchanged."""
    global _semaphore
    if request_delay_seconds is not None:
        _CONFIG["request_delay_seconds"] = max(0.0, float(request_delay_seconds))
    if rate_limit_backoff_seconds is not None:
        _CONFIG["rate_limit_backoff_seconds"] = max(0.0, float(rate_limit_backoff_seconds))
    if max_attempts is not None:
        _CONFIG["max_attempts"] = max(1, int(max_attempts))
    if max_concurrency is not None:
        _CONFIG["max_concurrency"] = max(1, int(max_concurrency))
        _semaphore = threading.Semaphore(_CONFIG["max_concurrency"])


def is_rate_limited(exc: BaseException) -> bool:
    """True if an exception looks like a Yahoo rate-limit (HTTP 429)."""
    msg = str(exc).lower()
    return "too many requests" in msg or "rate limit" in msg or "429" in msg


def _gate() -> None:
    """Block until at least `request_delay_seconds` has elapsed since the last
    network call (process-wide), then stamp 'now' as the latest call time."""
    global _last_call_ts
    delay = _CONFIG["request_delay_seconds"]
    if delay <= 0:
        return
    with _gate_lock:
        now = time.monotonic()
        wait = _last_call_ts + delay - now
        if wait > 0:
            time.sleep(wait)
        _last_call_ts = time.monotonic()


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
    """Decorator: throttle each call and retry transient failures.

    Before every attempt we enforce the inter-request delay and acquire the
    concurrency semaphore. On a rate-limit (429) we wait the long backoff;
    other transient errors get a short exponential backoff. After `max_attempts`
    the last exception is re-raised so the caller (cache.py) can serve cache.
    """
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        attempts = _CONFIG["max_attempts"]
        last_exc: BaseException | None = None
        for attempt in range(1, attempts + 1):
            _gate()
            try:
                with _semaphore:
                    return fn(*args, **kwargs)
            except (DataUnavailable, ConnectionError, TimeoutError) as e:
                last_exc = e
                if attempt >= attempts:
                    break
                if is_rate_limited(e):
                    wait = _CONFIG["rate_limit_backoff_seconds"]
                else:
                    wait = min(30.0, 2.0 * (2 ** (attempt - 1)))
                log.warning("retry %d/%d in %.0fs after: %s", attempt, attempts, wait, e)
                time.sleep(wait)
        assert last_exc is not None
        raise last_exc

    return wrapped
