from unittest.mock import patch

from fandom_dashboard.collector.fetch import fetch_instagram, RawItem


def _make_edge(shortcode: str, caption: str, timestamp: int, thumbnail: str) -> dict:
    return {
        "node": {
            "shortcode": shortcode,
            "taken_at_timestamp": timestamp,
            "thumbnail_src": thumbnail,
            "edge_media_to_caption": {"edges": [{"node": {"text": caption}}]},
        }
    }


def test_fetch_instagram_returns_raw_items():
    edges = [
        _make_edge("ABC123", "Hello\nworld", 1715000000, "https://cdn.example.com/img.jpg"),
        _make_edge("DEF456", "", 1715001000, ""),
    ]

    with patch("fandom_dashboard.collector.fetch._get_ig_posts", return_value=edges):
        items = fetch_instagram({"username": "test_user", "source_id": "ig_test"}, "momoclo")

    assert len(items) == 2

    first = items[0]
    assert isinstance(first, RawItem)
    assert first.url == "https://www.instagram.com/p/ABC123/"
    assert first.title == "Hello"
    assert first.summary == "Hello\nworld"
    assert "+00:00" in first.published
    assert first.image == "https://cdn.example.com/img.jpg"
    assert first.source_id == "ig_test"
    assert first.fandom_id == "momoclo"
    assert first.raw == {"shortcode": "ABC123"}


def test_fetch_instagram_empty_caption():
    edges = [_make_edge("XYZ", "", 1715000000, "")]

    with patch("fandom_dashboard.collector.fetch._get_ig_posts", return_value=edges):
        items = fetch_instagram({"username": "u", "source_id": "s"}, "momoclo")

    assert items[0].title == ""
    assert items[0].summary == ""


def test_fetch_instagram_long_caption_truncated():
    long_caption = "a" * 200
    edges = [_make_edge("ZZZ", long_caption, 1715000000, "")]

    with patch("fandom_dashboard.collector.fetch._get_ig_posts", return_value=edges):
        items = fetch_instagram({"username": "u", "source_id": "s"}, "momoclo")

    assert len(items[0].title) == 100
    assert items[0].summary == long_caption
