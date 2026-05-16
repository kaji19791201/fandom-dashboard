from __future__ import annotations

import json
import logging
import re

from ..llm.base import LLMProvider
from .fetch import RawItem

logger = logging.getLogger(__name__)


def _build_prompt(item: RawItem, members_json: str) -> str:
    return f"""あなたはファンダムニュースのキュレーターです。
以下の記事を読んで次の情報をJSONのみで返してください（説明文不要）:
- summary: 日本語で2-3文の要約
- category: "live" | "release" | "news" | "sns" のいずれか
- members: 登場するメンバーIDのリスト（定義: {members_json}）。グループ全体なら ["group"]

タイトル: {item.title}
本文: {item.summary[:800]}
"""


def _extract_json(text: str) -> dict:
    # strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("```").strip()
    return json.loads(text)


def summarize(item: RawItem, llm: LLMProvider, members: list[dict], image_url: str = "") -> dict:
    members_json = json.dumps(
        [{"id": m["id"], "names": m["names"]} for m in members],
        ensure_ascii=False,
    )
    prompt = _build_prompt(item, members_json)
    try:
        response = llm.complete(prompt, image_url=image_url)
        result = _extract_json(response)
        return {
            "summary": result.get("summary", ""),
            "category": result.get("category", "news"),
            "members": result.get("members", ["group"]),
        }
    except Exception as e:
        logger.warning("summarize failed for %s: %s", item.url, e)
        return {"summary": "", "category": "news", "members": ["group"]}
