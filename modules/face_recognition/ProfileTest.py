import pandas as pd
from typing import List
import os

from deepface import DeepFace
from testmain import startup

# Get the configurable database path
DB_PATH = os.getenv('CMPE246_DB_PATH', os.path.join(os.path.expanduser('~'), 'CMPE246_DB'))


def identity_test():
    # Example test image - replace with actual image path
    img1 = os.path.join(os.path.expanduser('~'), 'test_image.jpg')
    
    # Check if test image exists
    if not os.path.exists(img1):
        print(f"Test image not found at {img1}")
        print(f"Please provide a test image or update the path in ProfileTest.py")
        return
    
    # Check if database path exists
    if not os.path.exists(DB_PATH):
        print(f"Database path not found at {DB_PATH}")
        print(f"Please create the database directory and add face images")
        return
    
    #img2 = os.path.join(DB_PATH, 'Pic7.jpg')
    #img3 = os.path.join(DB_PATH, 'Pic9.jpg')
    #result: dict = DeepFace.verify(img1_path = img1, img2_path = img2, enforce_detection = False)
    #print(f"Verification result: {result}")
    
    print(f"Searching for face in database: {DB_PATH}")
    dfs: List[pd.DataFrame] = DeepFace.find(img_path = img1, db_path = DB_PATH, enforce_detection = False, refresh_database = True)
                                
    
    # print formatted results from the find call
    if dfs and len(dfs) > 0:
        result_df = dfs[0]
        if len(result_df) > 0:
            print(f"Found {len(result_df)} matching face(s):\n")
            for idx, row in result_df.iterrows():
                print(f"Match {idx + 1}:")
                print(f"  Identity: {row['identity']}")
                print(f"  Distance: {row['distance']:.4f}")
                print(f"  Confidence: {row['confidence']:.4f}")
                print()
            startup(registeredUser=True, userID=result_df.iloc[0]['identity'])
        else:
            print("No matching faces found in the database.")
            print()
            startup(registeredUser=False, userID=img1)
    else:
        print("No results returned from DeepFace.find().")

