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

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_waits_until_24_hours_before_first_airing(self):
        before_deadline = datetime.fromisoformat("2026-01-06T09:59:00-06:00")
        changed = publish_digest(self.schedule, self.feed_path, before_deadline)

        self.assertTrue(changed)
        root = ET.parse(self.feed_path).getroot()
        self.assertEqual(root.findall("./channel/item"), [])

    def test_publishes_one_digest_at_deadline(self):
        deadline = datetime.fromisoformat("2026-01-06T10:00:00-06:00")
        publish_digest(self.schedule, self.feed_path, deadline)

        root = ET.parse(self.feed_path).getroot()
        items = root.findall("./channel/item")
        self.assertEqual(len(items), 1)
        description = items[0].findtext("description")
        self.assertIn("First Show", description)
        self.assertIn("Second Show", description)
        self.assertEqual(
            items[0].findtext("guid"), "anime-schedule-2026-01-05"
        )

    def test_does_not_duplicate_a_published_week(self):
        deadline = datetime.fromisoformat("2026-01-06T10:00:00-06:00")
        publish_digest(self.schedule, self.feed_path, deadline)
        later = datetime.fromisoformat("2026-01-06T10:15:00-06:00")

        changed = publish_digest(self.schedule, self.feed_path, later)

        self.assertFalse(changed)
        self.assertEqual(len(ET.parse(self.feed_path).findall("./channel/item")), 1)


if __name__ == "__main__":
    unittest.main()