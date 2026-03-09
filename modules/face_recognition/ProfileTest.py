import pandas as pd
from typing import List

from deepface import DeepFace
from testmain import startup



def identity_test():
    img1 = r"C:\Users\lkkal\Stinky.jpg"
    #img2 = r"C:\Users\lkkal\CMPE246 DB\Pic7.jpg"
    #img3 = r"C:\Users\lkkal\CMPE246 DB\Pic9.jpg"
    #result: dict = DeepFace.verify(img1_path = img1, img2_path = img2, enforce_detection = False)
    #print(f"Verification result: {result}")
    dfs: List[pd.DataFrame] = DeepFace.find(img_path = img1, db_path = r"C:\Users\lkkal\CMPE246 DB", enforce_detection = False, refresh_database = True)
                                
    
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

