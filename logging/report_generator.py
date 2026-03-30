import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def load_session_logs(log_dir: str | Path, session_id: str) -> list[dict[str, Any]]:
    """Load all JSONL events for one session id."""
    log_path = Path(log_dir)
    events: list[dict[str, Any]] = []

    if not log_path.exists():
        return events

    for file_path in sorted(log_path.glob(f"{session_id}_*.jsonl")):
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    events.sort(key=lambda e: e.get("timestamp", ""))
    return events


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "total_events": len(events),
        "session_id": events[0].get("session_id") if events else "",
        "study_duration_seconds": 0,
        "water_pump_trigger_count": 0,
        "distracting_app_open_count": 0,
        "break_count": 0,
        "break_total_seconds": 0.0,
        "distraction_total_seconds": 0.0,
        "bad_posture_total_seconds": 0.0,
        "bad_posture_event_count": 0,
        "distraction_reason_counts": {},
        "active_window_titles": [],
        "event_type_counts": {},
        "module_event_counts": {},
        "users_seen": [],
        "user_names_seen": [],
        "primary_user_name": "",
        "event_duration_totals": {},
    }

    if not events:
        return summary

    event_type_counts: Counter[str] = Counter()
    module_event_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    distraction_reason_counts: Counter[str] = Counter()
    event_duration_totals: defaultdict[str, float] = defaultdict(float)
    users_seen: set[str] = set()
    user_names_seen: set[str] = set()
    active_window_titles: set[str] = set()

    first_ts = _parse_timestamp(events[0].get("timestamp", ""))
    last_ts = _parse_timestamp(events[-1].get("timestamp", ""))

    focus_start_ts: datetime | None = None
    focus_end_ts: datetime | None = None
    pump_trigger_keys: set[tuple[Any, ...]] = set()
    last_app_focus_state = "UNKNOWN_APP"
    distracting_app_open_count = 0

    for event in events:
        module = str(event.get("module", "unknown"))
        event_type = str(event.get("event_type", "unknown"))
        details = event.get("details", {}) or {}
        user_id = event.get("user_id")
        user_name = event.get("user_name")
        event_duration_seconds = event.get("event_duration_seconds")

        event_type_counts[event_type] += 1
        module_event_counts[module][event_type] += 1

        if user_id is not None:
            users_seen.add(str(user_id))
        if user_name:
            user_names_seen.add(str(user_name))

        if event_duration_seconds is not None:
            try:
                event_duration_totals[event_type] += float(event_duration_seconds)
            except (TypeError, ValueError):
                pass

        if event_type == "app_focus_changed":
            current_app_state = str(event.get("value", "UNKNOWN_APP"))
            if current_app_state == "DISTRACTING_APP" and last_app_focus_state != "DISTRACTING_APP":
                distracting_app_open_count += 1

            last_app_focus_state = current_app_state

            window_title = str(details.get("active_window_title") or "").strip()
            if window_title and window_title != "UNAVAILABLE":
                active_window_titles.add(window_title)

        if event_type == "water_pump_triggered":
            trigger_count = details.get("trigger_count")
            reason = str(details.get("reason") or event.get("value") or "unknown")
            ts = _parse_timestamp(str(event.get("timestamp", "")))

            # UI route mirrors pump triggers from detection module; skip mirrored events.
            if (
                module == "hardware_control"
                and str(details.get("source", "")) == "ui_fire_pump_route"
                and reason == "persistent_distraction"
            ):
                continue

            if trigger_count is not None:
                trigger_key = ("trigger_count", str(trigger_count))
            elif ts is not None:
                trigger_key = ("time_reason", int(ts.timestamp()), reason)
            else:
                trigger_key = ("fallback", str(event.get("timestamp", "")), reason)

            pump_trigger_keys.add(trigger_key)

        if event_type in {"warning_triggered", "punishment_ready", "water_pump_triggered", "focus_lost"}:
            reason = str(details.get("reason") or event.get("value") or "unknown")
            if reason == "DISTRACTING APP":
                continue
            distraction_reason_counts[reason] += 1

        if event_type == "break_started":
            summary["break_count"] += 1

        if event_type == "break_ended":
            try:
                summary["break_total_seconds"] += float(details.get("actual_duration_seconds") or details.get("duration_seconds") or 0.0)
            except (TypeError, ValueError):
                pass

        if event_type == "distraction_ended":
            try:
                summary["distraction_total_seconds"] += float(details.get("duration_seconds") or event_duration_seconds or 0.0)
            except (TypeError, ValueError):
                pass

        if event_type == "bad_posture_started":
            summary["bad_posture_event_count"] += 1

        if event_type == "bad_posture_ended":
            try:
                summary["bad_posture_total_seconds"] += float(details.get("duration_seconds") or event_duration_seconds or 0.0)
            except (TypeError, ValueError):
                pass

        if event_type == "session_started":
            ts = _parse_timestamp(event.get("timestamp", ""))
            if ts is not None and (focus_start_ts is None or ts < focus_start_ts):
                focus_start_ts = ts

        if event_type in {"session_ended", "session_stopped"}:
            ts = _parse_timestamp(event.get("timestamp", ""))
            if ts is not None and (focus_end_ts is None or ts > focus_end_ts):
                focus_end_ts = ts

    if focus_start_ts is not None and focus_end_ts is not None and focus_end_ts >= focus_start_ts:
        summary["study_duration_seconds"] = round((focus_end_ts - focus_start_ts).total_seconds(), 2)
    elif first_ts is not None and last_ts is not None and last_ts >= first_ts:
        summary["study_duration_seconds"] = round((last_ts - first_ts).total_seconds(), 2)

    summary["distraction_reason_counts"] = dict(distraction_reason_counts)
    summary["distraction_reason_counts"]["DISTRACTING APP"] = distracting_app_open_count
    summary["distracting_app_open_count"] = distracting_app_open_count
    summary["water_pump_trigger_count"] = len(pump_trigger_keys)
    summary["active_window_titles"] = sorted(active_window_titles)
    summary["event_type_counts"] = dict(event_type_counts)
    summary["module_event_counts"] = {
        module: dict(counter)
        for module, counter in module_event_counts.items()
    }
    summary["users_seen"] = sorted(users_seen)
    summary["user_names_seen"] = sorted(user_names_seen)
    summary["primary_user_name"] = summary["user_names_seen"][0] if summary["user_names_seen"] else ""
    summary["event_duration_totals"] = {
        key: round(value, 2) for key, value in sorted(event_duration_totals.items())
    }
    summary["break_total_seconds"] = round(summary["break_total_seconds"], 2)
    summary["distraction_total_seconds"] = round(summary["distraction_total_seconds"], 2)
    summary["bad_posture_total_seconds"] = round(summary["bad_posture_total_seconds"], 2)

    return summary


def save_summary(summary: dict[str, Any], output_dir: str | Path, session_id: str) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    summary_file = output_path / f"{session_id}_summary.json"
    with summary_file.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return summary_file


def print_summary(summary: dict[str, Any]) -> None:
    print("\n===== SMART DESK SESSION SUMMARY =====")
    print(f"Session ID: {summary.get('session_id', '')}")
    print(f"Total events: {summary.get('total_events', 0)}")
    print(f"Study duration (seconds): {summary.get('study_duration_seconds', 0)}")
    print(f"Water pump triggers: {summary.get('water_pump_trigger_count', 0)}")
    print(f"Break count: {summary.get('break_count', 0)}")
    print(f"Break total duration (seconds): {summary.get('break_total_seconds', 0)}")
    print(f"Distraction total duration (seconds): {summary.get('distraction_total_seconds', 0)}")
    print(f"Bad posture total duration (seconds): {summary.get('bad_posture_total_seconds', 0)}")

    users_seen = summary.get("users_seen", [])
    print(f"Users seen: {', '.join(users_seen) if users_seen else 'None'}")
    user_names_seen = summary.get("user_names_seen", [])
    print(f"User names: {', '.join(user_names_seen) if user_names_seen else 'None'}")

    print("Distraction reasons:")
    reason_counts = summary.get("distraction_reason_counts", {})
    if reason_counts:
        for reason, count in reason_counts.items():
            print(f"  - {reason}: {count}")
    else:
        print("  - None")


def generate_html_report(summary: dict[str, Any]) -> str:
    """Generate HTML report from session summary."""
    session_id = summary.get("session_id", "Unknown")
    study_duration = summary.get("study_duration_seconds", 0)
    pump_triggers = summary.get("water_pump_trigger_count", 0)
    break_count = summary.get("break_count", 0)
    break_total_seconds = summary.get("break_total_seconds", 0)
    distraction_total_seconds = summary.get("distraction_total_seconds", 0)
    bad_posture_total_seconds = summary.get("bad_posture_total_seconds", 0)
    
    # Convert study duration to minutes and seconds
    minutes = int(study_duration) // 60
    seconds = int(study_duration) % 60
    duration_str = f"{minutes}m {seconds}s"
    
    primary_user_name = summary.get("primary_user_name", "") or "Unknown"
    
    distraction_reasons = summary.get("distraction_reason_counts", {})
    reason_rows = ""
    for reason, count in sorted(distraction_reasons.items(), key=lambda x: x[1], reverse=True):
        reason_rows += f"<tr><td>{reason}</td><td class='center'>{count}</td></tr>\n"
    
    reason_section = ""
    if distraction_reasons:
        reason_section = f"""
        <div class="section">
            <h2>Distraction Reasons</h2>
            <table>
                <thead>
                    <tr>
                        <th>Reason</th>
                        <th>Count</th>
                    </tr>
                </thead>
                <tbody>
                    {reason_rows}
                </tbody>
            </table>
        </div>
        """
    else:
        reason_section = """
        <div class="section">
            <h2>Distraction Reasons</h2>
            <p class="muted">No distractions recorded.</p>
        </div>
        """
    
    duration_totals = summary.get("event_duration_totals", {})
    duration_rows = ""
    for event_name, seconds in sorted(duration_totals.items(), key=lambda x: x[1], reverse=True):
        duration_rows += f"<tr><td>{event_name}</td><td class='center'>{seconds}</td></tr>\n"

    duration_section = ""
    if duration_totals:
        duration_section = f"""
        <div class=\"section\">
            <h2>Event Duration Totals (seconds)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Event</th>
                        <th>Duration (s)</th>
                    </tr>
                </thead>
                <tbody>
                    {duration_rows}
                </tbody>
            </table>
        </div>
        """

    html = f"""
    <div class="report-card">
        <h2>Session Report</h2>
        <div class="report-content">
            <div class="info-grid">
                <div class="info-item">
                    <span class="label">User Name:</span>
                    <span class="value">{primary_user_name}</span>
                </div>
                <div class="info-item">
                    <span class="label">Session ID:</span>
                    <span class="value">{session_id}</span>
                </div>
                <div class="info-item">
                    <span class="label">Study Duration:</span>
                    <span class="value">{duration_str}</span>
                </div>
                <div class="info-item">
                    <span class="label">Water Pump Triggers:</span>
                    <span class="value">{pump_triggers}</span>
                </div>
                <div class="info-item">
                    <span class="label">Breaks:</span>
                    <span class="value">{break_count} ({break_total_seconds}s)</span>
                </div>
                <div class="info-item">
                    <span class="label">Distraction Time:</span>
                    <span class="value">{distraction_total_seconds}s</span>
                </div>
                <div class="info-item">
                    <span class="label">Bad Posture Time:</span>
                    <span class="value">{bad_posture_total_seconds}s</span>
                </div>
            </div>
            {reason_section}
            {duration_section}
        </div>
    </div>
    """
    
    return html


def load_report_summary(report_dir: str | Path, session_id: str) -> dict[str, Any] | None:
    """Load a previously generated report summary JSON file."""
    report_path = Path(report_dir) / f"{session_id}_summary.json"
    if report_path.exists():
        with report_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate session report from JSONL logs")
    parser.add_argument("session_id", help="Session id to summarize")
    parser.add_argument("--log-dir", default="logging/logs", help="Directory containing JSONL logs")
    parser.add_argument("--output-dir", default="logging/reports", help="Directory for summary outputs")
    args = parser.parse_args()

    events = load_session_logs(args.log_dir, args.session_id)
    if not events:
        print("No logs found for that session.")
        return

    summary = summarize_events(events)
    output_file = save_summary(summary, args.output_dir, args.session_id)
    print_summary(summary)
    print(f"Saved summary: {output_file}")


if __name__ == "__main__":
    main()
