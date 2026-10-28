"""Write-side business logic."""

import hashlib
import logging

from django.core.cache import cache

from .models import Location, LocationView

logger = logging.getLogger(__name__)

VIEW_DEDUP_TTL = 60 * 60  # one counted view per viewer per hour


def _viewer_id(request) -> str:
    if request.user.is_authenticated:
        return f"u:{request.user.pk}"
    # Anonymous: hash of IP + User-Agent. Session keys are useless here:
    # cookie-less clients would get a new session (and a new view) per request.
    # REMOTE_ADDR only: X-Forwarded-For is client-controlled without a trusted proxy.
    ip = request.META.get("REMOTE_ADDR", "")
    ua = request.META.get("HTTP_USER_AGENT", "")
    return "a:" + hashlib.sha256(f"{ip}|{ua}".encode()).hexdigest()[:32]


def register_view(request, location: Location) -> bool:
    """
    Counts a view at most once per viewer per hour. Returns True if counted.

    cache.add() maps to Redis `SET key 1 NX EX 3600`: atomic, so two parallel
    requests from the same viewer can't both pass the check.
    """
    key = f"locview:{location.pk}:{_viewer_id(request)}"
    try:
        if not cache.add(key, 1, timeout=VIEW_DEDUP_TTL):
            return False
    except Exception:  # Redis down: don't break the detail page, just skip counting
        logger.exception("View de-duplication unavailable, view not counted")
        return False

    LocationView.objects.create(
        location=location,
        user=request.user if request.user.is_authenticated else None,
    )
    return True
