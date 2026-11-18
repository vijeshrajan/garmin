"""Pure, auditable planning and training-decision helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import median
from typing import Any, Iterable


def measured(value: Any) -> float | None:
    """Return a finite non-negative number; Garmin negatives mean not measured."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 and value == value and abs(value) != float("inf") else None


def median_or_none(values: Iterable[Any]) -> float | None:
    cleaned = [value for item in values if (value := measured(item)) is not None]
    return float(median(cleaned)) if cleaned else None


def decide(today: dict, baselines: dict, checkin: dict, planned: list[dict]) -> dict:
    """Return a deterministic GO/MODIFY/REST/STOP training decision.

    Rules are intentionally ordered. Missing inputs never count as favourable.
    """
    rhr = measured(today.get("rhr"))
    hrv = measured(today.get("hrv"))
    sleep_h = measured(today.get("sleep_h"))
    rhr_base = measured(baselines.get("rhr_30d_median"))
    hrv_low = measured(baselines.get("hrv_balanced_low"))
    sleep_need_h = measured(baselines.get("sleep_need_h"))
    body = str(checkin.get("body") or "normal").strip().lower()
    missing = []
    for label, value in (("resting heart rate", rhr), ("overnight HRV", hrv), ("sleep", sleep_h)):
        if value is None:
            missing.append(label)

    reasons = []
    verdict = "GO"
    fired = [6]
    severe = {"chest pain, fainting, severe breathlessness", "red flag symptoms"}
    if body in severe:
        verdict, fired = "STOP", [1]
        reasons.append({"signal": "Check-in", "today": "Red-flag symptom", "baseline": "—", "read": "Seek medical care; do not train."})
    elif body in {"ill or in pain", "ill", "in pain"}:
        verdict, fired = "REST", [2]
        reasons.append({"signal": "Check-in", "today": "Ill or in pain", "baseline": "Normal", "read": "Walk only."})
    elif rhr is not None and rhr_base is not None and rhr >= rhr_base + 10:
        verdict, fired = "REST", [3]
        reasons.append({"signal": "Resting HR", "today": f"{rhr:.0f} bpm", "baseline": f"{rhr_base:.0f} bpm", "read": f"+{rhr-rhr_base:.0f}; verify the reading on the watch."})
    else:
        modify_reasons = []
        if rhr is not None and rhr_base is not None and rhr >= rhr_base + 5:
            modify_reasons.append((4, {"signal": "Resting HR", "today": f"{rhr:.0f} bpm", "baseline": f"{rhr_base:.0f} bpm", "read": f"+{rhr-rhr_base:.0f}; reduce training strain."}))
        if hrv is not None and hrv_low is not None and hrv < hrv_low:
            modify_reasons.append((4, {"signal": "Overnight HRV", "today": f"{hrv:.0f} ms", "baseline": f"{hrv_low:.0f} ms balanced low", "read": "Below personal balanced range."}))
        leg_or_long = any(item.get("kind") == "long_run" or "leg" in str(item.get("label", "")).lower() or "lower" in str(item.get("label", "")).lower() for item in planned)
        if sleep_h is not None and sleep_h < 6:
            modify_reasons.append((5, {"signal": "Sleep", "today": f"{sleep_h:.1f} h", "baseline": f"need {sleep_need_h:.1f} h" if sleep_need_h else "personal need", "read": "Below 6 hours."}))
        if body == "sore / heavy legs" and leg_or_long:
            modify_reasons.append((5, {"signal": "Check-in", "today": "Sore / heavy legs", "baseline": "Leg day or long run", "read": "Reduce lower-body strain."}))
        if modify_reasons:
            verdict = "MODIFY"
            fired = sorted(set(rule for rule, _ in modify_reasons))
            reasons.extend(reason for _, reason in modify_reasons)

    if not reasons:
        reasons.append({"signal": "Rule check", "today": "No downgrade rule fired", "baseline": "Personal ranges", "read": "Proceed with the planned session."})
    if today.get("rhr_partial") and rhr is not None:
        reasons.append({"signal": "Reading quality", "today": "Partial-day RHR", "baseline": "Complete-day history", "read": "Verify the reading on the watch."})
    if hrv is None:
        reasons.append({"signal": "Overnight HRV", "today": "Not measured", "baseline": f"{hrv_low:.0f} ms balanced low" if hrv_low else "Personal range", "read": "Not scored."})
    if measured(today.get("stress")) is None:
        reasons.append({"signal": "Stress", "today": "Not measured", "baseline": "—", "read": "Not scored."})

    confidence = "high" if not missing else "medium" if len(missing) == 1 else "low"
    labels = [item.get("label", "Session") for item in planned]
    original = " + ".join(labels) if labels else "Rest"
    if verdict == "STOP":
        adjusted = "No session shown"
    elif verdict == "REST":
        adjusted = "Walk only"
    elif verdict == "MODIFY":
        strength = next((item for item in planned if item.get("kind") == "strength"), None)
        adjusted_parts = []
        if strength:
            adjusted_parts.append(f"{strength.get('label')}: 2 sets per exercise, RIR 3, drop last 2 exercises")
        if any(item.get("kind") in {"easy_run", "long_run"} for item in planned):
            adjusted_parts.append("replace run with a 30-min walk")
        adjusted = "; ".join(adjusted_parts) or "30-min walk"
    else:
        adjusted = original
    return {"verdict": verdict, "originalSession": original, "adjustedSession": adjusted, "reasons": reasons[:4], "confidence": confidence, "missingInputs": missing, "rulesFired": fired}


def activity_day(activity: dict) -> date | None:
    try:
        return datetime.fromisoformat(str(activity.get("startTimeLocal", "")).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def activity_key(activity: dict) -> str:
    value = activity.get("activityType") or {}
    return str(value.get("typeKey") if isinstance(value, dict) else value).lower()


def easy_run_too_hard(activity: dict, cap: float = 152) -> bool:
    avg_hr = measured(activity.get("averageHR"))
    zones = [measured(activity.get(f"hrTimeInZone_{index}")) or 0 for index in range(1, 6)]
    zone_total = sum(zones)
    hard_share = sum(zones[2:]) / zone_total if zone_total else 0
    return (avg_hr is not None and avg_hr > cap) or hard_share > .20


def planned_sessions(plan: dict, on_date: date) -> list[dict]:
    weekday = on_date.strftime("%A").lower()
    row = next((item for item in plan.get("weekly_schedule", []) if item.get("day") == weekday), {})
    result = []
    strength_id = row.get("strength")
    if strength_id:
        session = plan.get("strength_sessions", {}).get(strength_id, {})
        result.append({"id": strength_id, "kind": "strength", "label": session.get("label", strength_id), "details": session})
    run_id = row.get("run")
    if run_id:
        run = plan.get("runs", {}).get(run_id, {})
        result.append({"id": run_id, "kind": "long_run" if run_id == "long_run" else "easy_run", "label": run.get("label", run_id), "details": run})
    if not result:
        result.append({"id": "rest", "kind": "rest", "label": "Rest", "details": {"note": row.get("note", "Recovery")}})
    return result


def match_week(plan: dict, activities: list[dict], week_start: date, today: date) -> dict:
    """Match each planned session separately to same-day Garmin activities."""
    by_day: dict[date, list[dict]] = {}
    for activity in activities:
        if (day := activity_day(activity)) is not None:
            by_day.setdefault(day, []).append(activity)
    days, planned_count, done_count, run_done, run_planned = [], 0, 0, 0.0, 0.0
    easy_ok, easy_total = 0, 0
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        available = list(by_day.get(day, []))
        rows = []
        for session in planned_sessions(plan, day):
            if session["kind"] == "rest":
                rows.append({**session, "status": "rest", "activity": None})
                continue
            planned_count += 1
            if session["kind"] == "strength":
                match = next((a for a in available if "strength" in activity_key(a)), None)
            elif session["kind"] == "easy_run":
                match = next((a for a in available if activity_key(a) in {"treadmill_running", "running"}), None)
                run_planned += measured(session["details"].get("target_distance_km")) or 0
            else:
                match = next((a for a in available if activity_key(a) in {"running", "trail_running"}), None)
                run_planned += measured(session["details"].get("target_distance_km")) or 0
            if match:
                available.remove(match)
                duration_min = (measured(match.get("duration")) or 0) / 60
                distance_km = (measured(match.get("distance")) or 0) / 1000
                too_hard = session["kind"] == "easy_run" and easy_run_too_hard(match, measured(session["details"].get("hr_cap_bpm")) or 152)
                target_km = measured(session["details"].get("target_distance_km")) or 0
                partial = (session["kind"] == "strength" and duration_min < 20) or (session["kind"] in {"easy_run", "long_run"} and target_km and distance_km < target_km * .7 and not too_hard)
                status = "partial" if partial else "done"
                done_count += 1 if status == "done" else .5
                if session["kind"] in {"easy_run", "long_run"}:
                    run_done += distance_km
                if session["kind"] == "easy_run":
                    easy_total += 1
                    easy_ok += 0 if too_hard else 1
                rows.append({**session, "status": status, "activity": {"name": match.get("activityName"), "type": activity_key(match), "duration_min": round(duration_min), "distance_km": round(distance_km, 1), "avg_hr": measured(match.get("averageHR")), "too_hard": too_hard}})
            else:
                status = "missed" if day < today else "planned"
                rows.append({**session, "status": status, "activity": None})
        for extra in available:
            rows.append({"id": f"extra-{extra.get('activityId', '')}", "kind": "extra", "label": extra.get("activityName") or activity_key(extra).replace("_", " ").title(), "status": "extra", "activity": {"type": activity_key(extra), "duration_min": round((measured(extra.get('duration')) or 0)/60), "distance_km": round((measured(extra.get('distance')) or 0)/1000, 1)}})
        days.append({"date": day.isoformat(), "label": day.strftime("%a %d"), "today": day == today, "sessions": rows})
    return {"days": days, "planned": planned_count, "done": done_count, "adherence": round(done_count/planned_count*100) if planned_count else None, "runKmDone": round(run_done, 1), "runKmPlanned": round(run_planned, 1), "easyRunsOk": easy_ok, "easyRunsTotal": easy_total}


def epley_1rm(weight_kg: float, reps: int) -> float | None:
    return round(weight_kg * (1 + reps / 30), 1) if weight_kg > 0 and 1 <= reps <= 10 else None

