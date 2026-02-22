# 🌾 Agro AI - Intelligent Agricultural Management System
## Complete AI/ML Documentation

---

## Table of Contents
1. [System Overview](#1-system-overview)
2. [AI Architecture](#2-ai-architecture)
3. [Machine Learning Model](#3-machine-learning-model)
4. [Intelligent Features](#4-intelligent-features)
5. [Data Flow & Integration](#5-data-flow--integration)
6. [Decision Logic](#6-decision-logic)
7. [API Reference](#7-api-reference)
8. [Performance Metrics](#8-performance-metrics)
9. [Training Guide](#9-training-guide)
10. [Future Enhancements](#10-future-enhancements)

---

## 1. System Overview

The **Agro AI** system is an intelligent IoT-based agricultural management platform that combines hardware sensors (ESP32), machine learning models, and real-time analytics to automate and optimize irrigation decisions.

### Key Components
```
┌─────────────────────────────────────────────────────────────────┐
│                      AGRO AI ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   ESP32      │───▶│   Flask      │───▶│   Web        │       │
│  │   Hardware   │    │   Server     │    │   Dashboard  │       │
│  │   Sensors    │◀───│   + AI       │◀───│   (React)    │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                   │                    │               │
│         ▼                   ▼                    ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ BME280       │    │ Random       │    │ Real-time    │       │
│  │ Soil Sensors │    │ Forest ML    │    │ Charts &     │       │
│  │ PIR, LDR     │    │ Model        │    │ Alerts       │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### AI Capabilities
- **Irrigation Prediction**: ML-based pump control recommendations
- **Weather Analysis**: Barometric pressure trend analysis
- **Evapotranspiration Calculation**: FAO-standard ET estimation
- **Crop Stress Monitoring**: Real-time plant health assessment
- **Smart Insights**: Context-aware agricultural recommendations

---

## 2. AI Architecture

### 2.1 Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| ML Framework | scikit-learn | Model training & inference |
| Algorithm | Random Forest | Multi-output classification |
| Data Processing | pandas, numpy | Feature engineering |
| Serialization | pickle, JSON | Model persistence |
| Deployment | Flask | Real-time inference API |
| Communication | SSE | Live dashboard updates |

### 2.2 Model Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 MULTI-OUTPUT RANDOM FOREST                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INPUT FEATURES (7)              OUTPUT TARGETS (3)              │
│  ─────────────────              ────────────────────             │
│  ┌─────────────┐                ┌─────────────────┐              │
│  │ soil1       │                │ pump1 (Zone α)  │──▶ ON/OFF    │
│  │ soil2       │    ┌───────┐   │                 │              │
│  │ soil3       │───▶│  100  │──▶│ pump2 (Zone β)  │──▶ ON/OFF    │
│  │ temperature │    │ Trees │   │                 │              │
│  │ humidity    │    └───────┘   │ pump3 (Paddy)   │──▶ ON/OFF    │
│  │ rain        │                └─────────────────┘              │
│  │ pressure    │                                                 │
│  └─────────────┘                                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Machine Learning Model

### 3.1 Input Features

| Feature | Range | Unit | Description |
|---------|-------|------|-------------|
| `soil1` | 0-100 | % | Zone Alpha soil moisture |
| `soil2` | 0-100 | % | Zone Beta soil moisture |
| `soil3` | 0-100 | % | Zone Gamma/Paddy moisture |
| `temp` | 5-48 | °C | Ambient temperature |
| `humidity` | 15-98 | % | Relative humidity |
| `rain` | 0/1 | binary | Rain detection flag |
| `pressure` | 980-1035 | hPa | Barometric pressure |

### 3.2 Output Targets

| Target | Values | Description |
|--------|--------|-------------|
| `p1` | 0/1 | Pump 1 (Zone Alpha) ON/OFF |
| `p2` | 0/1 | Pump 2 (Zone Beta) ON/OFF |
| `p3` | 0/1 | Pump 3 (Paddy Field) ON/OFF |

### 3.3 Model Parameters

```python
RandomForestClassifier(
    n_estimators=100,      # Number of decision trees
    max_depth=15,          # Maximum tree depth
    min_samples_split=5,   # Minimum samples to split
    min_samples_leaf=2,    # Minimum samples per leaf
    random_state=42        # Reproducibility seed
)
```

### 3.4 Why Random Forest?

1. **Robustness**: Handles noisy sensor data effectively
2. **Non-linear Relationships**: Captures complex interactions (temp × humidity effects)
3. **Feature Importance**: Provides interpretable insights
4. **No Scaling Required**: Works with raw sensor values
5. **Fast Inference**: Sub-millisecond predictions

---

## 4. Intelligent Features

### 4.1 Evapotranspiration (ET) Calculation

The system uses a simplified Penman-Monteith equation to estimate water loss:

```python
def calculate_evapotranspiration(temp, humidity):
    """
    Calculate ET factor (0-1 scale)
    Based on FAO-56 simplified formula
    """
    # Saturation vapor pressure
    es = 0.6108 * exp((17.27 * temp) / (temp + 237.3))
    
    # Actual vapor pressure
    ea = es * (humidity / 100)
    
    # Vapor Pressure Deficit
    vpd = es - ea
    
    # Normalized ET factor
    et_factor = vpd / 5
    return clip(et_factor, 0, 1)
```

**ET Factor Interpretation:**
- `0.0 - 0.3`: Low evaporation (humid, cool)
- `0.3 - 0.6`: Moderate evaporation (normal)
- `0.6 - 1.0`: High evaporation (hot, dry) → Water more

### 4.2 Crop Stress Index

Real-time plant stress assessment combining multiple factors:

```python
def calculate_crop_stress(temp, humidity, soil_moisture):
    """
    Calculate stress index (0-100)
    Higher = More urgent need for attention
    """
    stress = 0
    
    # Heat stress component
    if temp > 35:  # Heat stress threshold
        stress += (temp - 35) * 4
    
    # Moisture stress component
    if soil_moisture < 20:  # Critical dry
        stress += (20 - soil_moisture) * 3
    elif soil_moisture < 30:  # Dry threshold
        stress += (30 - soil_moisture) * 1.5
    
    # Atmospheric stress
    if humidity < 40:  # Dry air
        stress += (40 - humidity) * 0.5
    
    return clip(stress, 0, 100)
```

**Stress Level Actions:**
| Stress Index | Level | Action |
|--------------|-------|--------|
| 0-20 | Low | Normal monitoring |
| 20-40 | Moderate | Increased monitoring |
| 40-60 | High | Irrigation recommended |
| 60-100 | Critical | Immediate irrigation |

### 4.3 Weather Trend Analysis

Barometric pressure-based weather prediction:

```python
def analyze_weather_trend(pressure, rain):
    """
    Predict weather conditions from pressure
    """
    if rain:
        return "raining"
    elif pressure < 1000:
        return "storm_imminent"  # Storm within hours
    elif pressure < 1005:
        return "unsettled"       # Possible rain
    elif pressure > 1020:
        return "clear"           # Stable, dry
    else:
        return "stable"          # Normal conditions
```

### 4.4 Smart Insights Engine

The AI generates contextual insights based on conditions:

| Condition | Insight Generated |
|-----------|-------------------|
| ET > 0.6, no rain | "☀️ High Evaporation Rate. Water loss accelerated." |
| Stress > 50 | "🌡️ Crop Stress Alert: Index at X/100" |
| Pressure < 1000 | "🌩️ Storm Imminent. Irrigation suspended." |
| 6-8 AM | "🌅 Morning optimal watering window." |
| 11 AM - 2 PM, temp > 30 | "⚠️ Midday heat. Avoiding irrigation." |
| Zone variance > 20% | "📉 Uneven moisture distribution detected." |

---

## 5. Data Flow & Integration

### 5.1 Real-time Data Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA FLOW                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ESP32 Sensors ──(HTTP POST)──▶ /api/update_sensors             │
│         │                              │                         │
│         │                              ▼                         │
│         │                     ┌─────────────────┐               │
│         │                     │  State Update   │               │
│         │                     │  + History Log  │               │
│         │                     └────────┬────────┘               │
│         │                              │                         │
│         │                              ▼                         │
│         │                     ┌─────────────────┐               │
│         │                     │   ML Model      │               │
│         │                     │   Prediction    │               │
│         │                     └────────┬────────┘               │
│         │                              │                         │
│         │                              ▼                         │
│         │                     ┌─────────────────┐               │
│         │                     │  SSE Events     │───▶ Dashboard │
│         │                     │  (ai_decision,  │               │
│         │                     │   sys_log)      │               │
│         ▼                     └─────────────────┘               │
│                                                                  │
│  Dashboard ◀──(SSE Stream)──── /events                          │
│         │                                                        │
│         └──(HTTP GET)──────── /api/sensors                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Update Frequency

| Component | Frequency | Purpose |
|-----------|-----------|---------|
| Sensor Update | 2 seconds | ESP32 → Server |
| AI Prediction | 3 seconds | Server → Dashboard |
| AI Insights | 15 seconds | Context-aware tips |
| Dashboard Render | 2 seconds | UI refresh |

---

## 6. Decision Logic

### 6.1 Training Rules

The AI model is trained on synthetic data generated with these agronomic rules:

```python
# Base moisture threshold
threshold = 30  # % soil moisture

# Rule 1: Temperature adjustment
if temp > 35:  # Heat stress
    threshold += 15  # Water earlier
elif temp > 30:
    threshold += 8

# Rule 2: Humidity adjustment
if humidity < 40:  # Dry air
    threshold += 10  # Higher evaporation
elif humidity > 80:  # Humid
    threshold -= 10  # Lower evaporation

# Rule 3: Rain override
if rain == 1:
    pump1 = pump2 = pump3 = 0  # ALL OFF

# Rule 4: Storm prediction
if pressure < 1000:
    pump1 = pump2 = pump3 = 0  # Save water

# Rule 5: Critical override
if soil < 20 and rain == 0:
    pump = 1  # Always water if critical

# Rule 6: Saturation protection
if soil > 85:
    pump = 0  # Never over-water
```

### 6.2 Decision Matrix

| Soil (%) | Rain | Temp (°C) | Humidity (%) | Pressure | Decision |
|----------|------|-----------|--------------|----------|----------|
| < 20 | 0 | Any | Any | > 1000 | **IRRIGATE** (Critical) |
| 20-30 | 0 | < 30 | > 60 | > 1005 | **IRRIGATE** (Normal) |
| 20-30 | 0 | > 35 | Any | > 1005 | **IRRIGATE** (Heat stress) |
| 30-40 | 0 | > 35 | < 40 | > 1005 | **IRRIGATE** (High ET) |
| Any | 1 | Any | Any | Any | **NO IRRIGATION** (Rain) |
| Any | 0 | Any | Any | < 1000 | **NO IRRIGATION** (Storm) |
| > 70 | 0 | Any | Any | Any | **NO IRRIGATION** (Optimal) |
| > 85 | Any | Any | Any | Any | **NO IRRIGATION** (Saturated) |

---

## 7. API Reference

### 7.1 Get AI Status

```http
GET /api/ai_status
```

**Response:**
```json
{
    "model_loaded": true,
    "model_version": "3.0",
    "model_accuracy": {
        "exact_match": 94.5,
        "pump1": 97.2,
        "pump2": 97.8,
        "pump3": 98.1
    },
    "predictions_made": 1542,
    "insights_generated": 89,
    "last_prediction": [0, 1, 0],
    "evaporation_factor": 0.45,
    "crop_stress_index": 23.5,
    "weather_trend": "stable",
    "water_saved_actions": 12
}
```

### 7.2 Get Sensors with AI Metrics

```http
GET /api/sensors
```

**Response includes:**
```json
{
    "temp": 28.5,
    "humidity": 65,
    "pressure": 1013,
    "soil1": 45,
    "soil2": 52,
    "rain": 0,
    "ai_metrics": {
        "evaporation_factor": 0.35,
        "crop_stress_index": 15.2,
        "weather_trend": "stable",
        "predictions_made": 1542
    },
    "ai_status": {
        "active": true,
        "last_decision": "Monitoring",
        "confidence": 92
    }
}
```

### 7.3 SSE Events Stream

```http
GET /events
```

**Event Types:**
| Event | Data Format | Description |
|-------|-------------|-------------|
| `ai_decision` | String | AI recommendation/action |
| `sys_log` | String | System logs & insights |

---

## 8. Performance Metrics

### 8.1 Model Accuracy (v3.0)

| Metric | Score | Description |
|--------|-------|-------------|
| **Global Exact Match** | 94.5% | All 3 pumps correct |
| **Zone Alpha Accuracy** | 97.2% | Pump 1 predictions |
| **Zone Beta Accuracy** | 97.8% | Pump 2 predictions |
| **Paddy Field Accuracy** | 98.1% | Pump 3 predictions |

### 8.2 Feature Importance

```
soil1        0.312 ████████████████
soil2        0.298 ███████████████
soil3        0.187 █████████
rain         0.089 ████
temp         0.056 ██
humidity     0.035 █
pressure     0.023 █
```

### 8.3 Inference Performance

| Metric | Value |
|--------|-------|
| Prediction Time | < 5ms |
| Memory Usage | ~50MB |
| Update Frequency | 3 seconds |

---

## 9. Training Guide

### 9.1 Quick Start

```bash
# Navigate to project directory
cd "c:\Users\noyel\Desktop\Projects\Iot AI"

# Train the enhanced model
python train_model_v3.py

# Verify model
python evaluate_model.py
```

### 9.2 Training Output

```
============================================================
AGRO AI - ADVANCED MODEL TRAINING v3.0
============================================================

📊 Generating 10000 training samples...
✅ Generated 10000 samples

📊 PERFORMANCE METRICS:
   Global Exact Match Accuracy: 94.50%
   Zone Alpha (Div 1): 97.20%
   Zone Beta (Div 2): 97.80%
   Paddy Field (Div 3): 98.10%

✅ Model saved to model.pkl
✅ Metadata saved to model_metadata.json
```

### 9.3 Custom Training

Modify `train_model_v3.py` configuration:

```python
CONFIG = {
    "n_samples": 10000,      # Increase for better accuracy
    "n_estimators": 100,     # More trees = better but slower
    "test_size": 0.2,        # 80/20 train/test split
}

# Adjust agricultural thresholds
AGRO_CONSTANTS = {
    "DRY_THRESHOLD": 30,     # Lower = water sooner
    "HEAT_STRESS": 35,       # Temperature alert threshold
    "LOW_PRESSURE": 1005,    # Storm warning threshold
}
```

---

## 10. Future Enhancements

### 10.1 Planned Features

| Feature | Description | Priority |
|---------|-------------|----------|
| **LSTM Weather Prediction** | Multi-day forecast using pressure history | High |
| **Computer Vision** | Leaf health analysis via camera | Medium |
| **Reinforcement Learning** | Self-optimizing irrigation schedules | Medium |
| **Federated Learning** | Cross-farm model improvement | Low |

### 10.2 Sensor Additions

- **Leaf Wetness Sensor**: Disease prediction
- **EC Sensor**: Nutrient monitoring
- **pH Sensor**: Soil acidity management
- **Pyranometer**: Solar radiation for precise ET

### 10.3 Model Improvements

```python
# Planned: Gradient Boosting ensemble
from sklearn.ensemble import GradientBoostingClassifier

# Planned: Time-series features
features += ['soil1_delta', 'temp_trend', 'pressure_6h_change']

# Planned: Crop-specific models
models = {
    'rice': load('rice_model.pkl'),
    'wheat': load('wheat_model.pkl'),
    'vegetables': load('veg_model.pkl')
}
```

---

## Appendix A: Agricultural Constants

```python
AGRO_CONSTANTS = {
    # Soil Moisture Thresholds (%)
    "CRITICAL_DRY": 20,      # Wilting point risk
    "DRY_THRESHOLD": 30,     # Irrigation trigger
    "OPTIMAL_LOW": 40,       # Optimal range start
    "OPTIMAL_HIGH": 70,      # Optimal range end
    "SATURATED": 85,         # Over-watering risk
    
    # Temperature Thresholds (°C)
    "FROST_RISK": 5,         # Frost protection
    "COLD": 15,              # Reduced growth
    "OPTIMAL_TEMP_LOW": 20,  # Optimal growth
    "OPTIMAL_TEMP_HIGH": 30, # Optimal growth
    "HEAT_STRESS": 35,       # Plant stress
    "EXTREME_HEAT": 40,      # Critical stress
    
    # Pressure Thresholds (hPa)
    "STORM_IMMINENT": 1000,  # Storm likely
    "LOW_PRESSURE": 1005,    # Unsettled
    "NORMAL_PRESSURE": 1013, # Standard ATM
    "HIGH_PRESSURE": 1020,   # Clear weather
}
```

---

## Appendix B: File Structure

```
Iot AI/
├── server.py              # Flask server + AI integration
├── train_model_v3.py      # Enhanced model training
├── model.pkl              # Trained ML model
├── model_metadata.json    # Model performance metadata
├── index.html             # Web dashboard
├── script.js              # Frontend logic
├── style.css              # Dashboard styling
├── sketch_jan8a/
│   └── sketch_jan8a.ino   # ESP32 firmware
└── AI_DOCUMENTATION.md    # This file
```

---

**Document Version:** 3.0  
**Last Updated:** January 2026  
**Author:** Agro AI Development Team
