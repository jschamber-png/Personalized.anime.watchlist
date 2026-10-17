import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.publish_digest import publish_digest


class PublishDigestTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.feed_path = Path(self.temp_dir.name) / "anime-schedule.xml"
        self.schedule = {
            "week_start": "2026-01-05",
            "timezone": "America/Chicago",
            "airings": [
                {
                    "title": "First Show",
                    "airtime": "2026-01-07T10:00:00-06:00",
                    "source_url": "https://example.com/first",
                },
                {
                    "title": "Second Show",
                    "airtime": "2026-01-08T11:00:00-06:00",
                    "source_url": "https://example.com/second",
                },
            ],
        }
        self.cover_urls = {
            title: (
                "https://s4.anilist.co/file/anilistcdn/media/anime/cover/"
                f"large/{title.replace(' ', '-')}.jpg"
            )
            for title in ("First Show", "Second Show")
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_waits_until_24_hours_before_first_airing(self):
        before_deadline = datetime.fromisoformat("2026-01-06T09:59:00-06:00")
        changed = publish_digest(
            self.schedule, self.feed_path, self.cover_urls, before_deadline
        )

        self.assertTrue(changed)
        root = ET.parse(self.feed_path).getroot()
        self.assertEqual(root.findall("./channel/item"), [])

    def test_publishes_one_digest_at_deadline(self):
        deadline = datetime.fromisoformat("2026-01-06T10:00:00-06:00")
        publish_digest(self.schedule, self.feed_path, self.cover_urls, deadline)

        root = ET.parse(self.feed_path).getroot()
        items = root.findall("./channel/item")
        self.assertEqual(len(items), 1)
        description = items[0].findtext("description")
        self.assertIn("First Show", description)
        self.assertIn("Second Show", description)
        self.assertIn("Wednesday, Jan 7 at 10:00 AM CST: First Show", description)
        self.assertIn(f"Cover image: {self.cover_urls['First Show']}", description)
        self.assertIn(f"Cover image: {self.cover_urls['Second Show']}", description)
        self.assertEqual(
            items[0].findtext("guid"), "anime-schedule-2026-01-05"
        )

    def test_rejects_missing_anilist_cover(self):
        deadline = datetime.fromisoformat("2026-01-06T10:00:00-06:00")
        cover_urls = {"First Show": self.cover_urls["First Show"]}

        with self.assertRaisesRegex(ValueError, "Missing official AniList cover URL"):
            publish_digest(self.schedule, self.feed_path, cover_urls, deadline)

    def test_every_watchlist_title_has_an_anilist_cover(self):
        root = Path(__file__).resolve().parents[1]
        titles = set(json.loads((root / "watchlist.json").read_text()))
        cover_urls = json.loads((root / "anilist-covers.json").read_text())

        self.assertEqual(titles, set(cover_urls))
        self.assertTrue(
            all(
                url.startswith(
                    "https://s4.anilist.co/file/anilistcdn/media/anime/cover/"
                )
                for url in cover_urls.values()
            )
        )

    def test_does_not_duplicate_a_published_week(self):
        deadline = datetime.fromisoformat("2026-01-06T10:00:00-06:00")
        publish_digest(self.schedule, self.feed_path, self.cover_urls, deadline)
        later = datetime.fromisoformat("2026-01-06T10:15:00-06:00")

        changed = publish_digest(self.schedule, self.feed_path, self.cover_urls, later)

        self.assertFalse(changed)
        self.assertEqual(len(ET.parse(self.feed_path).findall("./channel/item")), 1)


if __name__ == "__main__":
    unittest.main()