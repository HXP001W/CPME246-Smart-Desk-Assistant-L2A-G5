import os
import cv2
import time
import threading
import gc
import numpy as np

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
    print("30-second timeout starts once facial recognition is active\n")

    # Start loading DeepFace in the background immediately
    threading.Thread(target=_load_deepface, daemon=True).start()

    # Open camera - try index 0 first (most common default), then 1
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Trying alternate camera (source 1)...")
        cap = cv2.VideoCapture(1)
        if not cap.isOpened():
            print("Error: No camera available")
            return

    # Keep stream memory footprint low
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Only keep 1 frame in buffer
    cap.set(cv2.CAP_PROP_FPS, 10)  # Reduce frame rate to reduce processing load

    warned_missing_deepface = False
    
    start_time = None
    timeout = 30  # 30 seconds timeout
    last_check_time = 0
    check_interval = 3  # Check every 3 seconds to reduce memory pressure
    frame_count = 0
    process_every_n_frames = 8  # Process every 8th frame for performance
    analysis_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture frame")
                break

            # Default on-screen status
            status_text = "Initializing face recognition..."
            status_color = (0, 200, 255)
            if _deepface_ready.is_set() and _deepface_available:
                status_text = "Facial recognition ACTIVE"
                status_color = (0, 255, 0)
                if start_time is None:
                    start_time = time.time()
            elif _deepface_ready.is_set() and not _deepface_available:
                status_text = "DeepFace unavailable - guest mode"
                status_color = (0, 0, 255)

                if not warned_missing_deepface:
                    print("\nDeepFace is not available in this environment.")
                    print("Install it with: pip install deepface tf-keras")
                    if _deepface_error:
                        print(f"Import error: {_deepface_error}")
                    print("Continuing as guest...")
                    warned_missing_deepface = True

                cap.release()
                cv2.destroyAllWindows()
                _startup(registeredUser=False, userID=-1)
                return
            
            # Check if timeout reached
            elapsed_time = 0 if start_time is None else (time.time() - start_time)
            if start_time is not None and elapsed_time >= timeout:
                print(f"\n⏱ Timeout reached ({timeout} seconds)")
                print("No registered user detected. Continuing as guest...")
                cap.release()
                cv2.destroyAllWindows()
                _startup(registeredUser=False, userID=-1)
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

                    # Downscale aggressively for lower memory use on Raspberry Pi
                    # Reduces resolution to 320x240 (~25% of original)
                    analysis_frame = cv2.resize(
                        frame,
                        (320, 240),
                        interpolation=cv2.INTER_AREA
                    )
                    
                    # Convert to uint8 to reduce memory footprint if needed
                    if analysis_frame.dtype != np.uint8:
                        analysis_frame = analysis_frame.astype(np.uint8)

                    try:
                        # Try to find matching face in database with memory-efficient settings
                        dfs = _deepface_module.find(
                            img_path=analysis_frame,
                            db_path=DB_PATH,
                            enforce_detection=False,
                            silent=True,
                            model_name="DeepFace",  # Lighter model than default VGG-Face
                            distance_metric="cosine"  # Faster computation than euclidean
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

                                # Call startup with registered user
                                _startup(registeredUser=True, userID=matched_identity)
                                return

                    except Exception as e:
                        # Silently handle detection errors (no face in frame, etc.)
                        pass
                    finally:
                        # Release recognition intermediates promptly to free memory
                        analysis_count += 1
                        if 'dfs' in locals():
                            del dfs
                        if 'result_df' in locals():
                            del result_df
                        if 'analysis_frame' in locals():
                            del analysis_frame

                        # Aggressive garbage collection to prevent memory buildup
                        # Run every 5 analysis iterations on Raspberry Pi
                        if analysis_count % 5 == 0:
                            gc.collect()

            # Draw status and timeout countdown overlay for user feedback
            cv2.putText(frame, status_text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
            if start_time is None:
                timeout_text = "Timeout: waiting for activation"
            else:
                countdown = max(0, int(timeout - elapsed_time))
                timeout_text = f"Timeout: {countdown}s"
            cv2.putText(frame, timeout_text, (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, "Press q to quit", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

            # Display the frame with overlays
            cv2.imshow('Face Recognition - Press q to quit', frame)
            
            # Clean up frame memory periodically
            if frame_count % 20 == 0:
                del frame
                gc.collect()
            
            # Check for 'q' key to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\nCamera stream stopped by user")
                print("No face recognized. Continuing as guest...")
                cap.release()
                cv2.destroyAllWindows()
                _startup(registeredUser=False, userID=-1)
                break
                
    except KeyboardInterrupt:
        print("\nCamera stream stopped by user")
    except Exception as e:
        print(f"\nError during camera streaming: {e}")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        gc.collect()

