from __future__ import annotations

from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from rapidfuzz import fuzz

from .fetch import RawItem

TITLE_SIM_THRESHOLD = 0.85


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    # strip tracking params
    keep_params = {k: v for k, v in parse_qs(parsed.query).items()
                   if not k.startswith(("utm_", "ref", "fbclid"))}
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        query=urlencode(keep_params, doseq=True),
        fragment="",
    )
    return urlunparse(normalized)


def deduplicate(items: list[RawItem]) -> list[RawItem]:
    # pass 1: URL dedup
    seen_urls: dict[str, RawItem] = {}
    url_deduped: list[RawItem] = []
    for item in items:
        norm = _normalize_url(item.url)
        if norm in seen_urls:
            # merge source into existing
            existing = seen_urls[norm]
            if item.source_id not in (existing.source_id or "").split(","):
                existing.source_id = f"{existing.source_id},{item.source_id}"
        else:
            seen_urls[norm] = item
            url_deduped.append(item)

    # pass 2: title fuzzy dedup
    result: list[RawItem] = []
    for item in url_deduped:
        duplicate = False
        for kept in result:
            if not item.title or not kept.title:
                continue
            sim = fuzz.ratio(item.title, kept.title) / 100.0
            if sim >= TITLE_SIM_THRESHOLD:
                # merge source
                if item.source_id not in kept.source_id:
                    kept.source_id = f"{kept.source_id},{item.source_id}"
                duplicate = True
                break
        if not duplicate:
            result.append(item)

    return result
