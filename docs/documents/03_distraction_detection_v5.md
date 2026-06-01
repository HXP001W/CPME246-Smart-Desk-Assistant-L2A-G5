# Distraction Detection System: `combined_focus_prototype_v5.py`

This file is the real-time focus and distraction detection engine of the Smart Desk Assistant.

It combines computer vision, app/window monitoring, temporal smoothing, rule-based decision logic, hardware feedback, and structured logging.

## High-Level Purpose

The script monitors the user during a focus session and decides whether the user is:

- focused
- distracted
- looking away
- looking down
- using a phone
- in poor posture
- using a distracting application

It then decides whether the system should keep monitoring, show a warning, or trigger a hardware response.

## Main Inputs

### 1. Webcam Frames

The webcam is opened with OpenCV:

```python
cap = cv2.VideoCapture(0)
```

The script sets a lower resolution and buffer size to improve responsiveness on Raspberry Pi.

### 2. MediaPipe Face Landmarks

The face landmarker model is used to detect facial landmarks. The script uses selected landmarks such as:

- nose tip
- left/right face boundary
- forehead
- chin

These are used to estimate approximate head direction.

Important: this is **not full eye tracking**. It is a head-orientation heuristic.

Possible face attention states:

- `FOCUSED`
- `LOOKING LEFT`
- `LOOKING RIGHT`
- `HEAD DOWN`
- `HEAD UP`
- `FACE MISSING`

### 3. MediaPipe Pose Landmarks

The pose landmarker estimates body landmarks. The script mainly uses:

- nose
- left shoulder
- right shoulder

These points are used for a coarse posture estimate.

Possible posture states:

- `UPRIGHT`
- `OK`
- `LEANING`
- `POSTURE WARNING`
- `UNKNOWN`

This is a lightweight posture heuristic, not a medical ergonomic model.

### 4. MediaPipe Object Detection

The object detector checks whether a phone-like object is visible.

The script searches object labels for words like:

- `phone`
- `cell phone`
- `mobile phone`
- `smartphone`

If a phone is detected with sufficient confidence, the phone signal becomes true.

### 5. Active Application / Window Detection

The script also checks computer activity.

On X11 Linux desktops, it tries to use:

- `xdotool`
- `wmctrl`
- `xprop`

These tools can reveal the active window title.

If active-window detection is unavailable, the script falls back to process scanning using the system process list. This is especially useful when running under Wayland, where global active-window inspection may be restricted.

App state categories:

- `STUDY_APP`
- `DISTRACTING_APP`
- `NEUTRAL_APP`
- `UNKNOWN_APP`

## Performance Optimizations

Raspberry Pi is less powerful than a laptop, so the script includes several optimizations:

- webcam frame resolution is reduced
- inference can be done on a smaller resized frame
- face detection runs frequently
- heavier models such as pose/object detection are run every few frames
- app/window checking is also done every few frames
- recent results are reused between checks

This keeps the system more responsive.

## Temporal Smoothing

Computer vision results can be noisy. A single bad frame should not immediately cause a warning.

The script uses `deque` buffers to store recent states:

- `attention_history`
- `posture_history`
- `phone_history`
- `app_history`

Then it applies simple smoothing:

- attention and posture use most-common recent state
- phone and app detection require repeated recent detections before being treated as true

This prevents the system from overreacting to one-frame mistakes.

## Combined Decision Logic

The function `classify_combined_state(...)` merges the smoothed signals into one final state.

The logic is priority-based:

1. If the face is missing, the user is treated as distracted.
2. If the head is turned left/right or up, the user is treated as distracted.
3. If a distracting app is active, the state becomes `DISTRACTING APP`.
4. If a phone is present, the state becomes `PHONE DETECTED`.
5. If the head is down, the state becomes `HEAD DOWN`.
6. If posture is poor, the state becomes `POSTURE WARNING`.
7. Otherwise, the state is `FOCUSED`.

This is a rule-based fusion system. The benefit is that it is interpretable, easy to tune, and easier to debug than an end-to-end neural network.

## Escalation Logic

The system separates detection from response.

A distracting state does not immediately trigger punishment. Instead, the script tracks how long the state persists.

The function `get_escalation_label(...)` returns:

- `NORMAL`
- `MONITORING`
- `WARNING`
- `PUNISHMENT READY`

Example behavior:

```text
Focused
  ↓
Short distraction detected
  ↓
MONITORING
  ↓ after warning delay
WARNING
  ↓ after punishment delay
PUNISHMENT READY
```

This makes the system more reasonable and prevents accidental triggers from short movements.

## Logging

The script logs important events through the shared logger:

- module started
- pump control initialized
- app focus changed
- combined state changed
- distraction started
- distraction ended
- bad posture started
- bad posture ended
- phone detected
- phone cleared
- escalation changed
- warning triggered
- punishment ready
- buzzer triggered
- water pump triggered
- module stopped

These logs are later summarized by `report_generator.py`.

## Hardware Feedback

The script supports two hardware-response paths:

### 1. Direct GPIO pump control

If running on a Raspberry Pi with GPIO access, the script can directly control a pump output device.

### 2. UI HTTP bridge

The script can call UI routes such as:

- `/fire_buzzer`
- `/fire_pump`

This allows `UI.py` to own the hardware while the detection script only sends requests. This is a safer architecture because one module controls physical outputs.

## What to Say in a Presentation

A concise explanation:

> The distraction detection system is a multi-signal rule-based engine. It combines face landmarks, pose landmarks, object detection, and app monitoring. Each raw input is converted into a semantic state, such as head down, phone detected, posture warning, or distracting app. We then apply temporal smoothing to reduce false positives and use timer-based escalation so short distractions do not immediately trigger hardware. If distraction persists, the system can warn the user with a buzzer and eventually activate the pump.

## Good Q&A Answers

### Is it eye tracking?

No. It estimates attention using head orientation from facial landmarks. Full eye tracking would require a more specialized model and calibration.

### Why use rule-based fusion instead of one neural network?

Rule-based fusion is easier to explain, tune, and debug. It also works better for a course prototype running on Raspberry Pi because it avoids training a custom model.

### How do you avoid false positives?

The system uses temporal smoothing and delay timers. A single bad frame does not immediately trigger a warning or hardware response.

### Why include app/window detection?

Camera vision alone cannot always tell whether the user is studying. App/window detection adds operating-system context, such as whether the active app is a study tool or a game/social media app.

### What happens on Wayland?

Wayland restricts active-window inspection. The script can fall back to process scanning, but X11 gives better active-window information.
