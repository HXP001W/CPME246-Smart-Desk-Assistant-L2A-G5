#This is the draft for the main logger. Save this as: core/logger.py

import json
import os
from datetime import datetime
from typing import Any, Optional


class EventLogger:
    """
    Shared logger utility for the Smart Desk Assistant project.

    Each module can create its own logger instance with:
    - a shared session_id
    - a module name
    - its own log file path

    Logs are written in JSON Lines format (.jsonl), one event per line.
    """

    def __init__(self, session_id: str, module_name: str, log_dir: str = "logs") -> None:
        self.session_id = session_id
        self.module_name = module_name
        self.log_dir = log_dir

        os.makedirs(self.log_dir, exist_ok=True)
        self.log_path = os.path.join(
            self.log_dir,
            f"{self.session_id}_{self.module_name}.jsonl"
        )

    def log_event(
        self,
        event_type: str,
        value: Any,
        details: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Write one structured log event.
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "module": self.module_name,
            "event_type": event_type,
            "value": value,
            "details": details or {}
        }

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def log_state_update(
        self,
        state_name: str,
        state_value: Any,
        details: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Convenience wrapper for logging common state updates.
        """
        self.log_event(
            event_type="state_update",
            value=state_value,
            details={
                "state_name": state_name,
                **(details or {})
            }
        )