"""
Location list cache with version-based invalidation.

Every cache key embeds the current "list version". Invalidation = bumping the
version (one atomic INCR), so all cached pages / filter combinations become
unreachable at once and simply expire by TTL. No need to find and delete keys
by pattern (KEYS/SCAN is O(N) and racy).
"""

import hashlib
import logging
import time
from urllib.parse import urlencode

from django.core.cache import cache

logger = logging.getLogger(__name__)

VERSION_KEY = "locations:list:version"
LIST_CACHE_TTL = 60 * 5  # also bounds staleness of views_7d/popularity in the list


def _fresh_version() -> int:
    # Time-based seed: if Redis loses the version key (restart, eviction),
    # the new version can't collide with an old one and serve stale pages.
    return time.time_ns()


def get_list_version() -> int:
    version = cache.get(VERSION_KEY)
    if version is None:
        cache.add(VERSION_KEY, _fresh_version(), timeout=None)
        version = cache.get(VERSION_KEY)
    return version


def bump_list_version() -> None:
    try:
        cache.incr(VERSION_KEY)
    except ValueError:  # key missing
        cache.set(VERSION_KEY, _fresh_version(), timeout=None)
    except Exception:
        logger.exception("Failed to invalidate location list cache")


def list_cache_key(request) -> str:
    # Sorted query string: ?a=1&b=2 and ?b=2&a=1 share one entry.
    # Host is included because pagination links are absolute URLs.
    query = urlencode(sorted(request.query_params.lists()), doseq=True)
    raw = f"{request.get_host()}{request.path}?{query}"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"locations:list:v{get_list_version()}:{digest}"
