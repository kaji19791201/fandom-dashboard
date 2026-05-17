"""Fix duplicate summaries and wrong members from the backfill run."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fandom_dashboard.config import FandomConfig  # noqa: E402

FANDOM_CONFIG_PATH = PROJECT_ROOT / "config" / "fandoms" / "momoclo.yaml"
ITEMS_DIR = Path("/Users/Shared/kaji/docs/fandom/momoclo/items")


def _split_file(md_path: Path):
    text = md_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, None, None
    fm = yaml.safe_load(parts[1]) or {}
    body = parts[2]
    return parts[1], fm, body


_HAS_JAPANESE = re.compile(r'[぀-ヿ一-鿿]')


def _is_real_summary(text: str) -> bool:
    """True if text looks like an actual summary (contains Japanese, not a URL fragment)."""
    return bool(_HAS_JAPANESE.search(text))


def _extract_text_blocks(body: str) -> list[str]:
    """Return non-empty text blocks that are not image embeds or [元記事] lines."""
    blocks = []
    current = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                text = "\n".join(current).strip()
                if text and not text.startswith("![") and not text.startswith("[元記事]"):
                    blocks.append(text)
                current = []
        else:
            current.append(line)
    if current:
        text = "\n".join(current).strip()
        if text and not text.startswith("![") and not text.startswith("[元記事]"):
            blocks.append(text)
    return blocks


def fix_file(md_path: Path, ig_member_map: dict[str, str]) -> bool:
    text = md_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False

    fm = yaml.safe_load(parts[1]) or {}
    body = parts[2]

    changed = False

    # 1. Fix trailing corruption (e.g., "2Gt/)" after [元記事]) — do this first
    cleaned = re.sub(r"(\[元記事\]\([^)]+\))\n\S+\n?$", r"\1\n", body)
    if cleaned != body:
        body = cleaned
        changed = True

    # 2. Fix wrong members via ig_member_map
    sources = fm.get("source", [])
    source_id = sources[0] if sources else ""
    if source_id in ig_member_map:
        correct_member = ig_member_map[source_id]
        current_members = fm.get("members") or []
        if current_members != [correct_member]:
            fm["members"] = [correct_member]
            changed = True

    # 3. Remove duplicate summary blocks - keep only the last real summary
    text_blocks = [b for b in _extract_text_blocks(body) if _is_real_summary(b)]
    if len(text_blocks) > 1:
        keep = text_blocks[-1]
        # Remove all text lines, re-insert only the last summary before [元記事]
        new_body_lines = []
        in_text_block = False
        for line in body.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("![") and not stripped.startswith("[元記事]"):
                in_text_block = True
                continue
            else:
                if in_text_block and not stripped:
                    in_text_block = False
                    continue
                new_body_lines.append(line)

        new_body = "\n".join(new_body_lines)
        new_body = re.sub(r"(\[元記事\])", f"{keep}\n\n\\1", new_body, count=1)
        body = new_body
        changed = True

    if not changed:
        return False

    # Rebuild frontmatter
    fm_keys = ["fandom", "date", "source", "category", "members", "title", "url", "image"]
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

    new_text = "---\n" + "\n".join(fm_lines) + "\n---" + body
    md_path.write_text(new_text, encoding="utf-8")
    return True


def main():
    with FANDOM_CONFIG_PATH.open(encoding="utf-8") as f:
        fandom_config = FandomConfig.model_validate(yaml.safe_load(f))
    ig_member_map, _ = fandom_config.build_ig_maps()

    fixed = 0
    for md_path in sorted(ITEMS_DIR.glob("*.md")):
        if fix_file(md_path, ig_member_map):
            print(f"Fixed: {md_path.name}")
            fixed += 1
    print(f"\nTotal fixed: {fixed}")


if __name__ == "__main__":
    main()
