#Session ID helper, Save this as: core/session_utils.py

from datetime import datetime


def create_session_id(prefix: str = "study_session") -> str:
    """
    Create a readable session ID such as:
    2026-03-23_16-52-10_study_session
    """
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{now}_{prefix}"

#Example usage in main.py:
from core.session_utils import create_session_id

session_id = create_session_id()
print("Session ID:", session_id)