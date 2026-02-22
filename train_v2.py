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
    print("Step 1: Generating Data")
    n_samples = 1000
    data = []
    for _ in range(n_samples):
        s1, s2, s3 = np.random.randint(0, 101, 3)
        temp = np.random.randint(15, 45)
        humidity = np.random.randint(20, 100)
        rain = np.random.randint(0, 2)
        
        threshold = 30
        if temp > 35: threshold = 40
        if humidity > 80: threshold = 25
        
        if rain == 1:
            a1, a2, a3 = 0, 0, 0
        else:
            a1 = 1 if s1 < threshold else 0
            a2 = 1 if s2 < threshold else 0
            a3 = 1 if s3 < threshold else 0
            
        data.append([s1, s2, s3, temp, humidity, rain, a1, a2, a3])

    df = pd.DataFrame(data, columns=['soil1', 'soil2', 'soil3', 'temp', 'humidity', 'rain', 'p1', 'p2', 'p3'])
    
    print("Step 2: Split Data")
    X = df[['soil1', 'soil2', 'soil3', 'temp', 'humidity', 'rain']]
    y = df[['p1', 'p2', 'p3']]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Step 3: Training")
    forest = RandomForestClassifier(n_estimators=10) # Reduced for speed
    clf = MultiOutputClassifier(forest, n_jobs=1) # n_jobs=1 to avoid threading issues
    clf.fit(X_train, y_train)
    
    print("Step 4: Evaluating")
    y_pred = clf.predict(X_test)
    exact_match = accuracy_score(y_test, y_pred)
    print(f"Accuracy: {exact_match}")
    
    print("Step 5: Saving")
    with open('model.pkl', 'wb') as f:
        pickle.dump(clf, f)
    print("Done.")

except Exception:
    traceback.print_exc()
