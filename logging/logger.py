import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def create_session_id(prefix: str = "study_session") -> str:
    """Create a readable session id for cross-module correlation."""
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{now}_{prefix}"


def find_user_sessions(log_dir: str | Path, user_id: str | int) -> list[str]:
    """Find all session ids that belong to a given user by scanning JSONL event files."""
    log_path = Path(log_dir)
    sessions: dict[str, datetime | None] = {}
    user_id_str = str(user_id)

    if not log_path.exists():
        return []

    for file_path in log_path.glob("*_*.jsonl"):
        try:
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        if event.get("user_id") == user_id_str:
                            session_id = event.get("session_id")
                            if session_id:
                                ts_str = event.get("timestamp", "")
                                try:
                                    ts = datetime.fromisoformat(ts_str)
                                    if session_id not in sessions or (sessions[session_id] is None or ts < sessions[session_id]):
                                        sessions[session_id] = ts
                                except (ValueError, TypeError):
                                    if session_id not in sessions:
                                        sessions[session_id] = None
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue

    sorted_sessions = sorted(sessions.items(), key=lambda x: (x[1] or datetime.min), reverse=True)
    return [session_id for session_id, _ in sorted_sessions]



class EventLogger:
    """Thread-safe JSONL logger with a shared session id and module name."""

    def __init__(self, session_id: str, module_name: str, log_dir: str | os.PathLike[str]) -> None:
        self.session_id = str(session_id)
        self.module_name = str(module_name)
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / f"{self.session_id}_{self.module_name}.jsonl"
        self._lock = threading.Lock()
        self._session_start_monotonic = time.monotonic()
        self._last_event_monotonic: float | None = None

    def log_event(
        self,
        event_type: str,
        value: Any,
        details: dict[str, Any] | None = None,
        user_id: str | int | None = None,
        user_name: str | None = None,
        duration_seconds: float | None = None,
    ) -> None:
        now_iso = datetime.now().isoformat()
        now_monotonic = time.monotonic()
        session_elapsed_seconds = round(now_monotonic - self._session_start_monotonic, 3)
        since_previous_event_seconds = None
        if self._last_event_monotonic is not None:
            since_previous_event_seconds = round(now_monotonic - self._last_event_monotonic, 3)

        event_duration_seconds = duration_seconds
        safe_details = dict(details or {})
        if event_duration_seconds is None and "duration_seconds" in safe_details:
            try:
                event_duration_seconds = float(safe_details.get("duration_seconds"))
            except (TypeError, ValueError):
                event_duration_seconds = None

        event: dict[str, Any] = {
            "timestamp": now_iso,
            "session_id": self.session_id,
            "module": self.module_name,
            "event_type": event_type,
            "value": value,
            "details": safe_details,
            "session_elapsed_seconds": session_elapsed_seconds,
            "since_previous_event_seconds": since_previous_event_seconds,
        }
        if user_id is not None:
            event["user_id"] = str(user_id)
        if user_name:
            event["user_name"] = str(user_name)
        if event_duration_seconds is not None:
            event["event_duration_seconds"] = round(float(event_duration_seconds), 3)

        self._last_event_monotonic = now_monotonic

        line = json.dumps(event, ensure_ascii=False)
        with self._lock:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def log_state_update(
        self,
        state_name: str,
        state_value: Any,
        details: dict[str, Any] | None = None,
        user_id: str | int | None = None,
        user_name: str | None = None,
        duration_seconds: float | None = None,
    ) -> None:
        payload = {"state_name": state_name}
        if details:
            payload.update(details)
        self.log_event(
            event_type="state_update",
            value=state_value,
            details=payload,
            user_id=user_id,
            user_name=user_name,
            duration_seconds=duration_seconds,
        )