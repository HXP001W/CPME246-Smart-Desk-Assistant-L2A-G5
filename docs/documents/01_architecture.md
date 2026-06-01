# System Architecture

## Purpose

The Smart Desk Assistant is organized as a modular embedded/software system. Each subsystem is responsible for one part of the overall workflow, and the modules communicate through function calls, subprocess environment variables, HTTP routes, and shared JSONL logs.

The most important architectural decision is that **`UI.py` acts as the main controller**, while the real-time computer vision logic runs in a separate script, **`combined_focus_prototype_v5.py`**.

## Main Subsystems

```text
┌─────────────────────────────┐
│ User / Browser              │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ UI.py                       │
│ Flask Web UI + Controller   │
└──────┬────────┬───────┬─────┘
       │        │       │
       │        │       └────────────────────┐
       │        │                            │
       ▼        ▼                            ▼
┌──────────┐ ┌────────────────────────┐ ┌──────────────────┐
│Identify.py│ │combined_focus_..._v5.py│ │Hardware Control  │
│DeepFace   │ │Real-time Focus Engine  │ │LED / buzzer/pump │
└────┬─────┘ └──────────────┬─────────┘ └─────────┬────────┘
     │                      │                     │
     ▼                      ▼                     ▼
┌──────────┐          ┌──────────────┐      ┌──────────────┐
│testmain.py│         │logger.py     │      │GPIO Outputs  │
│User DB    │         │JSONL events  │      │Physical demo │
└────┬─────┘          └──────┬───────┘      └──────────────┘
     │                       │
     ▼                       ▼
┌──────────┐          ┌──────────────────┐
│User.py   │          │report_generator.py│
│Profiles  │          │Session reports   │
└──────────┘          └──────────────────┘
```

## Runtime Workflow

1. The user opens the Flask UI from `UI.py`.
2. The user either continues as a guest or runs face recognition.
3. Face recognition is handled by `Identify.py`, which uses DeepFace to compare a camera capture against saved profile photos.
4. User profile data is loaded through `testmain.py` and represented with the `User` class from `User.py`.
5. The user starts a focus session in the UI.
6. `UI.py` creates a session ID and starts `combined_focus_prototype_v5.py` as a subprocess.
7. The focus detection script receives session/user information through environment variables:
   - `FOCUS_SESSION_ID`
   - `FOCUS_USER_ID`
   - `FOCUS_USER_NAME`
8. The detection script monitors webcam, posture, phone presence, and app/window status.
9. The detection script logs events through `logger.py`.
10. If the user reaches a warning or punishment state, the script can trigger the UI's buzzer/pump endpoints.
11. After the session, `report_generator.py` loads all session logs and creates a readable summary.
12. The UI can display the generated session report.

## Why the Design Is Modular

The project uses multiple files instead of placing all logic into one script because the system has several different responsibilities:

- UI and user interaction
- facial recognition
- real-time focus monitoring
- hardware control
- logging
- report generation

This separation makes the project easier to test, explain, debug, and divide among team members.
