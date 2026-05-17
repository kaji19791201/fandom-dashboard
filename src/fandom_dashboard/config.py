from __future__ import annotations

from pydantic import BaseModel


class Member(BaseModel):
    id: str
    names: list[str]


class RssSource(BaseModel):
    url: str
    source_id: str
    save_image: bool = True
    filter: bool = False


class ScrapeSource(BaseModel):
    url: str
    source_id: str
    selector: str
    save_image: bool = False
    filter: bool = False


class RsshubSource(BaseModel):
    url: str
    source_id: str
    enabled: bool = True
    filter: bool = False


class InstagramSource(BaseModel):
    username: str
    source_id: str


class Sources(BaseModel):
    rss: list[RssSource] = []
    scrape: list[ScrapeSource] = []
    rsshub: list[RsshubSource] = []
    instagram: list[InstagramSource] = []


class FandomConfig(BaseModel):
    id: str
    name: str
    members: list[Member]
    sources: Sources

    def build_ig_maps(self) -> tuple[dict[str, str], dict[str, str]]:
        """Returns (member_map, display_map) derived from instagram sources."""
        members_by_id = {m.id: m.names[0] for m in self.members}
        member_map: dict[str, str] = {}
        display_map: dict[str, str] = {}
        for src in self.sources.instagram:
            sid = src.source_id
            if sid == "instagram_official":
                display_map[sid] = f"{self.name}（公式）"
            else:
                mid = sid.removeprefix("instagram_")
                member_map[sid] = mid
                display_map[sid] = members_by_id.get(mid, mid)
        return member_map, display_map
