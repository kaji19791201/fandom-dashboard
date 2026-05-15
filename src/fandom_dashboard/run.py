from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

from .collector.dedup import deduplicate
from .collector.fetch import collect_all
from .collector.save import save_item
from .collector.summarize import summarize

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent.parent / "config" / "fandoms"


def _load_llm():
    provider = os.environ.get("LLM_PROVIDER", "claude_cli")
    if provider == "claude_cli":
        from .llm.claude_cli import ClaudeCLIProvider
        return ClaudeCLIProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def _keyword_filter(items, fandom_config):
    """Keep items whose title mentions fandom name or any member name."""
    fandom_name = fandom_config["name"]
    member_names = [
        name
        for m in fandom_config.get("members", [])
        for name in m.get("names", [])
    ]
    # skip short hiragana-only keywords (e.g. "れに") — too prone to substring false positives
    keywords = [
        kw for kw in [fandom_name] + member_names
        if not (all("ぁ" <= c <= "ゖ" for c in kw) and len(kw) < 4)
    ]

    filtered = []
    for item in items:
        if any(kw in item.title for kw in keywords):
            filtered.append(item)
    return filtered


def run_fandom(fandom_config: dict, llm) -> int:
    fandom_id = fandom_config["id"]
    logger.info("=== %s ===", fandom_config["name"])

    raw = collect_all(fandom_config)
    logger.info("fetched: %d items", len(raw))

    # Instagram items are from official member accounts — all are relevant
    instagram_items = [i for i in raw if i.source_id.startswith("instagram_")]
    other_items = [i for i in raw if not i.source_id.startswith("instagram_")]
    filtered = instagram_items + _keyword_filter(other_items, fandom_config)
    logger.info("after keyword filter: %d items", len(filtered))

    deduped = deduplicate(filtered)
    logger.info("after dedup: %d items", len(deduped))

    saved = 0
    for item in deduped:
        llm_result = summarize(item, llm, fandom_config.get("members", []))
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
            fandom_config = yaml.safe_load(f)
        total += run_fandom(fandom_config, llm)

    logger.info("total new items: %d", total)


if __name__ == "__main__":
    main()
