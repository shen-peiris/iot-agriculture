import pandas as pd
import numpy as np
import pickle
from sklearn.metrics import accuracy_score

def generate_data(n_samples=1000):
    data = []
    for _ in range(n_samples):
        # inputs
        s1, s2, s3 = np.random.randint(0, 101, 3)
        temp = np.random.randint(15, 45)
        humidity = np.random.randint(20, 100)
        rain = np.random.randint(0, 2)
        
        # logic
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
    
    return pd.DataFrame(data, columns=['soil1', 'soil2', 'soil3', 'temp', 'humidity', 'rain', 'p1', 'p2', 'p3'])

def evaluate():
    try:
        print("Loading model.pkl...")
        with open('model.pkl', 'rb') as f:
            clf = pickle.load(f)
        
        print("Generating test data...")
        df = generate_data(1000)
        
        X = df[['soil1', 'soil2', 'soil3', 'temp', 'humidity', 'rain']]
        y_true = df[['p1', 'p2', 'p3']]
        
        print("Predicting...")
        y_pred = clf.predict(X)
        
        exact_match = accuracy_score(y_true, y_pred)
        print(f"Global Exact Match Accuracy: {exact_match * 100:.2f}%")
        
        # Individual pump accuracy
        p1_acc = accuracy_score(y_true['p1'], y_pred[:, 0])
        p2_acc = accuracy_score(y_true['p2'], y_pred[:, 1])
        p3_acc = accuracy_score(y_true['p3'], y_pred[:, 2])
        
        print(f"Pump 1 Accuracy: {p1_acc * 100:.2f}%")
        print(f"Pump 2 Accuracy: {p2_acc * 100:.2f}%")
        print(f"Pump 3 Accuracy: {p3_acc * 100:.2f}%")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    evaluate()
