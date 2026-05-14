import tempfile
from pathlib import Path

from fandom_dashboard.collector.fetch import RawItem
from fandom_dashboard.collector.save import save_item


def _item():
    return RawItem(
        url="https://natalie.mu/music/news/12345",
        title="ももクロ夏のバカ騒ぎ2026発表",
        summary="ももいろクローバーZが夏ライブを発表した。",
        published="Thu, 15 May 2026 10:00:00 +0900",
        image="https://cdn.natalie.mu/img/test.jpg",
        source_id="natalie",
        fandom_id="momoclo",
    )


def test_save_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir)
        llm_result = {"summary": "テスト要約", "category": "live", "members": ["kanako", "ayaka"]}
        path = save_item(_item(), llm_result, "momoclo", output_dir=out)
        assert path is not None
        assert path.exists()
        content = path.read_text()
        assert "fandom: momoclo" in content
        assert "category: live" in content
        assert "kanako" in content
        assert "テスト要約" in content


def test_save_skip_existing():
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir)
        llm_result = {"summary": "要約", "category": "news", "members": ["group"]}
        path1 = save_item(_item(), llm_result, "momoclo", output_dir=out)
        path2 = save_item(_item(), llm_result, "momoclo", output_dir=out)
        assert path1 is not None
        assert path2 is None  # skipped
