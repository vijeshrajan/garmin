"""Incrementally download read-only Garmin Personal API data as local JSON."""

from __future__ import annotations

import json
import time
from collections import deque
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from garmin_client import DATA_DIR, GarminError, GarminHTTPError, get_json


PROJECT_DIR = Path(__file__).resolve().parent
REQUEST_PAUSE_SECONDS = 0.35
TODAY = date.today()
DEFAULT_START = TODAY - timedelta(days=365)


def load_records(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def save_json(filename: str, value) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / filename
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def parse_date(value) -> date | None:
    if not value:
        return None
    text = str(value)[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def record_date(record: dict) -> date | None:
    for field in (
        "calendarDate",
        "startTimeLocal",
        "startTimeGMT",
        "date",
        "summaryDate",
    ):
        parsed = parse_date(record.get(field))
        if parsed:
            return parsed
    return None


def newest_date(records: list[dict]) -> date | None:
    dates = [item_date for item in records if (item_date := record_date(item))]
    return max(dates) if dates else None


def activity_key(record: dict) -> str:
    activity_id = record.get("activityId") or record.get("id")
    if activity_id is not None:
        return f"id:{activity_id}"
    return "fallback:" + "|".join(
        str(record.get(field) or "")
        for field in ("startTimeLocal", "activityName", "distance", "duration")
    )


def merge_unique(
    old: list[dict], new: list[dict], key_function
) -> list[dict]:
    merged = {key_function(item): item for item in old if isinstance(item, dict)}
    for item in new:
        if isinstance(item, dict):
            merged[key_function(item)] = item
    return list(merged.values())


def date_key(record: dict) -> str:
    item_date = record_date(record)
    if item_date:
        return item_date.isoformat()
    return json.dumps(record, sort_keys=True, default=str)


def extract_list(payload, preferred_keys: tuple[str, ...]) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in preferred_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def pull_activities(start_date: date) -> list[dict]:
    filename = "activities.json"
    existing = load_records(filename)
    known = {activity_key(item) for item in existing}
    downloaded: list[dict] = []
    offset = 0

    print("Activities:")
    while True:
        path = (
            "/activitylist-service/activities/search/activities?"
            + urlencode({"start": offset, "limit": 20})
        )
        page = get_json(path)
        if not isinstance(page, list):
            raise GarminError("Garmin returned an unexpected activity list.")

        page_items = [item for item in page if isinstance(item, dict)]
        reached_known = bool(existing) and any(
            activity_key(item) in known for item in page_items
        )
        in_range = [
            item
            for item in page_items
            if (record_date(item) is None or record_date(item) >= start_date)
        ]
        downloaded.extend(item for item in in_range if activity_key(item) not in known)
        print(f"  Checked {offset + 1}-{offset + len(page_items)}; {len(downloaded)} new")

        oldest = min(
            (item_date for item in page_items if (item_date := record_date(item))),
            default=None,
        )
        if len(page_items) < 20 or reached_known or (oldest and oldest < start_date):
            break
        offset += 20
        time.sleep(REQUEST_PAUSE_SECONDS)

    merged = merge_unique(existing, downloaded, activity_key)
    merged = [
        item for item in merged if record_date(item) is None or record_date(item) >= start_date
    ]
    merged.sort(key=lambda item: str(item.get("startTimeLocal") or ""), reverse=True)
    save_json(filename, merged)
    return merged


def split_ranges(start_date: date, end_date: date, maximum_days: int):
    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(cursor + timedelta(days=maximum_days - 1), end_date)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def pull_dated_dataset(
    *,
    label: str,
    filename: str,
    start_date: date,
    end_date: date,
    maximum_days: int,
    path_builder,
    response_keys: tuple[str, ...],
) -> list[dict]:
    existing = load_records(filename)
    latest = newest_date(existing)
    fetch_start = max(start_date, latest) if latest else start_date
    if fetch_start > end_date:
        return existing

    queue = deque(split_ranges(fetch_start, end_date, maximum_days))
    downloaded: list[dict] = []
    print(f"{label}:")
    while queue:
        chunk_start, chunk_end = queue.popleft()
        print(f"  {chunk_start.isoformat()} to {chunk_end.isoformat()}...", end=" ", flush=True)
        try:
            payload = get_json(path_builder(chunk_start, chunk_end))
        except GarminHTTPError as exc:
            span_days = (chunk_end - chunk_start).days + 1
            if exc.status == 500 and span_days > 1:
                midpoint = chunk_start + timedelta(days=(span_days // 2) - 1)
                print("response too large; splitting")
                queue.appendleft((midpoint + timedelta(days=1), chunk_end))
                queue.appendleft((chunk_start, midpoint))
                continue
            raise

        items = extract_list(payload, response_keys)
        downloaded.extend(items)
        print(f"{len(items)} records")
        time.sleep(REQUEST_PAUSE_SECONDS)

    merged = merge_unique(existing, downloaded, date_key)
    merged = [
        item for item in merged if record_date(item) is None or record_date(item) >= start_date
    ]
    merged.sort(key=lambda item: date_key(item))
    save_json(filename, merged)
    return merged


def pull_singletons(end_date: date) -> None:
    print("Fitness age:")
    try:
        fitness_age = get_json(
            f"/fitnessage-service/fitnessage/v2/{end_date.isoformat()}"
        )
        save_json("fitness_age.json", fitness_age)
        print("  Saved")
    except GarminHTTPError as exc:
        if exc.status in {400, 404}:
            save_json("fitness_age.json", {})
            print("  No fitness-age record available")
        else:
            raise
    time.sleep(REQUEST_PAUSE_SECONDS)

    print("Heart-rate zones:")
    try:
        zones = get_json("/biometric-service/heartRateZones/v2")
        save_json("heart_rate_zones.json", zones)
        print("  Saved")
    except GarminHTTPError as exc:
        if exc.status in {400, 404}:
            save_json("heart_rate_zones.json", {})
            print("  No heart-rate zones available")
        else:
            raise


def dataset_range(*groups: list[dict]) -> tuple[date | None, date | None]:
    dates = [
        item_date
        for group in groups
        for item in group
        if (item_date := record_date(item))
    ]
    return (min(dates), max(dates)) if dates else (None, None)


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    start_date = DEFAULT_START
    end_date = TODAY
    print(f"Pulling Garmin data from {start_date.isoformat()} to {end_date.isoformat()}")
    print("Only new or most-recent records are requested when data already exists.\n")

    try:
        activities = pull_activities(start_date)
        daily = pull_dated_dataset(
            label="Daily summaries",
            filename="daily_summaries.json",
            start_date=start_date,
            end_date=end_date,
            maximum_days=60,
            path_builder=lambda start, end: (
                "/usersummary-service/v2/dailysummaries?"
                + urlencode({"startDate": start.isoformat(), "endDate": end.isoformat()})
            ),
            response_keys=("data", "dailySummaries"),
        )
        sleep = pull_dated_dataset(
            label="Sleep",
            filename="sleep.json",
            start_date=start_date,
            end_date=end_date,
            maximum_days=31,
            path_builder=lambda start, end: (
                "/sleep-service/sleep/dailySleepSummariesByDate?"
                + urlencode({"startDate": start.isoformat(), "endDate": end.isoformat()})
            ),
            response_keys=("dailySleepSummaries", "data", "sleepSummaries"),
        )
        hrv = pull_dated_dataset(
            label="HRV",
            filename="hrv.json",
            start_date=start_date,
            end_date=end_date,
            maximum_days=366,
            path_builder=lambda start, end: (
                f"/hrv-service/hrv/daily/{start.isoformat()}/{end.isoformat()}"
            ),
            response_keys=("hrvSummaries", "data"),
        )
        weight = pull_dated_dataset(
            label="Weight",
            filename="weight.json",
            start_date=start_date,
            end_date=end_date,
            maximum_days=366,
            path_builder=lambda start, end: (
                f"/weight-service/weight/range/{start.isoformat()}/{end.isoformat()}"
            ),
            response_keys=("dailyWeightSummaries", "data"),
        )
        pull_singletons(end_date)
    except GarminError as exc:
        print(f"\nPull failed: {exc}")
        return 1

    first_date, last_date = dataset_range(activities, daily, sleep, hrv, weight)
    print("\nPull complete")
    print(f"  Activities: {len(activities)}")
    print(f"  Daily summaries: {len(daily)} days")
    print(f"  Sleep summaries: {len(sleep)} nights")
    print(f"  HRV summaries: {len(hrv)} days")
    print(f"  Weight summaries: {len(weight)} days")
    if first_date and last_date:
        print(f"  Data range: {first_date.isoformat()} to {last_date.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

