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
        print("Welcome,", self.name, "!")
        self.options()


    def options(self):
        print("Current rhythm: Focus time -", self.focusTime, "minutes, Break time -", self.breakTime, "minutes.")
        print("Light setting:", self.light)
        print("Audio file:", self.audioFile)
        print("Reports available:", len(self.reportData))
        
        print(f"Options:")
        print(f"   1. Start Focus Session")
        print(f"   2. Update Settings")
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
        print("Updating settings...")
        self.focusTime = int(input("Enter new focus time (in minutes): "))
        self.breakTime = int(input("Enter new break time (in minutes): "))
        self.light = input("Enter new light setting: ")
        self.audioFile = input("Enter new audio file path: ")
        print("Settings updated successfully!")
        self.options()
    
    def view_reports(self):
        print("Viewing reports...")
        if len(self.reportData) == 0:
            print("No reports available.")
        for idx, report in enumerate(self.reportData):
            print(f"Report {idx + 1}: {report}")
        self.options