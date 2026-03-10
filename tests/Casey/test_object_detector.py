import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

MODEL_PATH = '/Users/a/Projects/smart-desk-assistant/models/efficientdet_lite0.tflite'

base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.ObjectDetectorOptions(
    base_options=base_options,
    max_results=5,
    score_threshold=0.3
)

detector = vision.ObjectDetector.create_from_options(options)

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

    for detection in result.detections:
        bbox = detection.bounding_box
        x, y, w, h = bbox.origin_x, bbox.origin_y, bbox.width, bbox.height

        label = "unknown"
        score = 0.0

        if detection.categories:
            label = detection.categories[0].category_name
            score = detection.categories[0].score

        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(
            frame,
            f"{label}: {score:.2f}",
            (x, max(20, y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2
        )

    cv2.imshow("Object Detector Test", frame)

    if (cv2.waitKey(1) & 0xFF) == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
detector.close()