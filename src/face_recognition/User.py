class User:
    def __init__(self, userID=-1, name=None, focusTime=0, breakTime=0, light=None, audioFile=None):
        self.userID = userID #This is the path of their picture in the database, which will be used to pull their settings and reports
        self.name = name
        self.focusTime = focusTime
        self.breakTime = breakTime
        self.light = light
        self.audioFile = audioFile
        self.reportData = []
    
    def start(self):
        print("Welcome,", self.name + "!")
        self.options()


    def options(self):
        print("Current rhythm: Focus time -", self.focusTime, "minutes, Break time -", self.breakTime, "minutes.")
        print("Light setting:", self.light)
        print("Audio file:", self.audioFile)
        print("Reports available:", len(self.reportData))
        
        print(f"Options:")
        print(f"   1. Start Focus Session")
        print(f"   2. Settings")
        print(f"   3. View Reports")
        choice = input("What would you like to do? (Enter the number of your choice): ")
        if choice == '1':
            self.start_focus_session()
        elif choice == '2':
            self.update_settings()
        elif choice == '3':
            self.view_reports()
        else:
            print("Invalid choice. Please try again.")
    
    def start_focus_session(self):
        print("Starting focus session for", self.focusTime, "minutes. Enjoy your music:", self.audioFile)
        # Here you would add the logic to start the timer and play the audio file
    
    def update_settings(self):
        try:
            from . import testmain
        except ImportError:
            import testmain
        print("\n=== Settings Menu ===")
        print("1. Update Focus/Break Time")
        print("2. Update Light Setting")
        print("3. Update Audio File")
        print("4. Delete Profile")
        print("5. Back to Options")
        
        choice = input("Enter your choice: ")
        
        if choice == '1':
            self.focusTime = int(input("Enter new focus time (in minutes): "))
            self.breakTime = int(input("Enter new break time (in minutes): "))
            print("✓ Focus/break times updated successfully!")
            testmain.save_users()
            self.options()
        elif choice == '2':
            self.light = input("Enter new light setting: ")
            print("✓ Light setting updated successfully!")
            testmain.save_users()
            self.options()
        elif choice == '3':
            self.audioFile = input("Enter new audio file path: ")
            print("✓ Audio file updated successfully!")
            testmain.save_users()
            self.options()
        elif choice == '4':
            confirm = input(f"Are you sure you want to delete the profile for {self.name}? This cannot be undone. (yes/no): ")
            if confirm.lower() == 'yes':
                if testmain.delete_profile(self):
                    print("\nProfile deleted. Returning to startup...")
                    return  # Exit to main menu
                else:
                    print("Profile deletion failed. Returning to settings.")
                    self.update_settings()
            else:
                print("Profile deletion cancelled.")
                self.update_settings()
        elif choice == '5':
            self.options()
        else:
            print("Invalid choice. Please try again.")
            self.update_settings()
    
    def view_reports(self):
        print("Viewing reports...")
        if len(self.reportData) == 0:
            print("No reports available.")
        for idx, report in enumerate(self.reportData):
            print(f"Report {idx + 1}: {report}")
        self.options()