from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

from .collector.dedup import deduplicate
from .collector.fetch import collect_all
from .collector.save import DOCS_ROOT, resolve_local_image, save_item
from .collector.summarize import summarize
from .config import FandomConfig

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent.parent / "config" / "fandoms"


def _load_llm():
    provider = os.environ.get("LLM_PROVIDER", "claude_cli")
    if provider == "claude_cli":
        from .llm.claude_cli import ClaudeCLIProvider
        return ClaudeCLIProvider()
    if provider == "gemini":
        from .llm.gemini import GeminiProvider
        return GeminiProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


_HIRAGANA = frozenset(chr(c) for c in range(0x3041, 0x3097))


def _is_short_hiragana(kw: str) -> bool:
    return len(kw) < 4 and all(c in _HIRAGANA for c in kw)


def _keyword_filter(items, fandom_config: FandomConfig, filter_source_ids: set[str]):
    """Keep items that mention fandom name or any member name.
    Only items whose source_id is in filter_source_ids are subject to filtering."""
    fandom_name = fandom_config.name
    member_names = [name for m in fandom_config.members for name in m.names]
    keywords = [kw for kw in ([fandom_name] + member_names) if not _is_short_hiragana(kw)]

    filtered = []
    for item in items:
        if item.source_id not in filter_source_ids:
            filtered.append(item)
            continue
        text = f"{item.title} {item.summary}"
        if any(kw in text for kw in keywords):
            filtered.append(item)
    return filtered


def run_fandom(fandom_config: FandomConfig, llm) -> int:
    fandom_id = fandom_config.id
    logger.info("=== %s ===", fandom_config.name)

    raw = collect_all(fandom_config)
    logger.info("fetched: %d items", len(raw))

    filter_source_ids = {
        src.source_id
        for src in [
            *fandom_config.sources.rss,
            *fandom_config.sources.scrape,
            *fandom_config.sources.rsshub,
        ]
        if src.filter
    }

    filtered = _keyword_filter(raw, fandom_config, filter_source_ids)
    logger.info("after keyword filter: %d items", len(filtered))

    deduped = deduplicate(filtered)
    logger.info("after dedup: %d items", len(deduped))

    ig_member_map, _ = fandom_config.build_ig_maps()

    items_dir = DOCS_ROOT / "fandom" / fandom_id / "items"
    members_dicts = [m.model_dump() for m in fandom_config.members]
    saved = 0
    for item in deduped:
        local_img = resolve_local_image(item, items_dir)
        image_url = str(local_img) if local_img else ""
        llm_result = summarize(item, llm, members_dicts, image_url=image_url)
        if item.source_id in ig_member_map:
            llm_result["members"] = [ig_member_map[item.source_id]]
        if not llm_result["members"]:
            logger.info("skip (no members): %s", item.url)
            continue
        path = save_item(item, llm_result, fandom_id)
        if path:
            saved += 1

    logger.info("saved %d new items", saved)
    return saved


def main():
    llm = _load_llm()
    config_files = sorted(CONFIG_DIR.glob("*.yaml"))
    if not config_files:
        logger.warning("no fandom config files found in %s", CONFIG_DIR)
        return

    total = 0
    for config_file in config_files:
        with config_file.open(encoding="utf-8") as f:
            fandom_config = FandomConfig.model_validate(yaml.safe_load(f))
        total += run_fandom(fandom_config, llm)

    logger.info("total new items: %d", total)


if __name__ == "__main__":
    main()
