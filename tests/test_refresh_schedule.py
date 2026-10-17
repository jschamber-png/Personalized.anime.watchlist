import contextlib
import io
import unittest
from datetime import date

from scripts.refresh_schedule import (
    build_prompt,
    next_week_start,
    validate_schedule,
)


class RefreshScheduleTests(unittest.TestCase):
    def test_requests_the_next_monday_through_sunday(self):
        week_start = next_week_start(date(2026, 10, 17))

        self.assertEqual(week_start, date(2026, 10, 19))
        prompt = build_prompt(["Show"], week_start)
        self.assertIn("from 2026-10-19 through 2026-10-25", prompt)

    def test_omits_and_reports_invalid_dates_using_chicago_week(self):
        schedule = {
            "week_start": "2026-10-19",
            "timezone": "America/Chicago",
            "airings": [
                {
                    "title": "Show",
                    "airtime": "2026-10-17T10:00:00-05:00",
                    "source_url": "https://example.com/outside",
                },
                {
                    "title": "Show",
                    "airtime": "2026-10-26T00:30:00+00:00",
                    "source_url": "https://example.com/within-chicago-week",
                },
                {
                    "title": "Show",
                    "airtime": "2026-10-20T10:00:00",
                    "source_url": "https://example.com/missing-offset",
                },
            ],
        }
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            airings = validate_schedule(schedule, ["Show"], date(2026, 10, 19))

        self.assertEqual(
            airings,
            [schedule["airings"][1]],
        )
        self.assertIn("Airtime is outside the requested week", errors.getvalue())
        self.assertIn("Every airtime must include a UTC offset", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
