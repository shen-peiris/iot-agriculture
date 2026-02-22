# Smart Irrigation AI Model Documentation

## Overview
This document details the Machine Learning model powering the **Smart Irrigation System**. The model is designed to make real-time decisions on whether to activate water pumps for three different agricultural divisions based on environmental sensor data.

## 1. Technology Stack
The AI component is built using Python's robust data science ecosystem:

-   **Language**: Python 3.x
-   **Machine Learning Library**: `scikit-learn` (for Random Forest and MultiOutput classification)
-   **Data Manipulation**: `pandas`, `numpy`
-   **Serialization**: `pickle` (for saving/loading the trained model)
-   **Deployment**: Integrated into a `Flask` web server for real-time inference.

## 2. Model Architecture
The system uses a **Multi-Output Random Forest Classifier**.

-   **Algorithm**: `RandomForestClassifier`
-   **Wrapper**: `MultiOutputClassifier` (This allows the model to predict the status of 3 separate pumps simultaneously in a single inference step).
-   **Estimators**: 50 Decision Trees (balanced for performance/accuracy).

### Why Random Forest?
Random Forest was chosen for its:
1.  **Robustness** against noise in sensor data.
2.  **Ability to handle non-linear relationships** (e.g., how temperature thresholds shift based on humidity).
3.  **Interpretability** and feature importance tracking.

## 3. Data & Training Logic
The model is trained on a synthetic dataset designed to mimic real-world agricultural scenarios with specific logic.

### Input Features (6 Variables)
The model accepts 6 environmental parameters:
1.  **`soil1`** (0-100): Moisture level of Division 1.
2.  **`soil2`** (0-100): Moisture level of Division 2.
3.  **`soil3`** (0-100): Moisture level of Division 3.
4.  **`temp`** (°C): Ambient temperature (15-45).
5.  **`humidity`** (%): Ambient humidity (20-100).
6.  **`rain`** (Binary): 1 if raining, 0 if not.

### Output Targets (3 Variables)
The model predicts the state of 3 pumps:
-   **`p1`**: Pump 1 ON/OFF (1/0)
-   **`p2`**: Pump 2 ON/OFF (1/0)
-   **`p3`**: Pump 3 ON/OFF (1/0)

### Decision Logic (The "Brain")
The training data was generated using the following agronomic rules:
1.  **Rain Override**: If it is raining (`rain == 1`), ALL pumps are OFF.
2.  **Dynamic Thresholds**:
    -   Base moisture threshold: **30%** (Below this, pump turns ON).
    -   **High Heat Exception**: If `temp > 35°C`, the threshold increases to **40%** (Plants need water sooner).
    -   **High Humidity Exception**: If `humidity > 80%`, the threshold decreases to **25%** (Plants transpire less).
3.  **Independent Control**: Each division is evaluated independently against these thresholds based on its specific soil moisture sensor.

## 4. Performance Evaluation
Based on a recent evaluation of 1000 test samples:

| Metric | Accuracy | Note |
| :--- | :--- | :--- |
| **Global Exact Match** | **93.70%** | Probability of getting ALL 3 pump states right simultaneously. |
| **Pump 1 Accuracy** | 97.30% | Individual accuracy for Division 1. |
| **Pump 2 Accuracy** | 97.60% | Individual accuracy for Division 2. |
| **Pump 3 Accuracy** | 98.30% | Individual accuracy for Division 3. |

*Note: The model achieves high accuracy, effectively replicating the logic rules defined during training.*

## 5. Integration Workflow
1.  **Sensors -> Server**: Hardware (ESP32) sends real-time data or the server simulates it (`server.py`).
2.  **Inference**: The server loads `model.pkl`.
3.  **Prediction**: Every 3 seconds, the server feeds the current state `[s1, s2, s3, temp, hum, rain]` into the model.
4.  **Decision**: The model returns `[p1, p2, p3]`.
    -   If `p1=1`, the system recommends watering Division 1.
    -   (Server logic handles the "Recommendation" vs "Auto-Action" switch).
5.  **Feedback**: The decision is streamed to the frontend via Server-Sent Events (SSE).
