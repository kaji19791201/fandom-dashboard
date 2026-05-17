"""Re-summarize saved items that are missing a summary text.

Usage:
  uv run python scripts/backfill_summaries.py            # fill missing summaries
  uv run python scripts/backfill_summaries.py --force    # re-summarize all items
  uv run python scripts/backfill_summaries.py file1 ...  # re-summarize specific files
"""
from __future__ import annotations

import asyncio
import logging
import re
import sys
import time
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fandom_dashboard.collector.fetch import RawItem, _fetch_page_ogp  # noqa: E402
from fandom_dashboard.collector.summarize import summarize  # noqa: E402
from fandom_dashboard.config import FandomConfig  # noqa: E402
from fandom_dashboard.run import _load_llm  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FANDOM_CONFIG_PATH = PROJECT_ROOT / "config" / "fandoms" / "momoclo.yaml"
ITEMS_DIR = Path("/Users/Shared/kaji/docs/fandom/momoclo/items")


def _has_summary(md_path: Path) -> bool:
    text = md_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False
    body = parts[2]
    lines = [
        line for line in body.splitlines()
        if line.strip()
        and not line.strip().startswith("![")
        and not line.strip().startswith("[元記事]")
    ]
    return bool(lines)


def _parse_frontmatter(md_path: Path) -> dict:
    text = md_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    return yaml.safe_load(parts[1]) or {}


def _patch_md(md_path: Path, summary: str, category: str, members: list[str]) -> None:
    """Write (or replace) summary + update category/members in the .md file."""
    text = md_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return

    fm = yaml.safe_load(parts[1]) or {}
    fm["category"] = category
    fm["members"] = members

    fm_keys = ["fandom", "date", "source", "category", "members", "title", "url", "image", "deleted"]
    fm_lines = []
    for k in fm_keys:
        if k not in fm:
            continue
        v = fm[k]
        if isinstance(v, list):
            fm_lines.append(f"{k}:")
            for item in (v or []):
                fm_lines.append(f"  - {item}")
        elif k == "title":
            escaped = str(v).replace('"', '\\"')
            fm_lines.append(f'{k}: "{escaped}"')
        elif isinstance(v, str):
            fm_lines.append(f"{k}: {v}")
        else:
            fm_lines.append(f"{k}: {v}")

    body = parts[2]

    # Remove any existing summary text (lines that are not image/link/blank)
    new_body_lines = []
    skip_blank = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("![") and not stripped.startswith("[元記事]"):
            skip_blank = True
            continue
        if skip_blank and not stripped:
            skip_blank = False
            continue
        new_body_lines.append(line)
    body = "\n".join(new_body_lines)

    # Insert new summary before [元記事]
    if "[元記事]" in body:
        body = re.sub(r"(\[元記事\])", f"\n{summary}\n\n\\1", body, count=1)
    else:
        body = body.rstrip() + f"\n\n{summary}\n\n"

    new_text = "---\n" + "\n".join(fm_lines) + "\n---" + body
    md_path.write_text(new_text, encoding="utf-8")


def _process_file(
    md_path: Path,
    fandom_config: FandomConfig,
    llm,
    ig_member_map: dict[str, str],
    ig_display_map: dict[str, str],
    ig_sources: set[str],
) -> bool:
    fm = _parse_frontmatter(md_path)
    url = fm.get("url", "")
    title = fm.get("title", "")
    source_ids = fm.get("source", [])
    source_id = source_ids[0] if source_ids else ""
    image_ref = fm.get("image", "")

    image_url = ""
    if image_ref and not image_ref.startswith("http"):
        local = ITEMS_DIR / image_ref
        if local.exists():
            image_url = str(local)

    raw_summary = ""
    if source_id not in ig_sources:
        try:
            ogp = asyncio.run(_fetch_page_ogp(url))
            raw_summary = ogp.get("description", "")
            if not title:
                title = ogp.get("title", "")
        except Exception as e:
            logger.warning("OGP fetch failed for %s: %s", url, e)
    elif source_id in ig_display_map:
        raw_summary = f"（投稿者: {ig_display_map[source_id]}）"

    item = RawItem(
        url=url,
        title=title,
        summary=raw_summary,
        published=str(fm.get("date", "")),
        image=image_ref,
        source_id=source_id,
        fandom_id=fandom_config.id,
    )

    members_dicts = [m.model_dump() for m in fandom_config.members]
    result = summarize(item, llm, members_dicts, image_url=image_url)
    if not result.get("summary"):
        logger.warning("No summary generated for %s", md_path.name)
        return False

    if source_id in ig_member_map:
        result["members"] = [ig_member_map[source_id]]

    _patch_md(md_path, result["summary"], result["category"], result["members"])
    logger.info("Updated %s: %s", md_path.name, result["summary"][:60])
    return True


def main():
    args = sys.argv[1:]
    force = "--force" in args
    specific_files = [Path(a) for a in args if not a.startswith("--")]

    with FANDOM_CONFIG_PATH.open(encoding="utf-8") as f:
        fandom_config = FandomConfig.model_validate(yaml.safe_load(f))

    ig_member_map, ig_display_map = fandom_config.build_ig_maps()
    ig_sources = set(ig_member_map) | {"instagram_official"}

    llm = _load_llm()

    if specific_files:
        targets = specific_files
    else:
        md_files = sorted(ITEMS_DIR.glob("*.md"))
        targets = md_files if force else [p for p in md_files if not _has_summary(p)]

    logger.info("Found %d items to process", len(targets))

    updated = 0
    for md_path in targets:
        if _parse_frontmatter(md_path).get("deleted"):
            logger.info("skip deleted: %s", md_path.name)
            continue
        if _process_file(md_path, fandom_config, llm, ig_member_map, ig_display_map, ig_sources):
            updated += 1
        time.sleep(3)

    logger.info("Done: %d/%d items updated", updated, len(targets))


if __name__ == "__main__":
    main()
