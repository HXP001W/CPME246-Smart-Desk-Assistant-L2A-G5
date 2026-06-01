# Tools and Dependencies

This document lists the main software tools used in the project and what each one does.

## Flask

Used in `UI.py`.

Flask provides the web interface. It handles routes, buttons, pages, JSON API responses, and report display.

In this project, Flask is the main control layer for:

- user onboarding
- starting face recognition
- starting/stopping focus sessions
- viewing reports
- controlling LEDs, buzzer, and pump

## OpenCV (`cv2`)

Used in:

- `UI.py`
- `Identify.py`
- `testmain.py`
- `combined_focus_prototype_v5.py`

OpenCV handles camera access and image display. It is used to:

- open the USB webcam
- capture frames
- show preview windows
- draw text, boxes, and landmarks
- capture user registration photos

## MediaPipe

Used in `combined_focus_prototype_v5.py`.

MediaPipe provides machine-learning vision tasks:

- face landmark detection
- pose landmark detection
- object detection

The project uses MediaPipe Tasks API with local model files such as:

- `face_landmarker.task`
- `pose_landmarker_lite.task`
- `efficientdet_lite2_8.tflite`

## DeepFace

Used in `Identify.py`.

DeepFace is used for face recognition. It compares a captured face image against the saved face database and determines whether the user matches a registered profile.

## NumPy

Used directly in `Identify.py` and indirectly by OpenCV/MediaPipe workflows.

NumPy provides array operations for image data.

## gpiozero

Used in `UI.py` and optionally in `combined_focus_prototype_v5.py`.

gpiozero provides simple Raspberry Pi GPIO control for:

- LEDs
- buzzer
- water pump relay/output

## RPi.GPIO backend

`UI.py` tries to use the RPi.GPIO backend through gpiozero:

```python
from gpiozero.pins.rpigpio import RPiGPIOFactory
```

This can provide more stable GPIO behavior on Raspberry Pi.

## subprocess

Used in `UI.py` and `combined_focus_prototype_v5.py`.

Subprocess is used to:

- launch the detection script from the UI
- run Linux commands for active-window/app detection
- open the browser through `xdg-open` fallback

## threading

Used in several files.

Threading allows background tasks to run without blocking the UI or main loop. Examples:

- face recognition job
- focus session loop
- pump pulse timing
- buzzer pulse timing
- DeepFace background loading

## JSON

Used in:

- `testmain.py`
- `logger.py`
- `report_generator.py`

JSON is used for:

- storing user profile data
- writing structured logs
- saving report summaries

## Linux desktop tools

Used indirectly in `combined_focus_prototype_v5.py`.

The active-window detection system can use:

- `xdotool`
- `wmctrl`
- `xprop`

These are mostly useful on X11. On Wayland, active-window access is limited, so the script includes a process-scan fallback.

## urllib

Used in `combined_focus_prototype_v5.py`.

The detection script uses `urllib` to call local UI endpoints such as:

- `/fire_buzzer`
- `/fire_pump`

This allows the focus detection module to request hardware actions from the UI.
