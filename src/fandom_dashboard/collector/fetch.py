from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import feedparser
import requests

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
    save_image: bool = True


def fetch_rss(source: dict[str, Any], fandom_id: str) -> list[RawItem]:
    feed = feedparser.parse(source["url"])
    save_image = source.get("save_image", True)
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
            save_image=save_image,
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
        from bs4 import BeautifulSoup
        from crawl4ai import AsyncWebCrawler
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)
            if not result.success or not result.html:
                return {}
            soup = BeautifulSoup(result.html, "html.parser")

            def og(prop: str) -> str:
                tag = soup.find("meta", property=prop)
                return tag["content"] if tag and tag.get("content") else ""

            def meta_name(name: str) -> str:
                tag = soup.find("meta", attrs={"name": name})
                return tag["content"] if tag and tag.get("content") else ""

            return {
                "title": og("og:title") or meta_name("title") or (soup.title.string if soup.title else ""),
                "description": og("og:description") or meta_name("description"),
                "image": og("og:image"),
                "published": meta_name("article:published_time") or meta_name("article:modified_time"),
            }
    except Exception as e:
        logger.warning("OGP fetch failed %s: %s", url, e)
    return {}


def fetch_scrape(source: dict[str, Any], fandom_id: str, base_url: str = "") -> list[RawItem]:
    page_url = source["url"]
    selector = source.get("selector", "a")
    save_image = source.get("save_image", True)
    links = asyncio.run(_scrape_page(page_url, selector))

    items = []
    for link in links:
        href = link.get("href", "")
        if not href:
            continue
        if href.startswith("/"):
            href = (base_url or page_url.rstrip("/")) + href

        ogp = asyncio.run(_fetch_page_ogp(href))
        published = ogp.get("published", "")
        title = ogp.get("title") or link.get("text", "")
        summary = ogp.get("description", "")
        image = ogp.get("image", "")

        items.append(RawItem(
            url=href,
            title=title,
            summary=summary,
            published=published,
            image=image,
            source_id=source["source_id"],
            fandom_id=fandom_id,
            save_image=save_image,
        ))
    return items


_IG_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "X-IG-App-ID": "936619743392459",
}


def _get_ig_posts(username: str) -> list[dict]:
    r = requests.get(
        "https://www.instagram.com/api/v1/users/web_profile_info/",
        params={"username": username},
        headers=_IG_HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["data"]["user"]["edge_owner_to_timeline_media"]["edges"]


def fetch_instagram(source: dict[str, Any], fandom_id: str) -> list[RawItem]:
    save_image = source.get("save_image", True)
    items = []
    for e in _get_ig_posts(source["username"]):
        node = e["node"]
        caption = (node.get("edge_media_to_caption", {}).get("edges") or [{}])[0].get("node", {}).get("text", "")
        published = datetime.fromtimestamp(node["taken_at_timestamp"], tz=timezone.utc).isoformat()
        items.append(RawItem(
            url=f"https://www.instagram.com/p/{node['shortcode']}/",
            title=caption.split("\n")[0][:100],
            summary=caption,
            published=published,
            image=node.get("display_url") or node.get("thumbnail_src", ""),
            source_id=source["source_id"],
            fandom_id=fandom_id,
            raw={"shortcode": node["shortcode"]},
            save_image=save_image,
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

    for src in sources.get("instagram", []):
        try:
            items.extend(fetch_instagram(src, fandom_id))
        except Exception as e:
            logger.error("instagram fetch error %s: %s", src["source_id"], e)

    return items
