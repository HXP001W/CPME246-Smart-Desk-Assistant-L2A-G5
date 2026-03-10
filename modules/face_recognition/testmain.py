
import User
import shutil
import ProfileTest
import os

# Configuration: Set database path via environment variable or use default
DB_PATH = os.getenv('CMPE246_DB_PATH', os.path.join(os.path.expanduser('~'), 'CMPE246_DB'))

userList = [User.User(userID=-1), User.User(userID=-1), User.User(userID=-1), User.User(userID=-1)]  # Initialize with empty users
guestUser = User.User(name="Guest", focusTime=25, breakTime=5, light="default", audioFile="default.mp3")

if __name__ == "__main__":
    ProfileTest.identity_test()


def startup(registeredUser=False, userID=-1):
    if registeredUser:
        for user in userList:
            if user.userID == userID:
                user.start()
                break
    else:
        print("Welcome to FocusBuddy! It looks like you are a new user. Register new user or continue as guest?")
        print("1. Continue as Guest")
        print("2. Register New User")
        choice = input("Enter the number of your choice: ")
        if choice == '1':
            print("Continuing as Guest with default settings...")
            guestUser.start()
        elif choice == '2':
            print("Welcome, let's get you set up!")
            idx = -1
            for user in userList:
                if user.userID == -1:
                    print("Open slot:", userList.index(user))
                    idx = userList.index(user)
                    break
            if idx == -1:
                print("Sorry, we are currently at maximum user capacity. Please try again later.")
                print("Continuing as Guest with default settings...")
                guestUser.start()
            name = input("Please enter your name: ")
            focusTime = int(input("Enter your desired focus time (in minutes): "))
            breakTime = int(input("Enter your desired break time (in minutes): "))
            light = input("Enter your preferred light setting: ")
            audioFile = input("Enter the path to your preferred audio file: ")
        
        # Create a new user with the provided information
        newUser = User.User(userID=userID, name=name, focusTime=focusTime, breakTime=breakTime, light=light, audioFile=audioFile)
        userList[idx] = newUser
        # Here you would add the logic to save the user's picture to the database and associate it with their userID
        # Define the source and destination paths
        # Use absolute or relative paths as strings or path-like objects
        source_path = userID
        destination_path = DB_PATH

        try:
            # Move the file
            shutil.move(source_path, destination_path)
            print(f"Moved '{source_path}' to '{destination_path}'")
        except FileNotFoundError:
            print(f"Error: The source file or destination directory was not found.")
        except Exception as e:
            print(f"An error occurred: {e}")
        newUser.userID = destination_path  # Update the userID to the path of their picture in the database
        
        print("Registration successful! Welcome,", name + "!")



