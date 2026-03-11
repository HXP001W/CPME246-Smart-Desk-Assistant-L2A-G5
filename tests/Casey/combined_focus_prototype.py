import cv2
import math
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# ============================================================
# 1. MODEL PATHS
# ------------------------------------------------------------
# These point to the models you already downloaded.
# Update them if your filenames are slightly different.
# ============================================================
FACE_MODEL_PATH = '/Users/a/Projects/smart-desk-assistant/models/face_landmarker.task'
POSE_MODEL_PATH = '/Users/a/Projects/smart-desk-assistant/models/pose_landmarker_lite.task'


# ============================================================
# 2. CREATE MEDIAPIPE TASK OBJECTS
# ------------------------------------------------------------
# We create one Face Landmarker and one Pose Landmarker.
# These will process each camera frame.
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


# ============================================================
# 3. HELPER FUNCTIONS
# ------------------------------------------------------------
# These functions keep the main loop cleaner.
# ============================================================

def euclidean_distance(p1, p2):
    """Return Euclidean distance between two (x, y) points."""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def get_face_attention_state(face_landmarks, frame_w, frame_h):
    """
    Estimate a simple attention state from face landmarks.

    We use a few face landmarks to infer rough head direction:
    - nose tip
    - left cheek / face side
    - right cheek / face side
    - forehead/chin relation

    This is NOT true gaze tracking.
    It is a heuristic approximation for:
    - looking left/right
    - head down
    - roughly centered/focused
    """

    # Landmark indices used here are common face mesh reference points.
    # These may not be perfect, but are enough for a prototype.
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

    # Convert normalized landmarks to pixel coordinates
    nose_px = (nose.x * frame_w, nose.y * frame_h)
    left_px = (left_face.x * frame_w, left_face.y * frame_h)
    right_px = (right_face.x * frame_w, right_face.y * frame_h)
    chin_px = (chin.x * frame_w, chin.y * frame_h)
    forehead_px = (forehead.x * frame_w, forehead.y * frame_h)

    # Horizontal head direction:
    # If the nose is closer to one side of the face box, head may be turned.
    left_dist = euclidean_distance(nose_px, left_px)
    right_dist = euclidean_distance(nose_px, right_px)

    # Ratio near 1.0 = face roughly centered
    # Smaller/larger ratio means head turned
    horizontal_ratio = left_dist / (right_dist + 1e-6)

    # Vertical estimate:
    # Compare nose relative to forehead/chin span.
    face_height = euclidean_distance(forehead_px, chin_px)
    nose_y_norm = (nose_px[1] - forehead_px[1]) / (face_height + 1e-6)

    # Heuristic thresholds
    if horizontal_ratio < 0.75:
        return "LOOKING RIGHT"
    elif horizontal_ratio > 1.35:
        return "LOOKING LEFT"
    elif nose_y_norm > 0.62:
        return "HEAD DOWN"
    else:
        return "FOCUSED"


def get_posture_state(pose_landmarks, frame_w, frame_h):
    """
    Estimate a very coarse posture state from pose landmarks.

    We use:
    - left shoulder
    - right shoulder
    - nose

    This is a rough sitting-posture heuristic:
    - shoulder line slope
    - nose position relative to shoulder center

    This does NOT truly measure spinal posture.
    It is just a useful prototype signal.
    """

    # Standard MediaPipe pose landmark indices
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

    # Shoulder slope: higher absolute slope may indicate leaning
    shoulder_dx = right_px[0] - left_px[0]
    shoulder_dy = right_px[1] - left_px[1]
    shoulder_slope = abs(shoulder_dy / (shoulder_dx + 1e-6))

    # How far forward/down the nose appears relative to shoulders
    vertical_offset = nose_px[1] - shoulder_center[1]

    # Heuristic thresholds for a desk prototype
    if shoulder_slope > 0.12:
        return "LEANING"
    elif vertical_offset < -140:
        return "UPRIGHT"
    elif vertical_offset < -90:
        return "OK"
    else:
        return "POSTURE WARNING"


def draw_face_landmarks(frame, face_landmarks):
    """Draw sparse face landmarks for easier visualization."""
    h, w, _ = frame.shape
    for idx, landmark in enumerate(face_landmarks):
        # Draw only some points to reduce clutter
        if idx % 20 == 0:
            cx = int(landmark.x * w)
            cy = int(landmark.y * h)
            cv2.circle(frame, (cx, cy), 1, (0, 255, 0), -1)


def draw_pose_landmarks(frame, pose_landmarks):
    """Draw all pose landmarks."""
    h, w, _ = frame.shape
    for landmark in pose_landmarks:
        cx = int(landmark.x * w)
        cy = int(landmark.y * h)
        cv2.circle(frame, (cx, cy), 3, (255, 0, 0), -1)


# ============================================================
# 4. CAMERA SETUP
# ------------------------------------------------------------
# Open the default webcam.
# ============================================================
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Could not open camera.")
    exit()


# ============================================================
# 5. MAIN LOOP
# ------------------------------------------------------------
# For each frame:
# - capture image
# - run face landmark detection
# - run pose landmark detection
# - infer attention state
# - infer posture state
# - fuse the results
# - display annotated output
# ============================================================
while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to read frame.")
        break

    frame_h, frame_w, _ = frame.shape

    # Convert OpenCV BGR -> RGB for MediaPipe
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    # Run both detectors
    face_result = face_landmarker.detect(mp_image)
    pose_result = pose_landmarker.detect(mp_image)

    attention_state = "FACE MISSING"
    posture_state = "UNKNOWN"
    combined_state = "DISTRACTED"

    # ---------------- FACE ANALYSIS ----------------
    if face_result.face_landmarks:
        face_landmarks = face_result.face_landmarks[0]
        draw_face_landmarks(frame, face_landmarks)
        attention_state = get_face_attention_state(face_landmarks, frame_w, frame_h)

    # ---------------- POSE ANALYSIS ----------------
    if pose_result.pose_landmarks:
        pose_landmarks = pose_result.pose_landmarks[0]
        draw_pose_landmarks(frame, pose_landmarks)
        posture_state = get_posture_state(pose_landmarks, frame_w, frame_h)

    # ---------------- FUSION LOGIC ----------------
    # This is your first simple decision engine.
    # Later you can replace this with timers and more advanced rules.
    if attention_state == "FACE MISSING":
        combined_state = "DISTRACTED"
    elif attention_state in ["LOOKING LEFT", "LOOKING RIGHT"]:
        combined_state = "DISTRACTED"
    elif attention_state == "HEAD DOWN":
        combined_state = "PHONE-LIKE POSTURE"
    elif posture_state in ["LEANING", "POSTURE WARNING"]:
        combined_state = "POSTURE WARNING"
    else:
        combined_state = "FOCUSED"

    # ---------------- DISPLAY TEXT ----------------
    cv2.putText(frame, f"Attention: {attention_state}", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.putText(frame, f"Posture: {posture_state}", (20, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

    # Color-code final state
    if combined_state == "FOCUSED":
        color = (0, 255, 0)
    elif combined_state == "POSTURE WARNING":
        color = (0, 255, 255)
    else:
        color = (0, 0, 255)

    cv2.putText(frame, f"State: {combined_state}", (20, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 3)

    cv2.imshow("Smart Desk Assistant Prototype", frame)

    # Press q to quit
    if (cv2.waitKey(1) & 0xFF) == ord("q"):
        break


# ============================================================
# 6. CLEANUP
# ------------------------------------------------------------
# Release camera and close windows.
# ============================================================
cap.release()
cv2.destroyAllWindows()
face_landmarker.close()
pose_landmarker.close()