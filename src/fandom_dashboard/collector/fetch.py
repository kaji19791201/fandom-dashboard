from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import feedparser

logger = logging.getLogger(__name__)


@dataclass
class RawItem:
    url: str
    title: str
    summary: str
    published: str
    image: str
    source_id: str
    fandom_id: str
    raw: dict = field(default_factory=dict)


def fetch_rss(source: dict[str, Any], fandom_id: str) -> list[RawItem]:
    feed = feedparser.parse(source["url"])
    items = []
    for entry in feed.entries:
        image = ""
        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            image = entry.media_thumbnail[0].get("url", "")
        elif hasattr(entry, "media_content") and entry.media_content:
            image = entry.media_content[0].get("url", "")

        items.append(RawItem(
            url=entry.get("link", ""),
            title=entry.get("title", ""),
            summary=entry.get("summary", ""),
            published=entry.get("published", ""),
            image=image,
            source_id=source["source_id"],
            fandom_id=fandom_id,
        ))
    return items


async def _scrape_page(url: str, selector: str) -> list[dict]:
    try:
        from bs4 import BeautifulSoup
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)
            if result.success and result.html:
                soup = BeautifulSoup(result.html, "html.parser")
                return [
                    {"href": a.get("href", ""), "text": a.get_text(strip=True)}
                    for a in soup.select(selector)
                    if a.get("href")
                ]
    except Exception as e:
        logger.warning("scrape failed %s: %s", url, e)
    return []


async def _fetch_page_ogp(url: str) -> dict:
    try:
        from crawl4ai import AsyncWebCrawler
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)
            if not result.success:
                return {}
            meta = result.metadata or {}
            return {
                "title": meta.get("og:title") or meta.get("title", ""),
                "description": meta.get("og:description", ""),
                "image": meta.get("og:image", ""),
            }
    except Exception as e:
        logger.warning("OGP fetch failed %s: %s", url, e)
    return {}


def fetch_scrape(source: dict[str, Any], fandom_id: str, base_url: str = "") -> list[RawItem]:
    page_url = source["url"]
    selector = source.get("selector", "a")
    links = asyncio.run(_scrape_page(page_url, selector))

    items = []
    for link in links:
        href = link.get("href", "")
        if not href:
            continue
        if href.startswith("/"):
            href = (base_url or page_url.rstrip("/")) + href

        ogp = asyncio.run(_fetch_page_ogp(href))
        items.append(RawItem(
            url=href,
            title=ogp.get("title") or link.get("text", ""),
            summary=ogp.get("description", ""),
            published="",
            image=ogp.get("image", ""),
            source_id=source["source_id"],
            fandom_id=fandom_id,
        ))
    return items


def collect_all(fandom_config: dict) -> list[RawItem]:
    fandom_id = fandom_config["id"]
    sources = fandom_config.get("sources", {})
    items: list[RawItem] = []

    for src in sources.get("rss", []):
        try:
            items.extend(fetch_rss(src, fandom_id))
            logger.info("RSS %s: %d items", src["source_id"], len(items))
        except Exception as e:
            logger.error("RSS fetch error %s: %s", src["source_id"], e)

    for src in sources.get("rsshub", []):
        if not src.get("enabled", True):
            continue
        try:
            items.extend(fetch_rss(src, fandom_id))
        except Exception as e:
            logger.error("RSSHub fetch error %s: %s", src["source_id"], e)

    for src in sources.get("scrape", []):
        try:
            items.extend(fetch_scrape(src, fandom_id))
        except Exception as e:
            logger.error("scrape error %s: %s", src["source_id"], e)

    return items
