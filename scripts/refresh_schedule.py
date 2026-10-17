import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
TIMEZONE = ZoneInfo("America/Chicago")
API_URL = "https://api.openai.com/v1/responses"


def next_week_start(today: date) -> date:
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    return today + timedelta(days=days_until_monday)


def response_text(response: dict) -> str:
    for output in response.get("output", []):
        if output.get("type") != "message":
            continue
        for content in output.get("content", []):
            if content.get("type") == "output_text":
                return content["text"]
    raise ValueError("OpenAI returned no structured text output")


def validate_schedule(schedule: dict, titles: list[str], week_start: date) -> None:
    if schedule.get("week_start") != week_start.isoformat():
        raise ValueError("OpenAI returned the wrong week_start")

    if schedule.get("timezone") != "America/Chicago":
        raise ValueError("OpenAI returned the wrong timezone")

    if not isinstance(schedule.get("airings"), list):
        raise ValueError("OpenAI returned an invalid airings list")

    week_end = week_start + timedelta(days=6)
    for airing in schedule["airings"]:
        if airing.get("title") not in titles:
            raise ValueError(f"Unexpected show title: {airing.get('title')!r}")

        airtime = datetime.fromisoformat(airing["airtime"])
        if airtime.utcoffset() is None:
            raise ValueError("Every airtime must include a UTC offset")
        local_date = airtime.astimezone(TIMEZONE).date()
        if not week_start <= local_date <= week_end:
            raise ValueError(f"Airtime is outside the requested week: {airing['airtime']}")

        parsed_url = urlparse(airing["source_url"])
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            raise ValueError("Every airing must include an HTTPS source URL")


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY Actions secret")

    titles = json.loads((ROOT / "watchlist.json").read_text(encoding="utf-8"))
    today = datetime.now(TIMEZONE).date()
    week_start = next_week_start(today)
    week_end = week_start + timedelta(days=6)

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "week_start": {"type": "string"},
            "timezone": {"type": "string", "enum": ["America/Chicago"]},
            "airings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string", "enum": titles},
                        "airtime": {"type": "string"},
                        "source_url": {"type": "string"},
                    },
                    "required": ["title", "airtime", "source_url"],
                },
            },
        },
        "required": ["week_start", "timezone", "airings"],
    }

    prompt = (
        f"Find new-episode streaming airtimes from {week_start.isoformat()} "
        f"through {week_end.isoformat()} for these exact shows: "
        f"{json.dumps(titles)}. Search official broadcaster or streaming-service "
        "pages first. Include only episodes with a verifiable date and time; do "
        "not infer or invent times. Convert every time to America/Chicago and "
        "return it as ISO 8601 with an explicit UTC offset. Include the direct "
        "HTTPS URL that verifies each airing. If an airing cannot be verified, "
        "omit it. Return the requested week_start exactly."
    )

    request_body = {
        "model": os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        "tools": [{"type": "web_search"}],
        "input": prompt,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "weekly_anime_schedule",
                "strict": True,
                "schema": schema,
            }
        },
    }
    request = Request(
        API_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=120) as response:
            result = json.loads(response.read())
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"OpenAI API returned HTTP {error.code}: {details}") from error

    schedule = json.loads(response_text(result))
    schedule["timezone"] = "America/Chicago"
    validate_schedule(schedule, titles, week_start)

    destination = ROOT / "schedule.json"
    destination.write_text(
        json.dumps(schedule, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Prepared {len(schedule['airings'])} verified airing(s) for {week_start}")


if __name__ == "__main__":
    main()