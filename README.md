# Smart Desk Assistant

The **Smart Desk Assistant** is a Raspberry-Pi-based study companion that combines a web UI, computer vision, facial recognition, application monitoring, logging, report generation, and hardware feedback.

The goal of the system is to help a user maintain focus during timed study sessions. During a session, the system monitors several signals:

- whether the user's face is visible
- approximate head direction and attention state
- coarse posture state
- whether a phone is detected in the camera view
- whether a distracting application/window is active
- whether the user has stayed distracted long enough to receive a warning or hardware response

The main entry point of the project is **`UI.py`**. It starts the Flask web interface, manages user flow, launches the real-time focus detection process, controls hardware outputs, and connects to the logging/reporting system.

## Main Features

- Web-based user interface built with Flask
- Guest and registered-user workflow
- Facial recognition with DeepFace
- Real-time webcam-based focus monitoring with OpenCV and MediaPipe
- Posture, phone, and app/window distraction detection
- LED brightness feedback based on a light sensor
- Buzzer and water pump feedback for warnings and persistent distraction
- Structured JSONL logging
- Session report generation

## High-Level System Flow

```text
User
  ↓
Flask Web UI (UI.py)
  ↓
User recognition / guest mode
  ↓
Focus session starts
  ↓
combined_focus_prototype_v5.py monitors:
  - face attention
  - posture
  - phone detection
  - active app/window
  ↓
Decision engine produces:
  - FOCUSED
  - DISTRACTED
  - PHONE DETECTED
  - HEAD DOWN
  - POSTURE WARNING
  - DISTRACTING APP
  ↓
System response:
  - visual status window
  - UI warning
  - buzzer
  - water pump trigger
  - JSONL event logs
  ↓
report_generator.py creates a readable session summary
```

## Repository Guide

Recommended documentation files:

- [`docs/01_architecture.md`](docs/01_architecture.md) — overall system architecture
- [`docs/02_file_map.md`](docs/02_file_map.md) — explanation of each Python file
- [`docs/03_distraction_detection_v5.md`](docs/03_distraction_detection_v5.md) — detailed explanation of the focus/distraction detection engine
- [`docs/04_logging_and_reports.md`](docs/04_logging_and_reports.md) — logging format and report generation
- [`docs/05_tools_and_dependencies.md`](docs/05_tools_and_dependencies.md) — software tools and libraries
- [`docs/06_presentation_notes.md`](docs/06_presentation_notes.md) — presentation and Q&A notes

## Main Runtime Files

| File                             | Purpose                                                         |
|----------------------------------|-----------------------------------------------------------------|
| `UI.py`                          | Main Flask UI, session manager, hardware control, report viewer |
| `combined_focus_prototype_v5.py` | Real-time focus/distraction/posture/app detection               |
| `Identify.py`                    | DeepFace-based one-time facial recognition                      |
| `testmain.py`                    | User registration, profile loading/saving, photo capture        |
| `User.py`                        | User profile object and command-line profile menu               |
| `logger.py`                      | Thread-safe structured JSONL event logger                       |
| `report_generator.py`            | Session log summarizer and HTML report generator                |
| `sessionid_helper.py`            | Small utility for generating session IDs                        |

## Notes

This project is designed as a prototype. The distraction and posture states are produced by interpretable heuristics, not by a medically validated ergonomic model or full eye-tracking model. The hardware feedback system should be tested carefully and used only in a safe demo configuration.
