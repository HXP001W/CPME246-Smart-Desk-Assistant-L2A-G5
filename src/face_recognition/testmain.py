import os
import warnings

# Suppress unnecessary DeepFace/TensorFlow log noise
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')

# Provide a Qt font directory for OpenCV Qt backend to avoid QFontDatabase warnings
for font_dir in ('/usr/share/fonts/truetype/dejavu', '/usr/share/fonts', '/usr/local/share/fonts'):
    if os.path.isdir(font_dir):
        os.environ.setdefault('QT_QPA_FONTDIR', font_dir)
        break

# Suppress repetitive QFontDatabase warnings from OpenCV UI backend
warnings.filterwarnings('ignore', message='.*QFontDatabase.*')

try:
    from . import User
    from . import Identify
except ImportError:
    import User
    import Identify
import shutil
import cv2
import json
import time
from pathlib import Path

# Configuration: Set database path via environment variable or use default
DB_PATH = os.getenv('CMPE246_DB_PATH', os.path.join(os.path.expanduser('~'), 'CMPE246_DB'))
USER_DATA_FILE = os.path.join(DB_PATH, 'users.json')

# Load existing user data from file
def load_users():
    """Load user data from JSON file"""
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, 'r') as f:
                users_data = json.load(f)
                users = []
                for user_data in users_data:
                    users.append(User.User(
                        userID=user_data.get('userID', -1),
                        name=user_data.get('name'),
                        focusTime=user_data.get('focusTime', 0),
                        breakTime=user_data.get('breakTime', 0),
                        light=user_data.get('light')
                    ))
                # Pad with empty users to have 4 slots
                while len(users) < 4:
                    users.append(User.User(userID=-1))
                return users[:4]  # Return only first 4
        except Exception as e:
            print(f"Error loading user data: {e}")
    # Return empty users if file doesn't exist or error occurs
    return [User.User(userID=-1), User.User(userID=-1), User.User(userID=-1), User.User(userID=-1)]

def save_users():
    """Save user data to JSON file"""
    try:
        os.makedirs(DB_PATH, exist_ok=True)
        users_data = []
        for user in userList:
            if user.userID != -1:  # Only save registered users
                users_data.append({
                    'userID': user.userID,
                    'name': user.name,
                    'focusTime': user.focusTime,
                    'breakTime': user.breakTime,
                    'light': user.light
                })
        with open(USER_DATA_FILE, 'w') as f:
            json.dump(users_data, f, indent=2)
        print(f"User data saved to {USER_DATA_FILE}")
    except Exception as e:
        print(f"Error saving user data: {e}")


def _find_user_sessions_in_logs(log_dir, user_id):
    """Return session IDs found in JSONL logs for a specific user."""
    sessions = set()
    log_path = Path(log_dir)
    if not log_path.exists():
        return sessions

    user_id_str = str(user_id)
    for file_path in log_path.glob("*_*.jsonl"):
        try:
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if str(event.get("user_id", "")) == user_id_str:
                        session_id = event.get("session_id")
                        if session_id:
                            sessions.add(str(session_id))
        except Exception:
            continue

    return sessions


def _delete_user_session_artifacts(user_id):
    """Delete per-session log files and report summaries for a user."""
    project_root = Path(__file__).resolve().parents[2]
    log_dir = project_root / "logging" / "logs"
    report_dir = project_root / "logging" / "reports"

    deleted_log_files = 0
    deleted_report_files = 0

    session_ids = _find_user_sessions_in_logs(log_dir, user_id)
    for session_id in session_ids:
        for log_file in log_dir.glob(f"{session_id}_*.jsonl"):
            try:
                log_file.unlink(missing_ok=True)
                deleted_log_files += 1
            except Exception:
                pass

        report_summary = report_dir / f"{session_id}_summary.json"
        if report_summary.exists():
            try:
                report_summary.unlink(missing_ok=True)
                deleted_report_files += 1
            except Exception:
                pass

    return {
        "session_count": len(session_ids),
        "deleted_log_files": deleted_log_files,
        "deleted_report_files": deleted_report_files,
    }

def delete_profile(user):
    """Delete a user profile, remove from registered users, and delete their picture"""
    if user.userID == -1:
        print("Cannot delete an empty profile.")
        return False
    
    try:
        # Delete the user's photo file
        if user.userID and os.path.exists(user.userID):
            os.remove(user.userID)
            print(f"✓ Deleted photo: {user.userID}")

        cleanup_result = _delete_user_session_artifacts(user.userID)
        print(
            "✓ Deleted user session artifacts: "
            f"sessions={cleanup_result['session_count']}, "
            f"logs={cleanup_result['deleted_log_files']}, "
            f"reports={cleanup_result['deleted_report_files']}"
        )
        
        # Find the user in the list and replace with an empty user
        for i, u in enumerate(userList):
            if u.userID == user.userID:
                userList[i] = User.User(userID=-1)  # Replace with empty slot
                print(f"✓ Profile for {user.name} has been deleted")
                break
        
        # Save the updated user list
        save_users()
        print("✓ Profile deletion complete. Empty slot created.")
        return True
        
    except Exception as e:
        print(f"Error deleting profile: {e}")
        return False

def capture_user_photo(user_name):
    """Capture a photo of the user using the front camera and save to database"""
    print(f"\nPreparing to take your photo, {user_name}...")
    print("Position yourself in front of the camera.")
    print("Press SPACE to capture, C to switch camera, or Q to cancel")

    # Reduce noisy OpenCV logs on systems with non-capture /dev/video* nodes.
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        pass

    # Allow forcing a camera index when device ordering is unstable.
    forced_index = os.getenv('CMPE246_CAMERA_INDEX')
    camera_indices = []
    if forced_index is not None:
        try:
            camera_indices.append(int(forced_index))
        except ValueError:
            print(f"Ignoring invalid CMPE246_CAMERA_INDEX value: {forced_index}")

    # Probe multiple candidates and keep only usable capture devices.
    for idx in [1, 0, 2, 3, 4, 5]:
        if idx not in camera_indices:
            camera_indices.append(idx)

    def _open_camera(index):
        backends = [cv2.CAP_V4L2, cv2.CAP_ANY]
        for backend in backends:
            camera = cv2.VideoCapture(index, backend)
            if not camera.isOpened():
                camera.release()
                continue

            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Validate that this device can actually produce frames.
            ok, frame = camera.read()
            if ok and frame is not None and frame.size > 0:
                return camera

            camera.release()
        return None

    available_camera_indices = []
    for idx in camera_indices:
        test_cap = _open_camera(idx)
        if test_cap is not None:
            available_camera_indices.append(idx)
            test_cap.release()

    if not available_camera_indices:
        print("Error: No valid video capture camera found")
        print("Tip: set CMPE246_CAMERA_INDEX to the correct camera index, e.g. CMPE246_CAMERA_INDEX=0")
        return None

    print(f"Available camera indices: {available_camera_indices}")
    current_camera_pos = 0
    cap = _open_camera(available_camera_indices[current_camera_pos])
    if cap is None:
        print("Error: Failed to open detected camera")
        return None
    
    photo_path = None
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture frame")
                break
            
            # Display preview
            cv2.putText(frame, "Press SPACE to capture, C to switch, Q to cancel",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Camera index: {available_camera_indices[current_camera_pos]}",
                        (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.imshow('Registration Photo - Position yourself', frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '):  # Space bar pressed
                # Create unique filename with timestamp
                timestamp = int(time.time())
                filename = f"{user_name.replace(' ', '_')}_{timestamp}.jpg"
                photo_path = os.path.join(DB_PATH, filename)
                
                # Save the photo
                cv2.imwrite(photo_path, frame)
                print(f"\n✓ Photo captured and saved to: {photo_path}")
                break
            elif key == ord('c'):
                if len(available_camera_indices) <= 1:
                    print("Only one usable camera detected")
                    continue

                next_camera_pos = (current_camera_pos + 1) % len(available_camera_indices)
                next_cap = _open_camera(available_camera_indices[next_camera_pos])
                if next_cap is None:
                    print(f"Camera {available_camera_indices[next_camera_pos]} is not available")
                else:
                    cap.release()
                    cap = next_cap
                    current_camera_pos = next_camera_pos
                    print(f"Switched to camera {available_camera_indices[current_camera_pos]}")
            elif key == ord('q'):  # Q pressed
                print("\nPhoto capture cancelled")
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    
    return photo_path

userList = load_users()
guestUser = User.User(name="Guest", focusTime=25, breakTime=5, light="default")

if __name__ == "__main__":
    Identify.identity_test()


def startup(registeredUser=False, userID=-1):
    if registeredUser:
        for user in userList:
            if user.userID == userID:
                user.start()
                return
        # If userID not found in list, it might be a new match from database
        print(f"Loading user from database: {userID}")
        # Could load user info from JSON here if needed
    else:
        print("\nWelcome to FocusBuddy! It looks like you are a new user. Register new user or continue as guest?")
        print("1. Continue as Guest")
        print("2. Register New User")
        choice = input("Enter the number of your choice: ")
        if choice == '1':
            print("Continuing as Guest with default settings...")
            guestUser.start()
        elif choice == '2':
            print("\nWelcome, let's get you set up!")
            
            # Find an open slot
            idx = -1
            for i, user in enumerate(userList):
                if user.userID == -1:
                    print(f"Open slot: {i}")
                    idx = i
                    break
            
            if idx == -1:
                print("Sorry, we are currently at maximum user capacity. Please try again later.")
                print("Continuing as Guest with default settings...")
                guestUser.start()
                return
            
            # Get user information
            name = input("Please enter your name: ")
            focusTime = int(input("Enter your desired focus time (in minutes): "))
            breakTime = int(input("Enter your desired break time (in minutes): "))
            light = input("Enter your preferred light setting: ")
            
            # Capture user photo
            print("\nNow let's take your photo for face recognition...")
            photo_path = capture_user_photo(name)
            
            if photo_path is None:
                print("Photo capture failed. Registration cancelled.")
                print("Continuing as Guest with default settings...")
                guestUser.start()
                return
            
            # Create a new user with the provided information
            newUser = User.User(
                userID=photo_path, 
                name=name, 
                focusTime=focusTime, 
                breakTime=breakTime, 
                light=light
            )
            userList[idx] = newUser
            
            # Save all user data to file
            save_users()
            
            print(f"\n✓ Registration successful! Welcome, {name}!")
            print(f"Your profile has been saved and you can now be recognized by the camera.")
            
            # Start the user session
            newUser.start()
        else:
            print("Invalid choice. Continuing as Guest...")
            guestUser.start()



