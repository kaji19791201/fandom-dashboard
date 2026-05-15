import tempfile
from pathlib import Path
from unittest.mock import patch

from fandom_dashboard.collector.fetch import RawItem
from fandom_dashboard.collector.save import save_item


def _item(save_image: bool = True):
    return RawItem(
        url="https://natalie.mu/music/news/12345",
        title="ももクロ夏のバカ騒ぎ2026発表",
        summary="ももいろクローバーZが夏ライブを発表した。",
        published="Thu, 15 May 2026 10:00:00 +0900",
        image="https://cdn.natalie.mu/img/test.jpg",
        source_id="natalie",
        fandom_id="momoclo",
        save_image=save_image,
    )


def test_save_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir)
        llm_result = {"summary": "テスト要約", "category": "live", "members": ["kanako", "ayaka"]}
        with patch("fandom_dashboard.collector.save._download_image", return_value=False):
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
        with patch("fandom_dashboard.collector.save._download_image", return_value=False):
            path1 = save_item(_item(), llm_result, "momoclo", output_dir=out)
            path2 = save_item(_item(), llm_result, "momoclo", output_dir=out)
        assert path1 is not None
        assert path2 is None  # skipped


def test_save_image_local_when_download_succeeds():
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir)
        llm_result = {"summary": "要約", "category": "news", "members": ["group"]}

        def fake_download(url: str, dest: Path) -> bool:
            dest.write_bytes(b"fake image data")
            return True

        with patch("fandom_dashboard.collector.save._download_image", side_effect=fake_download):
            path = save_item(_item(save_image=True), llm_result, "momoclo", output_dir=out)

        assert path is not None
        content = path.read_text()
        # local filename in frontmatter and embed (no angle brackets)
        assert "image: 2026-05-15_" in content
        assert "![](" in content
        assert "![](<" not in content


def test_save_image_false_no_embed():
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir)
        llm_result = {"summary": "要約", "category": "news", "members": ["group"]}
        path = save_item(_item(save_image=False), llm_result, "momoclo", output_dir=out)
        assert path is not None
        content = path.read_text()
        # URL is in frontmatter but not embedded
        assert "image: https://cdn.natalie.mu" in content
        assert "![]" not in content
