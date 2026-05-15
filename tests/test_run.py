from fandom_dashboard.collector.fetch import RawItem
from fandom_dashboard.run import _is_short_hiragana, _keyword_filter

FANDOM_CONFIG = {
    "name": "ももいろクローバーZ",
    "members": [
        {"names": ["百田夏菜子", "かなこ", "Kanako"]},
        {"names": ["高城れに", "れに", "Reni"]},
        {"names": ["玉井詩織", "しおり", "Shiori"]},
        {"names": ["佐々木彩夏", "あーりん", "Ayaka"]},
    ],
}


def make_item(title, source_id="natalie"):
    return RawItem(url="", title=title, summary="", published="", image="", source_id=source_id, fandom_id="momoclo")


class TestIsShortHiragana:
    def test_two_char_hiragana(self):
        assert _is_short_hiragana("れに") is True

    def test_three_char_hiragana(self):
        assert _is_short_hiragana("しおり") is True
        assert _is_short_hiragana("かなこ") is True

    def test_four_char_hiragana_not_excluded(self):
        assert _is_short_hiragana("ひらがな") is False

    def test_katakana_not_excluded(self):
        # あーりん contains ー (katakana long vowel mark, not hiragana)
        assert _is_short_hiragana("あーりん") is False

    def test_kanji_not_excluded(self):
        assert _is_short_hiragana("百田夏菜子") is False

    def test_ascii_not_excluded(self):
        assert _is_short_hiragana("Reni") is False


class TestKeywordFilter:
    def test_matching_item_passes(self):
        items = [make_item("ももいろクローバーZが新曲リリース")]
        result = _keyword_filter(items, FANDOM_CONFIG, {"natalie"})
        assert len(result) == 1

    def test_non_matching_item_blocked(self):
        items = [make_item("これに先がけて新作アニメ発表")]
        result = _keyword_filter(items, FANDOM_CONFIG, {"natalie"})
        assert len(result) == 0

    def test_source_not_in_filter_set_always_passes(self):
        items = [make_item("全然関係ないニュース", source_id="official")]
        result = _keyword_filter(items, FANDOM_CONFIG, {"natalie"})
        assert len(result) == 1

    def test_empty_filter_set_all_pass(self):
        items = [make_item("全然関係ないニュース", source_id="natalie")]
        result = _keyword_filter(items, FANDOM_CONFIG, set())
        assert len(result) == 1

    def test_short_hiragana_keyword_not_used(self):
        # "れに" is excluded from keywords; "これに先がけて" must NOT match
        items = [make_item("これに先がけてリリース")]
        result = _keyword_filter(items, FANDOM_CONFIG, {"natalie"})
        assert len(result) == 0

    def test_kanji_member_name_matches(self):
        items = [make_item("高城れにが単独公演")]
        result = _keyword_filter(items, FANDOM_CONFIG, {"natalie"})
        assert len(result) == 1
