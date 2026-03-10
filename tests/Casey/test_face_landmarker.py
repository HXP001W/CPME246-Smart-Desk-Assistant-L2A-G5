import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

MODEL_PATH = '/Users/a/Projects/smart-desk-assistant/models/face_landmarker.task'

base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    output_face_blendshapes=False,
    output_facial_transformation_matrixes=False,
    num_faces=1
)

detector = vision.FaceLandmarker.create_from_options(options)

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Could not open camera")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        break

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    result = detector.detect(mp_image)

    if result.face_landmarks:
        for face_landmarks in result.face_landmarks:
            h, w, _ = frame.shape
            for landmark in face_landmarks:
                cx = int(landmark.x * w)
                cy = int(landmark.y * h)
                cv2.circle(frame, (cx, cy), 1, (0, 255, 0), -1)

    cv2.imshow("Face Landmarker Test", frame)

    if (cv2.waitKey(1) & 0xFF) == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
detector.close()