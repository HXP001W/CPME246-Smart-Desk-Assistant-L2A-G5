import cv2
import math
import time
import os
import shutil
import subprocess
import threading
import urllib.request
import urllib.error
import importlib.util
from collections import deque, Counter

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


#model paths
FACE_MODEL_PATH = 'models/face_landmarker.task'
POSE_MODEL_PATH = 'models/pose_landmarker_lite.task'
OBJECT_MODEL_PATH = 'models/efficientdet_lite2_8.tflite'


#mediapipe task setup
face_base_options = python.BaseOptions(model_asset_path=FACE_MODEL_PATH)
face_options = vision.FaceLandmarkerOptions(
    base_options=face_base_options,
    output_face_blendshapes=False,
    output_facial_transformation_matrixes=False,
    num_faces=1
)
face_landmarker = vision.FaceLandmarker.create_from_options(face_options)

pose_base_options = python.BaseOptions(model_asset_path=POSE_MODEL_PATH)
pose_options = vision.PoseLandmarkerOptions(
    base_options=pose_base_options,
    output_segmentation_masks=False
)
pose_landmarker = vision.PoseLandmarker.create_from_options(pose_options)

object_base_options = python.BaseOptions(model_asset_path=OBJECT_MODEL_PATH)
object_options = vision.ObjectDetectorOptions(
    base_options=object_base_options,
    max_results=5,
    score_threshold=0.35
)
object_detector = vision.ObjectDetector.create_from_options(object_options)


#global settings & tuning patterns
#history lengths for smoothing
ATTENTION_HISTORY_LEN = 12
POSTURE_HISTORY_LEN = 12
PHONE_HISTORY_LEN = 12
APP_HISTORY_LEN = 8

# timers in seconds
DISTRACTION_WARNING_DELAY = 5.0
DISTRACTION_PUNISH_DELAY = 10.0
POSTURE_WARNING_DELAY = 5.0

#visualization settings
FONT = cv2.FONT_HERSHEY_SIMPLEX

# Performance tuning
INFERENCE_WIDTH = 640
POSE_EVERY_N_FRAMES = 2
OBJECT_EVERY_N_FRAMES = 3
APP_CHECK_EVERY_N_FRAMES = 5
PROCESS_SCAN_TIMEOUT_SECONDS = 0.8

#if phone appears in at least this many recent frames it is counted as present
PHONE_TRUE_THRESHOLD = 1

# application  detection settings
APP_FOCUS_TRUE_THRESHOLD = 3

#examples that can be changed
#if the active window contains one of the whitelist terms, it is treated as study-related.
##if it contains one of the blacklist terms, it is treated as distraction-related.
APP_STUDY_WHITELIST = [
    "code",
    "visual studio code",
    "chromium",
    "firefox",
    "pdf",
    "document viewer",
    "libreoffice",
    "writer",
    "impress",
    "calc",
    "terminal",
    "thonny",
    "canvas",
    "moodle",
    "jupyter",
    "notion",
    "obsidian"
]

APP_DISTRACTION_BLACKLIST = [
    "minecraft",
    "solitaire",
    "mahjongg",
    "games",
    "steam",
    "vlc",
    "spotify",
    "youtube",
    "netflix",
    "discord",
    "Avenger",
    "pgzrun"
]

# We tested and found that the xdo only works on X11 protocol and since newer raspberry pi os uses wayland protocol, it doesn't work.
# here are process-name fallback for Wayland or when active-window lookup is unavailable.
# These are checked against a task manager style process list.
APP_DISTRACTION_PROCESS_BLACKLIST = [
    "steam",
    "steamwebhelper",
    "lutris",
    "heroic",
    "discord",
    "minecraft",
    "prismlauncher",
    "multimc",
    "retroarch",
    "dolphin-emu",
    "pcsx2",
    "yuzu",
    "ryujinx",
    "wine",
    "gamescope",
    "pgzrun"
]

APP_STUDY_PROCESS_WHITELIST = [
    "code",
    "python",
    "jupyter",
    "chrome",
    "chromium",
    "firefox",
    "libreoffice",
    "evince",
    "zathura",
    "okular"
]

# Water pump settings with similar behavior as manual UI fire pulse
PUMP_PIN = 18
PUMP_ACTIVE_HIGH = True
PUMP_PULSE_SECONDS = 1.0
PUMP_COOLDOWN_SECONDS = 0.0
PUMP_HTTP_FIRE_URL = os.getenv("FOCUS_UI_FIRE_PUMP_URL", "http://127.0.0.1:5000/fire_pump")
PUMP_HTTP_STATUS_URL = os.getenv("FOCUS_UI_PUMP_STATUS_URL", "http://127.0.0.1:5000/pump_status")
PUMP_HTTP_TIMEOUT_SECONDS = 1.5
BUZZER_PULSE_SECONDS = 1.0
BUZZER_HTTP_FIRE_URL = os.getenv("FOCUS_UI_FIRE_BUZZER_URL", "http://127.0.0.1:5000/fire_buzzer")


#logging helper data structure
attention_history = deque(maxlen=ATTENTION_HISTORY_LEN)
posture_history = deque(maxlen=POSTURE_HISTORY_LEN)
phone_history = deque(maxlen=PHONE_HISTORY_LEN)
app_history = deque(maxlen=APP_HISTORY_LEN)

distraction_start_time = None
posture_start_time = None
punishment_trigger_count = 0

pump_device = None
pump_available = False
pump_last_fire_time = 0.0
pump_status_message = "Pump idle"
pump_control_mode = "unavailable"
pump_lock = threading.Lock()

session_id = os.getenv("FOCUS_SESSION_ID", time.strftime("%Y-%m-%d_%H-%M-%S_focus_session"))
user_id = os.getenv("FOCUS_USER_ID", "-1")
user_name = os.getenv("FOCUS_USER_NAME", "Guest")
logger_module = None
event_logger = None
last_combined_state = None
last_escalation_state = None
phone_start_time = None
last_logged_app_focus_state = None


def setup_event_logger():
    """Initialize shared JSONL logger from logging/logger.py when available."""
    global logger_module, event_logger
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        logger_path = os.path.join(project_root, 'logging', 'logger.py')
        if not os.path.exists(logger_path):
            return

        spec = importlib.util.spec_from_file_location('project_event_logger', logger_path)
        if spec is None or spec.loader is None:
            return

        logger_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(logger_module)

        log_dir = os.path.join(project_root, 'logging', 'logs')
        event_logger = logger_module.EventLogger(
            session_id=session_id,
            module_name='distraction_detection',
            log_dir=log_dir,
        )
    except Exception:
        event_logger = None


def log_event(event_type, value, details=None, duration_seconds=None):
    if event_logger is None:
        return
    try:
        event_logger.log_event(
            event_type=event_type,
            value=value,
            details=details or {},
            user_id=user_id,
            user_name=user_name,
            duration_seconds=duration_seconds,
        )
    except Exception:
        pass


# helper function
def euclidean_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def most_common_or_default(history, default_value):
    if not history:
        return default_value
    return Counter(history).most_common(1)[0][0]


def smoothed_phone_present(history):
    return sum(1 for x in history if x) >= PHONE_TRUE_THRESHOLD


def smoothed_app_distracting(history):
    return sum(1 for x in history if x == "DISTRACTING_APP") >= APP_FOCUS_TRUE_THRESHOLD



def _run_command(command):
    """
    Run a shell command safely and return stripped stdout.
    Returns None if the command is unavailable or fails.
    """
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception:
        return None


def setup_pump_device():
    """Initialize water pump GPIO device, if available on this machine."""
    global pump_device, pump_available, pump_status_message, pump_control_mode

    def _http_endpoint_available():
        try:
            with urllib.request.urlopen(PUMP_HTTP_STATUS_URL, timeout=PUMP_HTTP_TIMEOUT_SECONDS) as response:
                return response.status == 200
        except Exception:
            return False

    try:
        from gpiozero import OutputDevice
        pump_device = OutputDevice(PUMP_PIN, active_high=PUMP_ACTIVE_HIGH, initial_value=False)
        pump_available = True
        pump_control_mode = "gpio"
        pump_status_message = "Pump armed"
        print(f"Pump initialized on GPIO {PUMP_PIN} (pulse {PUMP_PULSE_SECONDS:.1f}s)")
        return
    except Exception as exc:
        print(f"Local pump GPIO unavailable: {exc}")

    if _http_endpoint_available():
        pump_available = True
        pump_control_mode = "ui_http"
        pump_status_message = "Pump armed (UI bridge)"
        print(f"Pump bridged via UI endpoint: {PUMP_HTTP_FIRE_URL}")
        return

    pump_available = False
    pump_control_mode = "unavailable"
    pump_status_message = "Pump unavailable"
    print("Pump unavailable: GPIO and UI bridge are both unavailable")


def _pump_pulse_worker():
    """Fire the water pump for one pulse."""
    global pump_status_message
    try:
        pump_status_message = "Pump firing"
        if pump_control_mode == "gpio":
            pump_device.on()
            time.sleep(PUMP_PULSE_SECONDS)
        elif pump_control_mode == "ui_http":
            request_url = (
                f"{PUMP_HTTP_FIRE_URL}?reason=persistent_distraction"
                f"&session_id={session_id}"
            )
            with urllib.request.urlopen(request_url, timeout=PUMP_HTTP_TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    raise RuntimeError(f"UI bridge returned HTTP {response.status}")

            time.sleep(0.1)
        else:
            raise RuntimeError("Pump control mode unavailable")
    except Exception as exc:
        pump_status_message = f"Pump error: {exc}"
    finally:
        try:
            if pump_control_mode == "gpio" and pump_device is not None:
                pump_device.off()
        except Exception:
            pass
        if pump_available:
            pump_status_message = "Pump armed" if pump_control_mode == "gpio" else "Pump armed (UI bridge)"


def try_fire_pump(current_time):
    """Attempt to fire pump with cooldown protection."""
    global pump_last_fire_time, pump_status_message

    if not pump_available:
        pump_status_message = "Pump unavailable"
        return False

    with pump_lock:
        if current_time - pump_last_fire_time < PUMP_COOLDOWN_SECONDS:
            return False
        pump_last_fire_time = current_time

    threading.Thread(target=_pump_pulse_worker, daemon=True).start()
    return True


def try_fire_warning_buzzer():
    """Trigger 1s warning buzzer through UI bridge."""
    try:
        request_url = (
            f"{BUZZER_HTTP_FIRE_URL}?reason=warning_distraction"
            f"&session_id={session_id}"
        )
        with urllib.request.urlopen(request_url, timeout=PUMP_HTTP_TIMEOUT_SECONDS) as response:
            return response.status == 200
    except Exception:
        return False


def get_running_process_names():
    """
    Return a lowercase set of process names from the system process table.
    Uses `ps` to avoid GUI protocol limitations under Wayland.
    """
    try:
        result = subprocess.run(
            ["ps", "-eo", "comm="],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=PROCESS_SCAN_TIMEOUT_SECONDS,
            check=False
        )
        if result.returncode != 0:
            return set()
        return {
            line.strip().lower()
            for line in result.stdout.splitlines()
            if line.strip()
        }
    except Exception:
        return set()



#this active-window detection code depends on X11 desktop tools.
# We installed these: sudo apt install xdotool, sudo apt install wmctrl x11-utils
# On Wayland sessions, these tools doesn't seem to be working.
def get_active_window_info():
    """
    Try to detect the active window title on Linux desktop environments.

    Primary path:
    - xdotool getactivewindow getwindowname

    Fallback path:
    - wmctrl -lp + xprop to resolve the active window id

    Returns a dictionary with:
    {
        "window_title": str,
        "source": str,
        "available": bool
    }

    If no usable information is available, returns a safe default.
    """

    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type == "wayland":
        return {
            "window_title": "WAYLAND_UNSUPPORTED",
            "source": "wayland",
            "available": False
        }

    # tried xdotool first.
    if shutil.which("xdotool"):
        window_title = _run_command(["xdotool", "getactivewindow", "getwindowname"])
        if window_title:
            return {
                "window_title": window_title,
                "source": "xdotool",
                "available": True
            }

    # fallback try xprop + wmctrl to recover the active window title.
    if shutil.which("xprop") and shutil.which("wmctrl"):
        active_line = _run_command(["xprop", "-root", "_NET_ACTIVE_WINDOW"])
        if active_line and "window id #" in active_line:
            try:
                window_id_hex = active_line.split("window id #")[-1].strip().split(",")[0].strip()
                wmctrl_output = _run_command(["wmctrl", "-lp"])
                if wmctrl_output:
                    for line in wmctrl_output.splitlines():
                        if not line.strip():
                            continue
                        parts = line.split(None, 4)
                        if len(parts) < 5:
                            continue
                        wmctrl_window_id = parts[0].lower()
                        window_title = parts[4].strip()
                        if wmctrl_window_id == window_id_hex.lower():
                            return {
                                "window_title": window_title,
                                "source": "wmctrl+xprop",
                                "available": True
                            }
            except Exception:
                pass

    return {
        "window_title": "UNAVAILABLE",
        "source": "none",
        "available": False
    }



def classify_app_focus_state(window_info):
    """
    Classify the currently active window into a simple focus category.

    Returns one of:
    - STUDY_APP
    - DISTRACTING_APP
    - NEUTRAL_APP
    - UNKNOWN_APP
    """
    if not window_info.get("available", False):
        return "UNKNOWN_APP"

    title = window_info.get("window_title", "").lower()

    for term in APP_DISTRACTION_BLACKLIST:
        if term in title:
            return "DISTRACTING_APP"

    for term in APP_STUDY_WHITELIST:
        if term in title:
            return "STUDY_APP"

    return "NEUTRAL_APP"


def classify_app_focus_state_from_processes(process_names):
    """
    Task-manager-style fallback classification from running process names.

    Returns one of:
    - DISTRACTING_APP
    - STUDY_APP
    - NEUTRAL_APP
    - UNKNOWN_APP
    """
    if not process_names:
        return "UNKNOWN_APP"

    for term in APP_DISTRACTION_PROCESS_BLACKLIST:
        if any(term in proc for proc in process_names):
            return "DISTRACTING_APP"

    for term in APP_STUDY_PROCESS_WHITELIST:
        if any(term in proc for proc in process_names):
            return "STUDY_APP"

    return "NEUTRAL_APP"


def draw_sparse_face_landmarks(frame, face_landmarks):
    h, w, _ = frame.shape
    for idx, landmark in enumerate(face_landmarks):
        if idx % 20 == 0:
            cx = int(landmark.x * w)
            cy = int(landmark.y * h)
            cv2.circle(frame, (cx, cy), 1, (0, 255, 0), -1)


def draw_pose_landmarks(frame, pose_landmarks):
    h, w, _ = frame.shape
    for landmark in pose_landmarks:
        cx = int(landmark.x * w)
        cy = int(landmark.y * h)
        cv2.circle(frame, (cx, cy), 3, (255, 0, 0), -1)


def draw_object_boxes(frame, object_result):
    for detection in object_result.detections:
        bbox = detection.bounding_box
        x, y, w, h = bbox.origin_x, bbox.origin_y, bbox.width, bbox.height

        label = "unknown"
        score = 0.0

        if detection.categories:
            label = detection.categories[0].category_name
            score = detection.categories[0].score

        cv2.rectangle(frame, (x, y), (x + w, y + h), (180, 255, 0), 2)
        cv2.putText(
            frame,
            f"{label}: {score:.2f}",
            (x, max(20, y - 10)),
            FONT,
            0.5,
            (180, 255, 0),
            2
        )


def draw_status_panel(frame, title, lines, x, y, width, bg_color=(20, 20, 20), alpha=0.45, text_offset_x=10):
    """Draw a semi-transparent info panel with title and line items."""
    header_h = 36
    row_h = 24
    padding = text_offset_x
    panel_h = header_h + (len(lines) * row_h) + padding

    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + width, y + panel_h), bg_color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    cv2.putText(frame, title, (x + padding, y + 22), FONT, 0.56, (240, 240, 240), 2)

    row_y = y + header_h + 2
    for line_text, line_color in lines:
        cv2.putText(frame, line_text, (x + padding, row_y), FONT, 0.54, line_color, 1)
        row_y += row_h

    return panel_h


def detect_phone(object_result):
    """
    Try to detect whether a phone is present in object detections.
    The exact label name depends on model metadata, so we check loosely.
    """
    for detection in object_result.detections:
        if detection.categories:
            label = detection.categories[0].category_name.lower()
            score = detection.categories[0].score

            if score < 0.35:
                continue

            if (
                "phone" in label
                or "cell phone" in label
                or "mobile phone" in label
                or "smartphone" in label
            ):
                return True

    return False


def get_face_attention_state(face_landmarks, frame_w, frame_h):
    """
    Estimate attention from face landmarks using simple geometry.

    Outputs:
    - FOCUSED
    - LOOKING LEFT
    - LOOKING RIGHT
    - HEAD DOWN
    - HEAD UP

    This is NOT gaze tracking.
    It is a head orientation heuristic based on landmark geometry.
    """

    #landmarks chosen for rough face orientation
    NOSE_TIP = 1
    LEFT_FACE = 234
    RIGHT_FACE = 454
    CHIN = 152
    FOREHEAD = 10

    nose = face_landmarks[NOSE_TIP]
    left_face = face_landmarks[LEFT_FACE]
    right_face = face_landmarks[RIGHT_FACE]
    chin = face_landmarks[CHIN]
    forehead = face_landmarks[FOREHEAD]

    nose_px = (nose.x * frame_w, nose.y * frame_h)
    left_px = (left_face.x * frame_w, left_face.y * frame_h)
    right_px = (right_face.x * frame_w, right_face.y * frame_h)
    chin_px = (chin.x * frame_w, chin.y * frame_h)
    forehead_px = (forehead.x * frame_w, forehead.y * frame_h)

    #horizontal orientation
    left_dist = euclidean_distance(nose_px, left_px)
    right_dist = euclidean_distance(nose_px, right_px)
    horizontal_ratio = left_dist / (right_dist + 1e-6)

    #vertical orientation
    face_height = euclidean_distance(forehead_px, chin_px)
    nose_y_norm = (nose_px[1] - forehead_px[1]) / (face_height + 1e-6)

    #more forgiving thresholds than earlier versions
    if horizontal_ratio < 0.44:
        return "LOOKING RIGHT"
    elif horizontal_ratio > 1.99:
        return "LOOKING LEFT"
    elif nose_y_norm > 0.68:
        return "HEAD DOWN"
    elif nose_y_norm < 0.42:
        return "HEAD UP"
    else:
        return "FOCUSED"


def get_posture_state(pose_landmarks, frame_w, frame_h):
    """
    Very coarse posture heuristic using nose and shoulders.

    Outputs:
    - UPRIGHT
    - OK
    - LEANING
    - POSTURE WARNING
    """

    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12

    nose = pose_landmarks[NOSE]
    left_shoulder = pose_landmarks[LEFT_SHOULDER]
    right_shoulder = pose_landmarks[RIGHT_SHOULDER]

    nose_px = (nose.x * frame_w, nose.y * frame_h)
    left_px = (left_shoulder.x * frame_w, left_shoulder.y * frame_h)
    right_px = (right_shoulder.x * frame_w, right_shoulder.y * frame_h)

    shoulder_center = ((left_px[0] + right_px[0]) / 2, (left_px[1] + right_px[1]) / 2)

    shoulder_dx = right_px[0] - left_px[0]
    shoulder_dy = right_px[1] - left_px[1]
    shoulder_slope = abs(shoulder_dy / (shoulder_dx + 1e-6))

    vertical_offset = nose_px[1] - shoulder_center[1]

    if shoulder_slope > 0.22:
        return "LEANING"
    elif vertical_offset < -155:
        return "UPRIGHT"
    elif vertical_offset < -70:
        return "OK"
    else:
        return "POSTURE WARNING"


def classify_combined_state(attention_state, posture_state, phone_present, app_focus_state):
    """
    Combine the current smoothed states into a higher-level state.
    """

    # Strong distraction cases first
    if attention_state == "FACE MISSING":
        return "DISTRACTED"

    if attention_state in ["LOOKING LEFT", "LOOKING RIGHT", "HEAD UP"]:
        return "DISTRACTED"

    if app_focus_state == "DISTRACTING_APP":
        return "DISTRACTING APP"

    if phone_present:
        return "PHONE DETECTED"

    if attention_state == "HEAD DOWN":
        return "HEAD DOWN"

    if posture_state in ["LEANING", "POSTURE WARNING"]:
        return "POSTURE WARNING"

    return "FOCUSED"


def get_escalation_label(distraction_duration, posture_duration, combined_state):
    """
    Decide whether the system is:
    - normal
    - warning
    - punishment-ready
    """

    # Distraction escalation
    if combined_state in ["DISTRACTED", "PHONE DETECTED", "HEAD DOWN", "DISTRACTING APP"]:
        if distraction_duration >= DISTRACTION_PUNISH_DELAY:
            return "PUNISHMENT READY"
        elif distraction_duration >= DISTRACTION_WARNING_DELAY:
            return "WARNING"
        else:
            return "MONITORING"

    # Posture escalation
    if combined_state == "POSTURE WARNING":
        if posture_duration >= POSTURE_WARNING_DELAY:
            return "WARNING"
        else:
            return "MONITORING"

    return "NORMAL"


# ============================================================
# 6. CAMERA SETUP
# ============================================================
setup_event_logger()
log_event(
    'module_started',
    'distraction_detection_started',
    details={'session_id': session_id, 'user_id': str(user_id), 'user_name': user_name},
)

setup_pump_device()
log_event(
    'pump_control_initialized',
    pump_control_mode,
    details={
        'pump_available': pump_available,
        'control_mode': pump_control_mode,
        'pump_pin': PUMP_PIN,
    },
)

cap = cv2.VideoCapture(0)

# Reduce camera buffering and input resolution where supported.
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print("Could not open camera.")
    exit()


# ============================================================
# 7. MAIN LOOP
# ============================================================
frame_idx = 0
last_pose_result = None
last_object_result = None
last_active_window_info = {"window_title": "UNAVAILABLE", "source": "none", "available": False}
last_app_focus_state = "UNKNOWN_APP"
last_process_hint = "none"
fps_window_start = time.time()
fps_counter = 0
fps_display = 0.0

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to read frame.")
        break

    frame_idx += 1
    current_time = time.time()
    frame_h, frame_w, _ = frame.shape

    # Keep UI responsive by running inference on a smaller frame.
    if frame_w > INFERENCE_WIDTH:
        infer_h = int(frame_h * (INFERENCE_WIDTH / frame_w))
        infer_frame = cv2.resize(frame, (INFERENCE_WIDTH, infer_h), interpolation=cv2.INTER_LINEAR)
    else:
        infer_frame = frame

    # Convert frame for MediaPipe
    rgb_frame = cv2.cvtColor(infer_frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    # Face is relatively light; keep per-frame updates.
    face_result = face_landmarker.detect(mp_image)

    # Run heavier models less frequently and reuse recent results.
    if last_pose_result is None or frame_idx % POSE_EVERY_N_FRAMES == 0:
        last_pose_result = pose_landmarker.detect(mp_image)
    pose_result = last_pose_result

    if last_object_result is None or frame_idx % OBJECT_EVERY_N_FRAMES == 0:
        last_object_result = object_detector.detect(mp_image)
    object_result = last_object_result

    # Defaults for current frame
    attention_state_current = "FACE MISSING"
    posture_state_current = "UNKNOWN"
    phone_present_current = False
    active_window_info = last_active_window_info
    app_focus_state_current = last_app_focus_state
    process_hint_current = last_process_hint

    # ---------------- FACE ----------------
    if face_result.face_landmarks:
        face_landmarks = face_result.face_landmarks[0]
        draw_sparse_face_landmarks(frame, face_landmarks)
        attention_state_current = get_face_attention_state(face_landmarks, frame_w, frame_h)

    # ---------------- POSE ----------------
    if pose_result.pose_landmarks:
        pose_landmarks = pose_result.pose_landmarks[0]
        draw_pose_landmarks(frame, pose_landmarks)
        posture_state_current = get_posture_state(pose_landmarks, frame_w, frame_h)

    # ---------------- OBJECT DETECTION ----------------
    draw_object_boxes(frame, object_result)
    phone_present_current = detect_phone(object_result)

    # ---------------- ACTIVE WINDOW / APP DETECTION ----------------
    if frame_idx % APP_CHECK_EVERY_N_FRAMES == 0:
        active_window_info = get_active_window_info()
        app_focus_state_current = classify_app_focus_state(active_window_info)

        # Wayland fallback: infer focus category from running processes.
        if app_focus_state_current == "UNKNOWN_APP":
            process_names = get_running_process_names()
            process_based_state = classify_app_focus_state_from_processes(process_names)

            if process_based_state != "UNKNOWN_APP":
                app_focus_state_current = process_based_state
                if process_based_state == "DISTRACTING_APP":
                    matched = next(
                        (
                            term
                            for term in APP_DISTRACTION_PROCESS_BLACKLIST
                            if any(term in proc for proc in process_names)
                        ),
                        "unknown"
                    )
                    process_hint_current = f"game-process:{matched}"
                elif process_based_state == "STUDY_APP":
                    matched = next(
                        (
                            term
                            for term in APP_STUDY_PROCESS_WHITELIST
                            if any(term in proc for proc in process_names)
                        ),
                        "unknown"
                    )
                    process_hint_current = f"study-process:{matched}"
                else:
                    process_hint_current = "process-scan"
            else:
                process_hint_current = "none"
        else:
            process_hint_current = "window-title"

        last_active_window_info = active_window_info
        last_app_focus_state = app_focus_state_current
        last_process_hint = process_hint_current

    # ---------------- APPEND TO HISTORY ----------------
    attention_history.append(attention_state_current)
    posture_history.append(posture_state_current)
    phone_history.append(phone_present_current)
    app_history.append(app_focus_state_current)

    # ---------------- SMOOTHED STATES ----------------
    attention_state = most_common_or_default(attention_history, "FACE MISSING")
    posture_state = most_common_or_default(posture_history, "UNKNOWN")
    phone_present = smoothed_phone_present(phone_history)
    app_focus_state = "DISTRACTING_APP" if smoothed_app_distracting(app_history) else most_common_or_default(app_history, "UNKNOWN_APP")

    if app_focus_state != last_logged_app_focus_state:
        log_event(
            'app_focus_changed',
            app_focus_state,
            details={
                'active_window_title': active_window_info.get('window_title', 'UNAVAILABLE'),
                'active_window_source': active_window_info.get('source', 'none'),
                'app_detection_hint': process_hint_current,
                'is_distracting_app': app_focus_state == 'DISTRACTING_APP',
            },
        )
        last_logged_app_focus_state = app_focus_state

    combined_state = classify_combined_state(attention_state, posture_state, phone_present, app_focus_state)

    if combined_state != last_combined_state:
        log_event(
            'state_update',
            combined_state,
            details={
                'state_name': 'combined_state',
                'attention_state': attention_state,
                'posture_state': posture_state,
                'phone_present': phone_present,
                'app_focus_state': app_focus_state,
            },
        )
        last_combined_state = combined_state

    # ---------------- TIMER LOGIC ----------------
    distraction_now = combined_state in ["DISTRACTED", "PHONE DETECTED", "HEAD DOWN", "DISTRACTING APP"]
    bad_posture_now = combined_state == "POSTURE WARNING"

    if distraction_now:
        if distraction_start_time is None:
            distraction_start_time = current_time
            log_event(
                'distraction_started',
                combined_state,
                details={
                    'reason': combined_state,
                    'app_focus_state': app_focus_state,
                    'posture_state': posture_state,
                },
            )
    else:
        if distraction_start_time is not None:
            resolved_duration = round(current_time - distraction_start_time, 2)
            log_event(
                'distraction_ended',
                'focus_recovered',
                details={
                    'last_state': combined_state,
                    'duration_seconds': resolved_duration,
                },
                duration_seconds=resolved_duration,
            )
        distraction_start_time = None

    if bad_posture_now:
        if posture_start_time is None:
            posture_start_time = current_time
            log_event(
                'bad_posture_started',
                posture_state,
                details={'reason': 'posture_warning'},
            )
    else:
        if posture_start_time is not None:
            posture_duration_resolved = round(current_time - posture_start_time, 2)
            log_event(
                'bad_posture_ended',
                'posture_recovered',
                details={'duration_seconds': posture_duration_resolved},
                duration_seconds=posture_duration_resolved,
            )
        posture_start_time = None

    distraction_duration = 0.0 if distraction_start_time is None else current_time - distraction_start_time
    posture_duration = 0.0 if posture_start_time is None else current_time - posture_start_time

    if phone_present:
        if phone_start_time is None:
            phone_start_time = current_time
            log_event(
                'phone_detected',
                'phone_present',
                details={
                    'reason': 'phone_object_detected',
                    'active_window_title': active_window_info.get('window_title', 'UNAVAILABLE'),
                },
            )
    else:
        if phone_start_time is not None:
            phone_duration = round(current_time - phone_start_time, 2)
            log_event(
                'phone_cleared',
                'phone_not_present',
                details={'duration_seconds': phone_duration},
                duration_seconds=phone_duration,
            )
        phone_start_time = None

    if not distraction_now:
        punishment_trigger_count = 0

    escalation_state = get_escalation_label(distraction_duration, posture_duration, combined_state)

    if escalation_state != last_escalation_state:
        log_event(
            'escalation_update',
            escalation_state,
            details={
                'combined_state': combined_state,
                'distraction_duration_seconds': round(distraction_duration, 2),
                'posture_duration_seconds': round(posture_duration, 2),
                'reason': combined_state,
            },
        )
        if escalation_state == 'WARNING':
            distraction_warning = combined_state in ["DISTRACTED", "PHONE DETECTED", "HEAD DOWN", "DISTRACTING APP"]
            if distraction_warning and try_fire_warning_buzzer():
                log_event(
                    'buzzer_triggered',
                    'warning_beep',
                    details={
                        'reason': 'warning_distraction',
                        'combined_state': combined_state,
                        'pulse_seconds': BUZZER_PULSE_SECONDS,
                        'control_mode': 'ui_http',
                    },
                    duration_seconds=BUZZER_PULSE_SECONDS,
                )

            log_event(
                'warning_triggered',
                combined_state,
                details={
                    'reason': combined_state,
                    'distraction_duration_seconds': round(distraction_duration, 2),
                    'app_focus_state': app_focus_state,
                    'posture_state': posture_state,
                },
            )
        elif escalation_state == 'PUNISHMENT READY':
            log_event(
                'punishment_ready',
                combined_state,
                details={
                    'reason': combined_state,
                    'distraction_duration_seconds': round(distraction_duration, 2),
                    'app_focus_state': app_focus_state,
                    'posture_state': posture_state,
                },
            )
        elif last_escalation_state in ['WARNING', 'PUNISHMENT READY'] and escalation_state in ['NORMAL', 'MONITORING']:
            log_event(
                'focus_restored',
                combined_state,
                details={'reason': 'focus_recovered'},
            )

        last_escalation_state = escalation_state

    # ---------------- ALERT TEXT ----------------
    distraction_message = ""
    posture_message = ""

    if escalation_state == "WARNING":
        if combined_state in ["DISTRACTED", "PHONE DETECTED", "HEAD DOWN", "DISTRACTING APP"]:
            distraction_message = "Distraction detected - please stay focused"
        elif combined_state == "POSTURE WARNING":
            posture_message = "Bad posture detected - please improve your posture"

    elif escalation_state == "PUNISHMENT READY":
        distraction_message = "Distraction persists - punishment system can be triggered"

    punishments_due = int(distraction_duration // DISTRACTION_PUNISH_DELAY)
    if escalation_state == "PUNISHMENT READY" and distraction_now and punishments_due > punishment_trigger_count:
        if try_fire_pump(current_time):
            punishment_trigger_count = punishments_due
            distraction_message = "Distraction persists - water punishment triggered"
            log_event(
                'water_pump_triggered',
                'triggered',
                details={
                    'trigger_count': punishment_trigger_count,
                    'reason': combined_state,
                    'distraction_duration_seconds': round(distraction_duration, 2),
                    'control_mode': pump_control_mode,
                    'pulse_seconds': PUMP_PULSE_SECONDS,
                },
                duration_seconds=PUMP_PULSE_SECONDS,
            )

    # ---------------- DRAW STATUS ----------------
    # Combined state color
    if combined_state == "FOCUSED":
        state_color = (0, 255, 0)
    elif combined_state == "POSTURE WARNING":
        state_color = (0, 255, 255)
    else:
        state_color = (0, 0, 255)

    # Escalation color
    if escalation_state == "NORMAL":
        escalation_color = (0, 255, 0)
    elif escalation_state == "MONITORING":
        escalation_color = (255, 200, 0)
    elif escalation_state == "WARNING":
        escalation_color = (0, 255, 255)
    else:
        escalation_color = (0, 0, 255)

    fps_counter += 1
    elapsed = current_time - fps_window_start
    if elapsed >= 0.5:
        fps_display = fps_counter / elapsed
        fps_counter = 0
        fps_window_start = current_time

    # Active window title (truncated for display). Hide unsupported marker in overlay.
    window_title_display = active_window_info.get("window_title", "UNAVAILABLE")
    if window_title_display == "WAYLAND_UNSUPPORTED":
        window_title_display = ""
    elif len(window_title_display) > 60:
        window_title_display = window_title_display[:57] + "..."

    # Responsive two-panel layout so text blocks do not overlap on narrower frames.
    panel_gap = 12
    side_margin = 14
    max_panel_w = (frame_w - (2 * side_margin) - panel_gap) // 2
    panel_w = max(240, min(430, max_panel_w))

    left_panel_lines = [
        (f"State: {combined_state}", state_color),
        (f"Escalation: {escalation_state}", escalation_color),
        (f"Distraction timer: {distraction_duration:.1f}s", (0, 170, 255)),
        (f"Posture timer: {posture_duration:.1f}s", (255, 170, 80)),
        (f"Pump: {pump_status_message}", (255, 255, 0)),
        (f"FPS: {fps_display:.1f}", (240, 240, 240)),
    ]
    draw_status_panel(frame, "SESSION STATUS", left_panel_lines, x=side_margin, y=14, width=panel_w)

    right_panel_lines = [
        (f"Attention: {attention_state}", (0, 255, 0)),
        (f"Posture: {posture_state}", (255, 100, 100)),
        (f"Phone present: {phone_present}", (180, 255, 0)),
        (f"App: {app_focus_state}", (255, 220, 120)),
    ]
    if window_title_display:
        right_panel_lines.append((f"Window: {window_title_display}", (220, 220, 220)))

    right_panel_x = frame_w - side_margin - panel_w
    draw_status_panel(
        frame,
        "CONTEXT",
        right_panel_lines,
        x=right_panel_x,
        y=14,
        width=panel_w,
        text_offset_x=18,
    )

    # Warning / punishment-ready messages near bottom
    if distraction_message:
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, frame_h - 72), (frame_w - 10, frame_h - 36), (40, 40, 150), -1)
        cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)
        cv2.putText(frame, distraction_message, (22, frame_h - 48), FONT, 0.62, (40, 40, 255), 2)

    if posture_message:
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, frame_h - 36), (frame_w - 10, frame_h - 6), (60, 140, 140), -1)
        cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)
        cv2.putText(frame, posture_message, (22, frame_h - 14), FONT, 0.56, (0, 255, 255), 2)

    cv2.imshow("Smart Desk Assistant Prototype V5", frame)

    if (cv2.waitKey(1) & 0xFF) == ord("q"):
        break


# ============================================================
# 8. CLEANUP
# ============================================================
cap.release()
cv2.destroyAllWindows()
face_landmarker.close()
pose_landmarker.close()
object_detector.close()

if pump_device is not None:
    try:
        pump_device.off()
        pump_device.close()
    except Exception:
        pass

log_event(
    'module_stopped',
    'distraction_detection_stopped',
    details={'reason': 'camera_loop_ended'},
)