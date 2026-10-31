"""Polite fetcher for official sources only.

Honours robots.txt, identifies itself, rate-limits, stores a snapshot with SHA-256.
It does NOT parse the scheme catalogue: that needs the real DOM, which portal_validation.md
lists as unverified (item 1). Implement CatalogueParser only after a human has inspected the pages.
"""
from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from ..config import settings

_last_fetch: dict[str, float] = {}


class SourceNotAllowed(Exception):
    pass


def is_official(url: str) -> bool:
    p = urlparse(url)
    host = (p.hostname or "").lower()
    return p.scheme == "https" and any(host == s or host.endswith("." + s) for s in settings.official_host_suffixes)


def _robots_allows(url: str) -> bool:
    p = urlparse(url)
    rp = RobotFileParser()
    try:
        r = httpx.get(f"{p.scheme}://{p.netloc}/robots.txt", timeout=10,
                      headers={"User-Agent": settings.fetch_user_agent})
        if r.status_code >= 400:
            return True  # no robots file published
        rp.parse(r.text.splitlines())
    except httpx.HTTPError:
        return False  # cannot confirm permission: do not fetch
    return rp.can_fetch(settings.fetch_user_agent, url)


def html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", "\n", html)
    return "\n".join(l.strip() for l in text.splitlines() if l.strip())


def fetch_official(url: str) -> dict:
    if not is_official(url):
        raise SourceNotAllowed(f"{url} is not an allowed official https source")
    if not _robots_allows(url):
        raise SourceNotAllowed(f"robots.txt does not permit fetching {url}")
    host = urlparse(url).hostname or ""
    wait = settings.fetch_min_interval_seconds - (time.time() - _last_fetch.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    r = httpx.get(url, timeout=30, follow_redirects=True, headers={"User-Agent": settings.fetch_user_agent})
    _last_fetch[host] = time.time()
    text = html_to_text(r.text) if "html" in r.headers.get("content-type", "") else ""
    return {
        "url": str(r.url), "http_status": r.status_code, "retrieved_at": datetime.now(timezone.utc),
        "sha256": hashlib.sha256(r.content).hexdigest(), "content_text": text,
    }
