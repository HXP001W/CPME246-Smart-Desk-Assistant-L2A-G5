#This is the draft code that could be used under the hardware module to log hardware events like light changes and water gun triggers.

from core.logger import EventLogger


def run_hardware_module(session_id: str) -> None:
    logger = EventLogger(session_id=session_id, module_name="hardware_control")

    logger.log_event(
        event_type="light_changed",
        value="brightness_updated",
        details={
            "old_brightness": 40,
            "new_brightness": 75,
            "reason": "ambient_light_low"
        }
    )

    logger.log_event(
        event_type="water_gun_triggered",
        value="triggered",
        details={
            "duration_ms": 400,
            "reason": "persistent_distraction"
        }
    )