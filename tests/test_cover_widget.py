import tempfile
import unittest
from pathlib import Path

from audio_division.cover_widget import CoverWidget, album_cover_info


class FakeLabel:
    def __init__(self):
        self.configured = {}

    def config(self, **kwargs):
        self.configured.update(kwargs)

    def update_idletasks(self):
        pass

    def winfo_width(self):
        return 320

    def winfo_height(self):
        return 320


class FakeStatus:
    def __init__(self):
        self.text = ""

    def config(self, **kwargs):
        self.text = kwargs.get("text", self.text)


class CoverWidgetTests(unittest.TestCase):
    def test_album_cover_info_uses_existing_local_artwork(self):
        with tempfile.TemporaryDirectory() as tmp:
            cover = Path(tmp) / "cover.jpg"
            cover.write_text("art")

            info = album_cover_info({"artwork": {"local": str(cover)}})

        self.assertEqual(info["status"], "Present")
        self.assertEqual(info["source"], "local")
        self.assertEqual(info["display"], "cover.jpg")

    def test_album_cover_info_uses_archive_artwork_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            (album / "z-random.jpg").write_text("art")
            (album / "folder.jpg").write_text("art")

            info = album_cover_info({"artwork": {"local": ""}}, album)

        self.assertEqual(info["status"], "Present")
        self.assertEqual(info["source"], "local")
        self.assertEqual(info["display"], "folder.jpg")

    def test_album_cover_info_reports_missing_artwork(self):
        info = album_cover_info({"artwork": {"local": ""}})

        self.assertEqual(info["status"], "Missing")
        self.assertEqual(info["source"], "none")
        self.assertEqual(info["display"], "No artwork available")

    def test_cover_widget_renders_missing_placeholder(self):
        label = FakeLabel()
        status = FakeStatus()

        image = CoverWidget(label, status).render({"status": "Missing", "display": "No artwork available"})

        self.assertIsNone(image)
        self.assertEqual(label.configured["text"], "No artwork")
        self.assertEqual(status.text, "Artwork: Missing - No artwork available")

    def test_cover_widget_handles_loading_failure(self):
        label = FakeLabel()
        status = FakeStatus()

        def failing_loader(path, label):
            raise OSError("bad image")

        image = CoverWidget(label, status, image_loader=failing_loader).render(
            {"status": "Present", "display": "cover.jpg", "path": "/tmp/cover.jpg"}
        )

        self.assertIsNone(image)
        self.assertEqual(label.configured["text"], "Artwork unavailable")
        self.assertEqual(status.text, "Artwork: Present - cover.jpg")


if __name__ == "__main__":
    unittest.main()
