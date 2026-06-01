# File Map and Component Explanations

This document explains the purpose of each main Python file and how the files connect with each other.

---

## `UI.py` — Main Web Interface and System Controller

`UI.py` is the main entry point of the project. It creates a Flask web application and coordinates the rest of the system.

### Main Responsibilities

- Starts the Flask web server.
- Displays user onboarding, registration, settings, focus-session, session-list, and report pages.
- Manages the active user state.
- Starts and stops focus sessions.
- Launches `combined_focus_prototype_v5.py` as a subprocess.
- Passes user/session information to the focus detection script through environment variables.
- Controls hardware outputs:
  - LEDs
  - light sensor
  - water pump
  - buzzer
- Provides HTTP routes that other modules can call to trigger hardware.
- Loads logs and reports for the current user.

### Important Internal Concepts

#### Active user state

`UI.py` stores the currently active user in a shared state:

```python
web_user_state = {
    'mode': 'guest',
    'user_id': -1,
}
```

This lets the UI know whether the current user is a guest or a registered user.

#### Focus session state

The UI also tracks the active focus session:

```python
focus_session_state = {
    'running': False,
    'phase': 'idle',
    'message': 'Focus session not started.',
    ...
}
```

This allows the web interface to show whether a session is running, whether it is in a focus or break phase, and which user/session ID is active.

#### Launching the focus detector

`UI.py` starts the real-time detection script as a subprocess. It passes:

- session ID
- user ID
- user name
- pump trigger URL
- buzzer trigger URL

This allows `combined_focus_prototype_v5.py` to log events under the correct session and trigger UI-controlled hardware.

### Hardware Routes

`UI.py` exposes routes such as:

- `/fire_pump`
- `/fire_buzzer`
- `/pump_status`
- `/set_led`
- `/status`

These routes are useful because the detection script can trigger hardware through HTTP instead of directly owning every hardware device.

---

## `combined_focus_prototype_v5.py` — Real-Time Focus Detection Engine

This file is the main intelligence layer for focus monitoring.

### Main Responsibilities

- Opens the webcam with OpenCV.
- Runs MediaPipe face landmarking.
- Runs MediaPipe pose landmarking.
- Runs MediaPipe object detection.
- Detects phones in the camera view.
- Detects active app/window state using Linux desktop tools.
- Falls back to process scanning if active-window detection is unavailable.
- Smooths noisy frame-by-frame results using short history buffers.
- Combines attention, posture, phone, and app signals into one focus state.
- Applies timers for warning and punishment escalation.
- Logs state changes and important events.
- Triggers buzzer and water pump responses when needed.

### Output States

The combined focus system can produce states such as:

- `FOCUSED`
- `DISTRACTED`
- `PHONE DETECTED`
- `HEAD DOWN`
- `POSTURE WARNING`
- `DISTRACTING APP`

### Escalation States

After the combined state is produced, the script decides whether the system should be:

- `NORMAL`
- `MONITORING`
- `WARNING`
- `PUNISHMENT READY`

---

## `Identify.py` — Face Recognition

`Identify.py` handles one-time identity checking using DeepFace.

### Main Responsibilities

- Opens the camera.
- Captures a single image when the user presses SPACE.
- Loads DeepFace in a background thread to avoid blocking startup.
- Compares the captured face image with the saved face database.
- Calls startup logic with either a matched user or guest mode.

### Important Design Detail

DeepFace is imported lazily in the background. This is useful on the Raspberry Pi because DeepFace/TensorFlow can take time to load and may produce many logs.

The file also includes recovery logic for corrupted DeepFace weight files. If DeepFace fails because a `.h5` weight file is corrupted, the code tries to remove that file and retry once.

---

## `testmain.py` — User Profile Database and Registration Logic

`testmain.py` manages user data and registration.

### Main Responsibilities

- Loads registered users from `users.json`.
- Saves user profile data back to JSON.
- Captures registration photos with OpenCV.
- Stores profile photos in the face database directory.
- Deletes user profiles.
- Deletes the user's related logs and report summaries when a profile is deleted.
- Provides a command-line startup flow used by the original version of the project.

### User Database

The default database path is:

```text
~/CMPE246_DB
```

This can be changed with the environment variable:

```bash
CMPE246_DB_PATH=/custom/path
```

The user profile data is stored in:

```text
users.json
```

Each user record stores:

- user ID / photo path
- name
- focus time
- break time
- preferred light setting

---

## `User.py` — User Profile Object

`User.py` defines the `User` class.

### Main Responsibilities

- Stores user profile data.
- Provides simple command-line options for:
  - starting focus session
  - changing settings
  - viewing reports
  - deleting profile

### Main Fields

```python
userID
name
focusTime
breakTime
light
reportData
```

In this project, `userID` is often the path to the user's stored face image. This path is used by the recognition/profile system.

---

## `logger.py` — Shared Event Logger

`logger.py` provides a thread-safe JSONL logging system.

### Main Responsibilities

- Creates readable session IDs.
- Writes structured event logs.
- Stores one JSON object per line.
- Associates events with:
  - session ID
  - module name
  - event type
  - value
  - details
  - user ID
  - user name
  - elapsed time
  - optional duration
- Finds all sessions belonging to a user.

### Why JSONL?

JSONL is useful because each line is an independent event. This makes logs easy to append, scan, debug, and summarize.

Example event structure:

```json
{
  "timestamp": "2026-04-01T14:30:10.123456",
  "session_id": "2026-04-01_14-30-00_study_session",
  "module": "distraction_detection",
  "event_type": "state_update",
  "value": "DISTRACTED",
  "details": {
    "attention_state": "LOOKING LEFT",
    "posture_state": "OK",
    "phone_present": false
  },
  "user_id": "user_photo_path",
  "user_name": "Alice"
}
```

---

## `report_generator.py` — Session Summary and HTML Report

`report_generator.py` reads session logs and converts them into a readable report.

### Main Responsibilities

- Loads all JSONL log files for one session.
- Counts event types.
- Calculates study duration.
- Counts break events.
- Calculates total distraction duration.
- Calculates bad-posture duration.
- Counts water-pump triggers.
- Counts distracting-app events.
- Builds an HTML report that can be embedded into the Flask UI.

### Main Outputs

The report includes:

- user name
- session ID
- study duration
- number of water pump triggers
- number and duration of breaks
- total distraction time
- total bad-posture time
- distraction reason counts
- event duration totals

---

## `sessionid_helper.py` — Session ID Utility

This is a small helper script that imports `create_session_id()` from `logger.py` and prints a new session ID.

It is useful for quick testing from the terminal.
