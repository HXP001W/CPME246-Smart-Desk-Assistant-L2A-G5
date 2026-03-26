import cv2
import math
import time
from collections import deque, Counter

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# ============================================================
# 1. MODEL PATHS
# ============================================================
FACE_MODEL_PATH = 'models/face_landmarker.task'
POSE_MODEL_PATH = 'models/pose_landmarker_lite.task'
OBJECT_MODEL_PATH = 'models/efficientdet_lite2_8.tflite'


# ============================================================
# 2. MEDIAPIPE TASK SETUP
# ============================================================
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


# ============================================================
# 3. GLOBAL SETTINGS / TUNING PARAMETERS
# ============================================================

# History lengths for smoothing
ATTENTION_HISTORY_LEN = 12
POSTURE_HISTORY_LEN = 12
PHONE_HISTORY_LEN = 12

# Timers (seconds)
DISTRACTION_WARNING_DELAY = 5.0
DISTRACTION_PUNISH_DELAY = 10.0
POSTURE_WARNING_DELAY = 5.0

# Visualization settings
FONT = cv2.FONT_HERSHEY_SIMPLEX

# If phone appears in at least this many recent frames, count it as present
PHONE_TRUE_THRESHOLD = 1


# ============================================================
# 4. HELPER DATA STRUCTURES
# ============================================================
attention_history = deque(maxlen=ATTENTION_HISTORY_LEN)
posture_history = deque(maxlen=POSTURE_HISTORY_LEN)
phone_history = deque(maxlen=PHONE_HISTORY_LEN)

distraction_start_time = None
posture_start_time = None


# ============================================================
# 5. HELPER FUNCTIONS
# ============================================================
def euclidean_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def most_common_or_default(history, default_value):
    if not history:
        return default_value
    return Counter(history).most_common(1)[0][0]


def smoothed_phone_present(history):
    return sum(1 for x in history if x) >= PHONE_TRUE_THRESHOLD


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

    # Landmarks chosen for rough face orientation
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

    # ----- Horizontal orientation -----
    left_dist = euclidean_distance(nose_px, left_px)
    right_dist = euclidean_distance(nose_px, right_px)
    horizontal_ratio = left_dist / (right_dist + 1e-6)

    # ----- Vertical orientation -----
    face_height = euclidean_distance(forehead_px, chin_px)
    nose_y_norm = (nose_px[1] - forehead_px[1]) / (face_height + 1e-6)

    # More forgiving thresholds than earlier versions
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


def classify_combined_state(attention_state, posture_state, phone_present):
    """
    Combine the current smoothed states into a higher-level state.
    """

    # Strong distraction cases first
    if attention_state == "FACE MISSING":
        return "DISTRACTED"

    if attention_state in ["LOOKING LEFT", "LOOKING RIGHT", "HEAD UP"]:
        return "DISTRACTED"

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
    if combined_state in ["DISTRACTED", "PHONE DETECTED", "HEAD DOWN"]:
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
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Could not open camera.")
    exit()


# ============================================================
# 7. MAIN LOOP
# ============================================================
while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to read frame.")
        break

    current_time = time.time()
    frame_h, frame_w, _ = frame.shape

    # Convert frame for MediaPipe
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    # Run inference
    face_result = face_landmarker.detect(mp_image)
    pose_result = pose_landmarker.detect(mp_image)
    object_result = object_detector.detect(mp_image)

    # Defaults for current frame
    attention_state_current = "FACE MISSING"
    posture_state_current = "UNKNOWN"
    phone_present_current = False

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

    # ---------------- APPEND TO HISTORY ----------------
    attention_history.append(attention_state_current)
    posture_history.append(posture_state_current)
    phone_history.append(phone_present_current)

    # ---------------- SMOOTHED STATES ----------------
    attention_state = most_common_or_default(attention_history, "FACE MISSING")
    posture_state = most_common_or_default(posture_history, "UNKNOWN")
    phone_present = smoothed_phone_present(phone_history)

    combined_state = classify_combined_state(attention_state, posture_state, phone_present)

    # ---------------- TIMER LOGIC ----------------
    distraction_now = combined_state in ["DISTRACTED", "PHONE DETECTED", "HEAD DOWN"]
    bad_posture_now = combined_state == "POSTURE WARNING"

    if distraction_now:
        if distraction_start_time is None:
            distraction_start_time = current_time
    else:
        distraction_start_time = None

    if bad_posture_now:
        if posture_start_time is None:
            posture_start_time = current_time
    else:
        posture_start_time = None

    distraction_duration = 0.0 if distraction_start_time is None else current_time - distraction_start_time
    posture_duration = 0.0 if posture_start_time is None else current_time - posture_start_time

    escalation_state = get_escalation_label(distraction_duration, posture_duration, combined_state)

    # ---------------- ALERT TEXT ----------------
    distraction_message = ""
    posture_message = ""

    if escalation_state == "WARNING":
        if combined_state in ["DISTRACTED", "PHONE DETECTED", "HEAD DOWN"]:
            distraction_message = "Distraction detected - please stay focused"
        elif combined_state == "POSTURE WARNING":
            posture_message = "Bad posture detected - please improve your posture"

    elif escalation_state == "PUNISHMENT READY":
        distraction_message = "Distraction persists - punishment system can be triggered"

    # ---------------- DRAW STATUS ----------------
    cv2.putText(frame, f"Attention(current): {attention_state_current}", (20, 30),
                FONT, 0.55, (120, 255, 120), 2)

    cv2.putText(frame, f"Attention(smoothed): {attention_state}", (20, 60),
                FONT, 0.65, (0, 255, 0), 2)

    cv2.putText(frame, f"Posture(smoothed): {posture_state}", (20, 90),
                FONT, 0.65, (255, 0, 0), 2)

    cv2.putText(frame, f"Phone(smoothed): {phone_present}", (20, 120),
                FONT, 0.65, (180, 255, 0), 2)

    # Combined state color
    if combined_state == "FOCUSED":
        state_color = (0, 255, 0)
    elif combined_state == "POSTURE WARNING":
        state_color = (0, 255, 255)
    else:
        state_color = (0, 0, 255)

    cv2.putText(frame, f"State: {combined_state}", (20, 160),
                FONT, 0.9, state_color, 3)

    # Escalation color
    if escalation_state == "NORMAL":
        escalation_color = (0, 255, 0)
    elif escalation_state == "MONITORING":
        escalation_color = (255, 200, 0)
    elif escalation_state == "WARNING":
        escalation_color = (0, 255, 255)
    else:
        escalation_color = (0, 0, 255)

    cv2.putText(frame, f"Escalation: {escalation_state}", (20, 200),
                FONT, 0.8, escalation_color, 2)

    cv2.putText(frame, f"Distraction timer: {distraction_duration:.1f}s", (20, 235),
                FONT, 0.6, (0, 150, 255), 2)

    cv2.putText(frame, f"Posture timer: {posture_duration:.1f}s", (20, 265),
                FONT, 0.6, (255, 150, 0), 2)

    # Warning / punishment-ready messages near bottom
    if distraction_message:
        cv2.putText(frame, distraction_message, (20, frame_h - 50),
                    FONT, 0.7, (0, 0, 255), 3)

    if posture_message:
        cv2.putText(frame, posture_message, (20, frame_h - 20),
                    FONT, 0.7, (0, 255, 255), 3)

    cv2.imshow("Smart Desk Assistant Prototype V3", frame)

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