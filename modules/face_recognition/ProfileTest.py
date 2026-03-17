import pandas as pd
from typing import List
import os
import cv2
import time
import threading

from testmain import startup

# DeepFace is imported lazily in a background thread to avoid blocking startup
_deepface_module = None
_deepface_ready = threading.Event()

def _load_deepface():
    global _deepface_module
    from deepface import DeepFace
    _deepface_module = DeepFace
    _deepface_ready.set()

# Get the configurable database path
DB_PATH = os.getenv('CMPE246_DB_PATH', os.path.join(os.path.expanduser('~'), 'CMPE246_DB'))


def identity_test():
    """
    Uses the front camera to identify faces from the database in real-time.
    Press 'q' to quit the camera stream.
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
    
    print("\nStarting camera face recognition...")
    print("Press 'q' to quit the camera stream")
    print("Will automatically continue as guest after 30 seconds if no face detected\n")

    # Start loading DeepFace in the background immediately
    threading.Thread(target=_load_deepface, daemon=True).start()

    # Open camera - try index 0 first (most common default), then 1
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("Trying alternate camera (source 1)...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: No camera available")
            return
    
    start_time = time.time()
    timeout = 30  # 30 seconds timeout
    last_check_time = 0
    check_interval = 2  # Check every 2 seconds
    frame_count = 0
    process_every_n_frames = 5  # Process every 5th frame for performance
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture frame")
                break

            # Default on-screen status
            status_text = "Initializing face recognition..."
            status_color = (0, 200, 255)
            if _deepface_ready.is_set():
                status_text = "Facial recognition ACTIVE"
                status_color = (0, 255, 0)
            
            # Check if timeout reached
            elapsed_time = time.time() - start_time
            if elapsed_time >= timeout:
                print(f"\n⏱ Timeout reached ({timeout} seconds)")
                print("No registered user detected. Continuing as guest...")
                cap.release()
                cv2.destroyAllWindows()
                startup(registeredUser=False, userID=-1)
                return
            
            frame_count += 1
            current_time = time.time()
            
            # Process frame every N frames and after the time interval
            if frame_count % process_every_n_frames == 0 and (current_time - last_check_time) >= check_interval:
                last_check_time = current_time

                # Skip recognition until DeepFace has finished loading
                if not _deepface_ready.is_set():
                    status_text = "Initializing face recognition..."
                    status_color = (0, 200, 255)
                else:
                    status_text = "Facial recognition ACTIVE - analyzing..."
                    status_color = (0, 255, 0)

                    # Save current frame temporarily
                    temp_frame_path = "temp_frame.jpg"
                    cv2.imwrite(temp_frame_path, frame)

                    try:
                        # Try to find matching face in database
                        dfs = _deepface_module.find(
                            img_path=temp_frame_path,
                            db_path=DB_PATH,
                            enforce_detection=False,
                            silent=True
                        )

                        # Check if match found
                        if dfs and len(dfs) > 0:
                            result_df = dfs[0]
                            if len(result_df) > 0:
                                # Get the best match (first result)
                                matched_identity = result_df.iloc[0]['identity']
                                distance = result_df.iloc[0]['distance']

                                print(f"\n✓ Face recognized!")
                                print(f"  Identity: {matched_identity}")
                                print(f"  Distance: {distance:.4f}")
                                print("\nStarting user session...")

                                # Clean up
                                cap.release()
                                cv2.destroyAllWindows()
                                if os.path.exists(temp_frame_path):
                                    os.remove(temp_frame_path)

                                # Call startup with registered user
                                startup(registeredUser=True, userID=matched_identity)
                                return

                    except Exception as e:
                        # Silently handle detection errors (no face in frame, etc.)
                        pass

                    # Clean up temp file
                    if os.path.exists(temp_frame_path):
                        os.remove(temp_frame_path)

            # Draw status and timeout countdown overlay for user feedback
            cv2.putText(frame, status_text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
            countdown = max(0, int(timeout - elapsed_time))
            cv2.putText(frame, f"Timeout: {countdown}s", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, "Press q to quit", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

            # Display the frame with overlays
            cv2.imshow('Face Recognition - Press q to quit', frame)
            
            # Check for 'q' key to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\nCamera stream stopped by user")
                print("No face recognized. Continuing as guest...")
                cap.release()
                cv2.destroyAllWindows()
                startup(registeredUser=False, userID=-1)
                break
                
    except KeyboardInterrupt:
        print("\nCamera stream stopped by user")
    except Exception as e:
        print(f"\nError during camera streaming: {e}")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if os.path.exists("temp_frame.jpg"):
            os.remove("temp_frame.jpg")

