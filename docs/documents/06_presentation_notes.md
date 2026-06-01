# Presentation Notes and Q&A Preparation

## One-Minute Project Explanation

> Our project is a Smart Desk Assistant built around a Raspberry Pi. It uses a web UI to manage users and study sessions, computer vision to detect focus, posture, phone use, and distraction, and hardware outputs like LEDs, a buzzer, and a water pump to provide feedback. The system also logs events during each session and generates a final report so the user can review their study behavior.

## How to Explain the Architecture

> `UI.py` is the main controller. It manages the web interface, user flow, focus session timing, hardware routes, and report pages. When a focus session starts, the UI launches `combined_focus_prototype_v5.py` as a subprocess. That script does the real-time monitoring using OpenCV and MediaPipe. It logs events through `logger.py`, and after the session, `report_generator.py` summarizes those logs into a report.

## How to Explain the Detection System

> The detection system combines multiple signals instead of relying on just one. It uses face landmarks to estimate whether the user is looking forward or away, pose landmarks for rough posture checking, object detection for phone detection, and app/window monitoring for computer distraction. These signals are smoothed over time and then fused into one combined state such as `FOCUSED`, `DISTRACTED`, `PHONE DETECTED`, `POSTURE WARNING`, or `DISTRACTING APP`.

## Main Technical Strengths

- Modular architecture
- Real-time computer vision
- Multiple distraction signals
- Temporal smoothing to reduce false positives
- Timer-based escalation instead of instant punishment
- Hardware integration
- Structured logging and report generation
- Registered user and guest workflow

## Good Q&A Answers

### Why did you use multiple detection methods?

Because one method alone can be misleading. Looking down could mean reading notes, and a phone could be visible without being used. Combining face, posture, phone, and app context makes the decision more reliable.

### Is the system doing real eye tracking?

No. It uses face landmark geometry to estimate head orientation. Full eye tracking would require a more specialized model and calibration.

### How do you prevent false triggers?

The system uses history buffers and timers. It reacts to sustained distraction, not one bad frame.

### Why use rule-based logic?

Rule-based logic is transparent and easy to tune. For a Raspberry Pi prototype, this is more practical than training a full custom neural network.

### How is hardware triggered?

The detection script can call the Flask UI's local `/fire_buzzer` and `/fire_pump` routes. The UI then controls the physical GPIO hardware.

### What was difficult?

The hardest parts were integration and deployment: making camera, MediaPipe, DeepFace, Flask, GPIO hardware, logs, and reports work together on Raspberry Pi.

### What could be improved?

Future improvements could include better posture models, calibrated gaze tracking, more accurate app classification, user-specific thresholds, and a safer/polished hardware enclosure.
