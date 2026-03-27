import os
import cv2
import time
import threading
import gc
import numpy as np

# Suppress unnecessary DeepFace/TensorFlow log noise
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')

# Provide a Qt font directory for OpenCV Qt backend to avoid QFontDatabase warnings
for font_dir in ('/usr/share/fonts/truetype/dejavu', '/usr/share/fonts', '/usr/local/share/fonts'):
    if os.path.isdir(font_dir):
        os.environ.setdefault('QT_QPA_FONTDIR', font_dir)
        break

# DeepFace is imported lazily in a background thread to avoid blocking startup
_deepface_module = None
_deepface_ready = threading.Event()
_deepface_available = False
_deepface_error = None


def _startup(registeredUser=False, userID=-1):
    """Import startup lazily to avoid circular imports."""
    try:
        from .testmain import startup
    except ImportError:
        from testmain import startup
    startup(registeredUser=registeredUser, userID=userID)

def _load_deepface():
    global _deepface_module, _deepface_available, _deepface_error
    try:
        from deepface import DeepFace
        _deepface_module = DeepFace
        _deepface_available = True
        
        # Configure DeepFace for memory-efficient operation on Raspberry Pi
        # Suppress verbose logging to reduce memory overhead
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow warnings
        
    except Exception as e:
        _deepface_error = str(e)
        _deepface_available = False
    finally:
        _deepface_ready.set()

# Get the configurable database path
DB_PATH = os.getenv('CMPE246_DB_PATH', os.path.join(os.path.expanduser('~'), 'CMPE246_DB'))


def identity_test():
    """
    Captures a single photo from the front camera and compares it against
    the registered faces database.

    Controls:
    - Press SPACE to capture photo
    - Press C to switch camera (front/back)
    - Press Q to quit and continue as guest

    When a face is recognized, calls startup() with the matched user.
    """
    
    # Check if database path exists
    if not os.path.exists(DB_PATH):
        print(f"Database path not found at {DB_PATH}")
        print(f"Please create the database directory and add face images")
        os.makedirs(DB_PATH, exist_ok=True)
        print(f"Created database directory at: {DB_PATH}")
        print("Please add face images to the database and try again.")
        return
    
    # Check if database has any images
    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp')
    db_images = [f for f in os.listdir(DB_PATH) if f.lower().endswith(image_extensions)]
    
    if not db_images:
        print(f"No registered users found in database: {DB_PATH}")
        print(f"You can add face images to register users, or continue as guest.")
    else:
        print(f"Database path: {DB_PATH}")
        print(f"Found {len(db_images)} registered user(s) in database")
    
    print("\nStarting camera for one-time photo capture...")
    print("Press SPACE to take your picture")
    print("Press C to switch camera")
    print("Press Q to skip and continue as guest\n")

    # Reduce OpenCV log noise
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        pass

    # Start loading DeepFace in the background immediately
    threading.Thread(target=_load_deepface, daemon=True).start()

    # Track two common camera indices: 0 (usually back/default), 1 (usually front)
    camera_indices = [0, 1]
    current_camera_pos = 0

    def _open_camera(index):
        camera = cv2.VideoCapture(index)
        if not camera.isOpened():
            return None
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        camera.set(cv2.CAP_PROP_FPS, 10)
        return camera

    cap = _open_camera(camera_indices[current_camera_pos])
    if cap is None:
        # Try alternate camera on startup
        current_camera_pos = 1
        cap = _open_camera(camera_indices[current_camera_pos])
        if cap is None:
            print("Error: No camera available")
            return

    captured_frame = None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture frame")
                cap.release()
                cv2.destroyAllWindows()
                _startup(registeredUser=False, userID=-1)
                return

            cv2.putText(frame, "Align face and press SPACE to capture", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Camera index: {camera_indices[current_camera_pos]}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, "Press c to switch camera", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
            cv2.putText(frame, "Press q to continue as guest", (10, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

            cv2.imshow('Face Capture - Press SPACE to take photo', frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("\nPhoto capture skipped by user")
                print("Continuing as guest...")
                cap.release()
                cv2.destroyAllWindows()
                _startup(registeredUser=False, userID=-1)
                return

            if key == ord('c'):
                next_camera_pos = 1 - current_camera_pos
                next_cap = _open_camera(camera_indices[next_camera_pos])
                if next_cap is None:
                    print(f"Camera {camera_indices[next_camera_pos]} is not available")
                else:
                    cap.release()
                    cap = next_cap
                    current_camera_pos = next_camera_pos
                    print(f"Switched to camera {camera_indices[current_camera_pos]}")
                continue

            if key == ord(' '):
                captured_frame = frame.copy()
                print("\nPhoto captured. Comparing with database...")
                break

        # Camera no longer needed after one-shot capture
        cap.release()
        cv2.destroyAllWindows()

        # Wait for DeepFace initialization (up to 30s)
        _deepface_ready.wait(timeout=30)
        if not _deepface_available:
            print("\nDeepFace is not available in this environment.")
            print("Install it with: pip install deepface tf-keras")
            if _deepface_error:
                print(f"Import error: {_deepface_error}")
            print("Continuing as guest...")
            _startup(registeredUser=False, userID=-1)
            return

        # Downscale for memory efficiency
        analysis_frame = cv2.resize(captured_frame, (320, 240), interpolation=cv2.INTER_AREA)
        analysis_frame = analysis_frame.astype(np.uint8)

        dfs = _deepface_module.find(
            img_path=analysis_frame,
            db_path=DB_PATH,
            enforce_detection=False,
            silent=True
        )

        if dfs and len(dfs) > 0:
            result_df = dfs[0]
            if len(result_df) > 0:
                matched_identity = result_df.iloc[0]['identity']
                distance = result_df.iloc[0]['distance']

                print(f"\n✓ Face recognized!")
                print(f"  Identity: {matched_identity}")
                print(f"  Distance: {distance:.4f}")
                print("\nStarting user session...")
                _startup(registeredUser=True, userID=matched_identity)
                return

        print("\nNo registered user matched from captured photo.")
        print("Continuing as guest...")
        _startup(registeredUser=False, userID=-1)

    except KeyboardInterrupt:
        print("\nPhoto capture interrupted by user")
        _startup(registeredUser=False, userID=-1)
    except Exception as e:
        print(f"\nError during photo-based identification: {e}")
        _startup(registeredUser=False, userID=-1)
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if 'captured_frame' in locals():
            del captured_frame
        if 'analysis_frame' in locals():
            del analysis_frame
        if 'dfs' in locals():
            del dfs
        if 'result_df' in locals():
            del result_df
        gc.collect()

