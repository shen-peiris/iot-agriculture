import pandas as pd
import numpy as np
import traceback
from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import pickle

print("Step 0: Imports done")

try:
    print("Step 1: Generating Advanced Synthetic Data")
    n_samples = 5000
    data = []
    
    for _ in range(n_samples):
        # inputs
        s1, s2, s3 = np.random.randint(0, 101, 3)
        temp = np.random.randint(15, 45)
        humidity = np.random.randint(20, 100)
        rain = np.random.randint(0, 2)
        pressure = np.random.randint(980, 1030) # New Feature
        
        # logic
        threshold = 30
        if temp > 35: threshold = 40
        if humidity > 80: threshold = 25
        
        # Storm Logic: If pressure is low, rain is likely coming. save water.
        storm_risk = pressure < 1005
        
        if rain == 1 or storm_risk:
            # If raining OR storm approaching, don't water
            a1, a2, a3 = 0, 0, 0
        else:
            a1 = 1 if s1 < threshold else 0
            a2 = 1 if s2 < threshold else 0
            a3 = 1 if s3 < threshold else 0
            
        data.append([s1, s2, s3, temp, humidity, rain, pressure, a1, a2, a3])

    df = pd.DataFrame(data, columns=['soil1', 'soil2', 'soil3', 'temp', 'humidity', 'rain', 'pressure', 'p1', 'p2', 'p3'])
    
    print("Step 2: Split Data")
    X = df[['soil1', 'soil2', 'soil3', 'temp', 'humidity', 'rain', 'pressure']]
    y = df[['p1', 'p2', 'p3']]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Step 3: Training with MultiOutputClassifier")
    # Using n_jobs=1 to ensure stability in all environments
    forest = RandomForestClassifier(n_estimators=50, random_state=42)
    clf = MultiOutputClassifier(forest, n_jobs=1)
    clf.fit(X_train, y_train)
    
    print("Step 4: Evaluating")
    y_pred = clf.predict(X_test)
    exact_match = accuracy_score(y_test, y_pred)
    print(f"Global Exact Match Accuracy: {exact_match * 100:.2f}%")
    
    # Check individual pump accuracy
    p1_acc = accuracy_score(y_test['p1'], y_pred[:, 0])
    print(f"Pump 1 Logic Accuracy: {p1_acc * 100:.2f}%")
    
    print("Step 5: Saving Model")
    with open('model.pkl', 'wb') as f:
        pickle.dump(clf, f)
    print("Smart AI Model saved to model.pkl successfully.")

except Exception:
    traceback.print_exc()
