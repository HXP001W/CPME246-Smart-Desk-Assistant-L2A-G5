#This is the draft code that could be used in the distraction detection module.

from core.logger import EventLogger


def run_distraction_module(session_id: str) -> None:
    logger = EventLogger(session_id=session_id, module_name="distraction_detection")

    logger.log_event(
        event_type="module_started",
        value="started",
        details={"message": "Distraction detection module initialized"}
    )

    # Example state update
    logger.log_state_update(
        state_name="combined_state",
        state_value="FOCUSED",
        details={
            "attention_state": "FOCUSED",
            "posture_state": "OK",
            "phone_present": False
        }
    )

    # Example warning event
    logger.log_event(
        event_type="warning_triggered",
        value="distraction",
        details={
            "attention_state": "LOOKING_LEFT",
            "posture_state": "OK",
            "phone_present": False,
            "duration_seconds": 5.3
        }
    )