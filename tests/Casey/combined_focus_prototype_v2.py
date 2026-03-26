import cv2
import math
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# ============================================================
# 1. MODEL PATHS
# ============================================================
FACE_MODEL_PATH = 'CPME246-Smart-Desk-Assistant-L2A-G5/models/face_landmarker.task'
POSE_MODEL_PATH = 'CPME246-Smart-Desk-Assistant-L2A-G5/models/pose_landmarker_lite.task'
OBJECT_MODEL_PATH = 'CPME246-Smart-Desk-Assistant-L2A-G5/models/efficientdet_lite0.tflite'


# ============================================================
# 2. CREATE MEDIAPIPE TASK OBJECTS
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
# 3. HELPER FUNCTIONS
# ============================================================
def euclidean_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def get_face_attention_state(face_landmarks, frame_w, frame_h):
    """
    Estimate rough head direction / attention state.
    This version is LESS sensitive than before.
    """

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

    left_dist = euclidean_distance(nose_px, left_px)
    right_dist = euclidean_distance(nose_px, right_px)
    horizontal_ratio = left_dist / (right_dist + 1e-6)

    face_height = euclidean_distance(forehead_px, chin_px)
    nose_y_norm = (nose_px[1] - forehead_px[1]) / (face_height + 1e-6)

    # Less sensitive thresholds than the previous version
    if horizontal_ratio < 0.44:
        return "LOOKING RIGHT"
    elif horizontal_ratio > 1.99:
        return "LOOKING LEFT"
    elif nose_y_norm > 0.68:
        return "HEAD DOWN"
    else:
        return "FOCUSED"


def get_posture_state(pose_landmarks, frame_w, frame_h):
    """
    Estimate coarse posture state.
    Also made a bit less sensitive.
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

    # Slightly more forgiving posture thresholds
    if shoulder_slope > 0.12:
        return "LEANING"
    elif vertical_offset < -140:
        return "UPRIGHT"
    elif vertical_offset < -90:
        return "OK"
    else:
        return "POSTURE WARNING"


def detect_phone(object_result):
    """
    Check if a phone/cell phone appears in object detection results.
    """
    for detection in object_result.detections:
        if detection.categories:
            label = detection.categories[0].category_name.lower()
            score = detection.categories[0].score

            if ("phone" in label or "cell phone" in label or "mobile phone" in label) and score > 0.35:
                return True
    return False


def draw_face_landmarks(frame, face_landmarks):
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
    """
    Draw bounding boxes for detected objects.
    """
    for detection in object_result.detections:
        bbox = detection.bounding_box
        x, y, w, h = bbox.origin_x, bbox.origin_y, bbox.width, bbox.height

        label = "unknown"
        score = 0.0

        if detection.categories:
            label = detection.categories[0].category_name
            score = detection.categories[0].score

        cv2.rectangle(frame, (x, y), (x + w, y + h), (200, 255, 0), 2)
        cv2.putText(
            frame,
            f"{label}: {score:.2f}",
            (x, max(20, y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 255, 0),
            2
        )


# ============================================================
# 4. STATE TIMERS
# ------------------------------------------------------------
# These track how long a bad condition has lasted.
# ============================================================
distraction_start_time = None
posture_start_time = None

DISTRACTION_ALERT_DELAY = 5.0
POSTURE_ALERT_DELAY = 5.0


# ============================================================
# 5. CAMERA SETUP
# ============================================================
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Could not open camera.")
    exit()


# ============================================================
# 6. MAIN LOOP
# ============================================================
while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to read frame.")
        break

    frame_h, frame_w, _ = frame.shape
    current_time = time.time()

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    face_result = face_landmarker.detect(mp_image)
    pose_result = pose_landmarker.detect(mp_image)
    object_result = object_detector.detect(mp_image)

    attention_state = "FACE MISSING"
    posture_state = "UNKNOWN"
    phone_present = False
    combined_state = "DISTRACTED"

    # ---------------- FACE ----------------
    if face_result.face_landmarks:
        face_landmarks = face_result.face_landmarks[0]
        draw_face_landmarks(frame, face_landmarks)
        attention_state = get_face_attention_state(face_landmarks, frame_w, frame_h)

    # ---------------- POSE ----------------
    if pose_result.pose_landmarks:
        pose_landmarks = pose_result.pose_landmarks[0]
        draw_pose_landmarks(frame, pose_landmarks)
        posture_state = get_posture_state(pose_landmarks, frame_w, frame_h)

    # ---------------- OBJECT / PHONE ----------------
    draw_object_boxes(frame, object_result)
    phone_present = detect_phone(object_result)

    # ---------------- DECISION ENGINE ----------------
    distraction_now = False
    bad_posture_now = False

    # Distraction logic
    if attention_state == "FACE MISSING":
        distraction_now = True
        combined_state = "DISTRACTED"
    elif attention_state in ["LOOKING LEFT", "LOOKING RIGHT"]:
        distraction_now = True
        combined_state = "DISTRACTED"
    elif attention_state == "HEAD DOWN" and phone_present:
        distraction_now = True
        combined_state = "PHONE DETECTED"
    elif attention_state == "HEAD DOWN":
        distraction_now = True
        combined_state = "HEAD DOWN"
    else:
        combined_state = "FOCUSED"

    # Posture logic
    if posture_state in ["LEANING", "POSTURE WARNING"]:
        bad_posture_now = True
        if not distraction_now:
            combined_state = "POSTURE WARNING"

    # ---------------- TIMER LOGIC ----------------
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

    distraction_message = ""
    posture_message = ""

    if distraction_duration >= DISTRACTION_ALERT_DELAY:
        distraction_message = "Distraction detected - please stay focused"

    if posture_duration >= POSTURE_ALERT_DELAY:
        posture_message = "Bad posture detected - please improve your posture"

    # ---------------- DISPLAY TEXT ----------------
    cv2.putText(frame, f"Attention: {attention_state}", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.putText(frame, f"Posture: {posture_state}", (20, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

    cv2.putText(frame, f"Phone present: {phone_present}", (20, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 255, 0), 2)

    if combined_state == "FOCUSED":
        state_color = (0, 255, 0)
    elif combined_state == "POSTURE WARNING":
        state_color = (0, 255, 255)
    else:
        state_color = (0, 0, 255)

    cv2.putText(frame, f"State: {combined_state}", (20, 130),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, state_color, 3)

    cv2.putText(frame, f"Distraction timer: {distraction_duration:.1f}s", (20, 170),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 150, 255), 2)

    cv2.putText(frame, f"Posture timer: {posture_duration:.1f}s", (20, 200),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 150, 0), 2)

    # Show alert messages after 5 seconds
    if distraction_message:
        cv2.putText(frame, distraction_message, (20, frame_h - 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 3)

    if posture_message:
        cv2.putText(frame, posture_message, (20, frame_h - 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 3)

    cv2.imshow("Smart Desk Assistant Prototype V2", frame)

    if (cv2.waitKey(1) & 0xFF) == ord("q"):
        break


# ============================================================
# 7. CLEANUP
# ============================================================
cap.release()
cv2.destroyAllWindows()
face_landmarker.close()
pose_landmarker.close()
object_detector.close()