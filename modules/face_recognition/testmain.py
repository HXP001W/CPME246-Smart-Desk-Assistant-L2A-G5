
import User
import shutil
import ProfileTest
import os
import cv2
import json
import time

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
                        light=user_data.get('light'),
                        audioFile=user_data.get('audioFile')
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
                    'light': user.light,
                    'audioFile': user.audioFile
                })
        with open(USER_DATA_FILE, 'w') as f:
            json.dump(users_data, f, indent=2)
        print(f"User data saved to {USER_DATA_FILE}")
    except Exception as e:
        print(f"Error saving user data: {e}")

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
    print("Press SPACE to capture, or 'q' to cancel")
    
    # Try front camera first (usually index 1), fallback to 0
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("Front camera not available, trying alternate camera...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: No camera available")
            return None
    
    photo_path = None
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture frame")
                break
            
            # Display preview
            cv2.putText(frame, "Press SPACE to capture, Q to cancel", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
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
            elif key == ord('q'):  # Q pressed
                print("\nPhoto capture cancelled")
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    
    return photo_path

userList = load_users()
guestUser = User.User(name="Guest", focusTime=25, breakTime=5, light="default", audioFile="default.mp3")

if __name__ == "__main__":
    ProfileTest.identity_test()


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
            audioFile = input("Enter the path to your preferred audio file: ")
            
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
                light=light, 
                audioFile=audioFile
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



