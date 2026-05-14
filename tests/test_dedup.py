from fandom_dashboard.collector.fetch import RawItem
from fandom_dashboard.collector.dedup import deduplicate


def _item(url, title, source="natalie"):
    return RawItem(url=url, title=title, summary="", published="", image="", source_id=source, fandom_id="momoclo")


def test_exact_url_dedup():
    items = [
        _item("https://example.com/news/1?utm_source=tw", "ももクロライブ発表"),
        _item("https://example.com/news/1?utm_source=fb", "ももクロライブ発表"),
    ]
    result = deduplicate(items)
    assert len(result) == 1


def test_different_urls_kept():
    items = [
        _item("https://example.com/news/1", "ももクロライブ発表"),
        _item("https://example.com/news/2", "あーりん誕生日"),
    ]
    result = deduplicate(items)
    assert len(result) == 2


def test_fuzzy_title_dedup():
    items = [
        _item("https://natalie.mu/1", "ももいろクローバーZ 夏ライブ2026発表！"),
        _item("https://barks.jp/1", "ももいろクローバーZ 夏ライブ2026発表", source="barks"),
    ]
    result = deduplicate(items)
    assert len(result) == 1
    # sources merged
    assert "natalie" in result[0].source_id
    assert "barks" in result[0].source_id


def test_source_merge_on_url_dedup():
    items = [
        _item("https://example.com/1?utm_source=tw", "title", source="natalie"),
        _item("https://example.com/1?utm_source=fb", "title", source="barks"),
    ]
    result = deduplicate(items)
    assert len(result) == 1
    assert "natalie" in result[0].source_id
    assert "barks" in result[0].source_id
