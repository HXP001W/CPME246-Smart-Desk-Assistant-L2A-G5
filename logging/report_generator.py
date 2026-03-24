#This is the skeleton code for the report generator. It loads all logs for a given session, summarizes them, and saves a report. 
#The summarization is basic and can be expanded with more detailed analysis as needed.
#Save this as: reporting/report_generator.py

import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any


def load_session_logs(log_dir: str, session_id: str) -> list[dict[str, Any]]:
    """
    Load all .jsonl log files for a given session_id from the log directory.
    """
    events: list[dict[str, Any]] = []

    if not os.path.exists(log_dir):
        return events

    for filename in os.listdir(log_dir):
        if not filename.startswith(session_id) or not filename.endswith(".jsonl"):
            continue

        file_path = os.path.join(log_dir, filename)

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"Warning: skipped invalid JSON line in {file_path}")

    # Sort by timestamp if available
    events.sort(key=lambda e: e.get("timestamp", ""))
    return events


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Create a basic summary from all session events.
    This is intentionally simple and can be expanded later.
    """
    summary: dict[str, Any] = {
        "total_events": len(events),
        "modules_seen": [],
        "event_type_counts": {},
        "module_event_counts": {},
        "users_detected": [],
        "warnings_triggered": 0,
        "punishment_ready_count": 0,
        "water_gun_trigger_count": 0,
        "phone_detect_count": 0,
        "light_changes": 0,
        "temperature_readings": [],
        "noise_readings": [],
        "light_readings": []
    }

    modules = Counter()
    event_types = Counter()
    module_event_counts = defaultdict(Counter)
    users_detected = set()

    for event in events:
        module = event.get("module", "unknown")
        event_type = event.get("event_type", "unknown")
        value = event.get("value")
        details = event.get("details", {})

        modules[module] += 1
        event_types[event_type] += 1
        module_event_counts[module][event_type] += 1

        if event_type == "user_detected":
            users_detected.add(str(value))

        if event_type == "warning_triggered":
            summary["warnings_triggered"] += 1

        if event_type == "punishment_ready":
            summary["punishment_ready_count"] += 1

        if event_type == "water_gun_triggered":
            summary["water_gun_trigger_count"] += 1

        if event_type == "phone_detected":
            summary["phone_detect_count"] += 1

        if event_type == "light_changed":
            summary["light_changes"] += 1

        if event_type == "temperature_reading":
            reading = details.get("celsius")
            if reading is not None:
                summary["temperature_readings"].append(reading)

        if event_type == "noise_reading":
            reading = details.get("db")
            if reading is not None:
                summary["noise_readings"].append(reading)

        if event_type == "light_reading":
            reading = details.get("lux")
            if reading is not None:
                summary["light_readings"].append(reading)

    summary["modules_seen"] = sorted(modules.keys())
    summary["event_type_counts"] = dict(event_types)
    summary["module_event_counts"] = {
        module: dict(counter) for module, counter in module_event_counts.items()
    }
    summary["users_detected"] = sorted(users_detected)

    # Simple averages
    summary["avg_temperature_c"] = average_or_none(summary["temperature_readings"])
    summary["avg_noise_db"] = average_or_none(summary["noise_readings"])
    summary["avg_light_lux"] = average_or_none(summary["light_readings"])

    return summary


def average_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def save_summary(summary: dict[str, Any], output_dir: str, session_id: str) -> str:
    """
    Save the summary as a JSON file.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{session_id}_summary.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return output_path


def print_summary(summary: dict[str, Any]) -> None:
    """
    Human-readable console output.
    """
    print("\n===== STUDY SESSION SUMMARY =====")
    print(f"Total events: {summary['total_events']}")
    print(f"Modules seen: {', '.join(summary['modules_seen'])}")
    print(f"Users detected: {', '.join(summary['users_detected']) if summary['users_detected'] else 'None'}")
    print(f"Warnings triggered: {summary['warnings_triggered']}")
    print(f"Punishment-ready count: {summary['punishment_ready_count']}")
    print(f"Water gun trigger count: {summary['water_gun_trigger_count']}")
    print(f"Phone detect count: {summary['phone_detect_count']}")
    print(f"Light changes: {summary['light_changes']}")
    print(f"Average temperature (C): {summary['avg_temperature_c']}")
    print(f"Average noise (dB): {summary['avg_noise_db']}")
    print(f"Average light (lux): {summary['avg_light_lux']}")
    print("\nEvent type counts:")
    for event_type, count in summary["event_type_counts"].items():
        print(f"  - {event_type}: {count}")


def main() -> None:
    """
    Example standalone entry point.
    Change the session_id to the one you want to summarize.
    """
    session_id = input("Enter session_id: ").strip()
    log_dir = "logs"
    output_dir = "reports"

    events = load_session_logs(log_dir=log_dir, session_id=session_id)
    if not events:
        print("No logs found for that session.")
        return

    summary = summarize_events(events)
    output_path = save_summary(summary, output_dir=output_dir, session_id=session_id)
    print_summary(summary)
    print(f"\nSaved summary to: {output_path}")


if __name__ == "__main__":
    main()