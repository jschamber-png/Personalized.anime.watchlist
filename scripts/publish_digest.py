import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SCHEDULE_PATH = ROOT / "schedule.json"
COVERS_PATH = ROOT / "anilist-covers.json"
FEED_PATH = ROOT / "docs" / "anime-schedule.xml"
CENTRAL = ZoneInfo("America/Chicago")
PAGES_URL = "https://jschamber-png.github.io/Personalized.anime.watchlist/"
ANILIST_CDN_PREFIX = "https://s4.anilist.co/file/anilistcdn/media/anime/cover/"


def parse_airings(schedule: dict) -> list[tuple[dict, datetime]]:
    week_start = datetime.fromisoformat(schedule["week_start"]).date()
    if week_start.weekday() != 0:
        raise ValueError("week_start must be a Monday")
    if schedule.get("timezone") != "America/Chicago":
        raise ValueError("schedule timezone must be America/Chicago")

    week_end = week_start + timedelta(days=6)
    airings = []
    for airing in schedule.get("airings", []):
        timestamp = datetime.fromisoformat(airing["airtime"])
        if timestamp.utcoffset() is None:
            raise ValueError("airtime must include a UTC offset")
        local_timestamp = timestamp.astimezone(CENTRAL)
        if not week_start <= local_timestamp.date() <= week_end:
            raise ValueError("airtime is outside the schedule week")
        if not airing.get("title") or not airing.get("source_url", "").startswith("https://"):
            raise ValueError("each airing needs a title and HTTPS source URL")
        airings.append((airing, local_timestamp))
    return sorted(airings, key=lambda airing: airing[1])


def make_feed(now: datetime, item: tuple[str, str, str, str] | None = None) -> bytes:
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "My Personalized Anime Watchlist Schedule"
    ET.SubElement(channel, "link").text = PAGES_URL
    ET.SubElement(channel, "description").text = (
        "Weekly anime airtimes in America/Chicago."
    )
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(now.astimezone(timezone.utc))

    if item is not None:
        title, description, guid, pub_date = item
        entry = ET.SubElement(channel, "item")
        ET.SubElement(entry, "title").text = title
        ET.SubElement(entry, "link").text = PAGES_URL
        ET.SubElement(entry, "description").text = description
        ET.SubElement(entry, "pubDate").text = pub_date
        ET.SubElement(entry, "guid", {"isPermaLink": "false"}).text = guid

    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def current_guid(feed_path: Path) -> str | None:
    if not feed_path.exists():
        return None
    root = ET.parse(feed_path).getroot()
    guid = root.findtext("./channel/item/guid")
    return guid


def publish_digest(
    schedule: dict,
    feed_path: Path,
    cover_urls: dict[str, str],
    now: datetime | None = None,
) -> bool:
    now = now or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    airings = parse_airings(schedule)

    if not feed_path.exists():
        feed_path.parent.mkdir(parents=True, exist_ok=True)
        feed_path.write_bytes(make_feed(now))
        changed = True
    else:
        changed = False

    if not airings:
        return changed

    first_airing = airings[0][1].astimezone(timezone.utc)
    publish_at = first_airing - timedelta(hours=24)
    if now < publish_at or now >= first_airing:
        return changed

    week_start = datetime.fromisoformat(schedule["week_start"]).date()
    guid = f"anime-schedule-{week_start.isoformat()}"
    if current_guid(feed_path) == guid:
        return changed

    week_end = week_start + timedelta(days=6)
    title = (
        f"Weekly Anime Schedule: {week_start.strftime('%b')} "
        f"{week_start.day}-{week_end.day}, {week_start.year}"
    )
    lines = ["This week's anime airtimes (Central Time):", ""]
    for airing, local_time in airings:
        cover_url = cover_urls.get(airing["title"])
        if not cover_url or not cover_url.startswith(ANILIST_CDN_PREFIX):
            raise ValueError(
                f"Missing official AniList cover URL for {airing['title']!r}"
            )
        lines.append(
            f"{local_time.strftime('%A, %b')} {local_time.day} at "
            f"{local_time.strftime('%I:%M %p %Z').lstrip('0')}: {airing['title']}"
        )
        lines.append(f"Cover image: {cover_url}")
        lines.append(f"Schedule source: {airing['source_url']}")
        lines.append("")

    pub_date = format_datetime(now)
    feed_path.write_bytes(
        make_feed(now, (title, "\n".join(lines).rstrip(), guid, pub_date))
    )
    return True


def main() -> None:
    schedule = json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))
    cover_urls = json.loads(COVERS_PATH.read_text(encoding="utf-8"))
    changed = publish_digest(schedule, FEED_PATH, cover_urls)
    print("Feed changed" if changed else "No feed change is due")


if __name__ == "__main__":
    main()