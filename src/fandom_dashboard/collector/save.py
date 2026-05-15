from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path

from dateutil import parser as dateparser

from .fetch import RawItem

logger = logging.getLogger(__name__)

DOCS_ROOT = Path("/Users/Shared/kaji/docs")


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:8]


def _parse_date(published: str) -> str:
    if not published:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        return dateparser.parse(published).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _slugify_sources(source_id: str) -> list[str]:
    return [s.strip() for s in source_id.split(",") if s.strip()]


def save_item(
    item: RawItem,
    llm_result: dict,
    fandom_id: str,
    output_dir: Path | None = None,
) -> Path | None:
    if output_dir is None:
        output_dir = DOCS_ROOT / "fandom" / fandom_id / "items"
    output_dir.mkdir(parents=True, exist_ok=True)

    url_hash = _url_hash(item.url)
    date_str = _parse_date(item.published)
    filename = f"{date_str}_{url_hash}.md"
    filepath = output_dir / filename

    if filepath.exists():
        logger.debug("skip existing: %s", filename)
        return None

    sources = _slugify_sources(item.source_id)
    members = llm_result.get("members", ["group"])
    category = llm_result.get("category", "news")
    summary = llm_result.get("summary", "")

    # build frontmatter
    sources_yaml = "\n".join(f"  - {s}" for s in sources)
    members_yaml = "\n".join(f"  - {m}" for m in members)

    title_escaped = item.title.replace('"', '\\"')
    content = f"""---
fandom: {fandom_id}
date: {date_str}
source:
{sources_yaml}
category: {category}
members:
{members_yaml}
title: "{title_escaped}"
url: {item.url}
image: {item.image or ""}
---

"""
    if item.image:
        content += f"![](<{item.image}>)\n\n"

    if summary:
        content += f"{summary}\n\n"

    content += f"[元記事]({item.url})\n"

    filepath.write_text(content, encoding="utf-8")
    logger.info("saved: %s", filename)
    return filepath
