from fandom_dashboard.collector.fetch import RawItem
from fandom_dashboard.collector.summarize import summarize


class MockLLM:
    def __init__(self, response: str):
        self.response = response
        self.last_image_url = None

    def complete(self, prompt: str, image_url: str = "") -> str:
        self.last_image_url = image_url
        return self.response


MEMBERS = [
    {"id": "kanako", "names": ["百田夏菜子", "かなこ"]},
    {"id": "ayaka", "names": ["佐々木彩夏", "あーりん"]},
]

_ITEM = RawItem(
    url="https://example.com/1",
    title="ももクロ夏ライブ発表",
    summary="ももいろクローバーZが夏のライブを発表した。",
    published="",
    image="",
    source_id="natalie",
    fandom_id="momoclo",
)


def test_summarize_valid_json():
    llm = MockLLM('{"summary": "夏のライブを発表。", "category": "live", "members": ["kanako"]}')
    result = summarize(_ITEM, llm, MEMBERS)
    assert result["summary"] == "夏のライブを発表。"
    assert result["category"] == "live"
    assert "kanako" in result["members"]


def test_summarize_with_code_fence():
    llm = MockLLM('```json\n{"summary": "要約", "category": "news", "members": ["group"]}\n```')
    result = summarize(_ITEM, llm, MEMBERS)
    assert result["summary"] == "要約"


def test_summarize_fallback_on_invalid():
    llm = MockLLM("LLMが返した不正テキスト")
    result = summarize(_ITEM, llm, MEMBERS)
    assert result["category"] == "news"
    assert result["members"] == ["group"]


def test_summarize_passes_image_url():
    item_with_image = RawItem(
        url="https://example.com/2",
        title="タイトル",
        summary="本文",
        published="",
        image="https://example.com/thumb.jpg",
        source_id="natalie",
        fandom_id="momoclo",
    )
    llm = MockLLM('{"summary": "要約", "category": "news", "members": ["group"]}')
    summarize(item_with_image, llm, MEMBERS)
    assert llm.last_image_url == "https://example.com/thumb.jpg"
