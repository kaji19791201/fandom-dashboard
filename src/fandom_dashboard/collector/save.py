from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path

import requests
from dateutil import parser as dateparser

from .fetch import RawItem

logger = logging.getLogger(__name__)

DOCS_ROOT = Path(os.environ.get("DOCS_ROOT", "/Users/Shared/kaji/docs"))


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:8]


def _parse_date(published: str, url: str = "") -> str:
    if not published:
        logger.warning("no published date, using today: %s", url)
        return datetime.now().strftime("%Y-%m-%d")
    try:
        return dateparser.parse(published).strftime("%Y-%m-%d")
    except Exception:
        logger.warning("unparsable date %r, using today: %s", published, url)
        return datetime.now().strftime("%Y-%m-%d")


def _slugify_sources(source_id: str) -> list[str]:
    return [s.strip() for s in source_id.split(",") if s.strip()]


def _image_ext(url: str) -> str:
    suffix = Path(url.split("?")[0]).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else ".jpg"


def _download_image(url: str, dest: Path) -> bool:
    try:
        import io
        from PIL import Image
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        dest.write_bytes(r.content)
        img = Image.open(io.BytesIO(r.content))
        logger.info("  image: %s %dx%d", dest.name, img.width, img.height)
        return True
    except Exception as e:
        logger.warning("  image download failed %s: %s", url[:80], e)
        return False


def resolve_local_image(item: RawItem, output_dir: Path) -> Path | None:
    """Return local image path if it already exists, otherwise None."""
    if not item.image or not item.save_image:
        return None
    url_hash = _url_hash(item.url)
    date_str = _parse_date(item.published, item.url)
    local_path = output_dir / f"{date_str}_{url_hash}{_image_ext(item.image)}"
    return local_path if local_path.exists() else None


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
    date_str = _parse_date(item.published, item.url)
    filename = f"{date_str}_{url_hash}.md"
    filepath = output_dir / filename

    if filepath.exists():
        logger.debug("skip existing: %s", filename)
        return None

    sources = _slugify_sources(item.source_id)
    members = llm_result.get("members", ["group"])
    category = llm_result.get("category", "news")
    summary = llm_result.get("summary", "")

    # resolve image reference
    image_ref = ""
    image_embed = ""
    if item.image and item.save_image:
        local_name = f"{date_str}_{url_hash}{_image_ext(item.image)}"
        local_path = output_dir / local_name
        if local_path.exists():
            image_ref = local_name
            image_embed = f"![]({local_name})"
        elif _download_image(item.image, local_path):
            image_ref = local_name
            image_embed = f"![]({local_name})"
        else:
            image_ref = item.image
            image_embed = f"![](<{item.image}>)"
    elif item.image:
        # save_image=False: keep URL in frontmatter but don't embed
        image_ref = item.image

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
image: {image_ref}
---

"""
    if image_embed:
        content += f"{image_embed}\n\n"

    if summary:
        content += f"{summary}\n\n"

    content += f"[元記事]({item.url})\n"

    filepath.write_text(content, encoding="utf-8")
    logger.info("saved: %s [%s] %s", filename, item.source_id, item.title[:50])
    return filepath
