"""
================================================================================
AGRO AI - ADVANCED SMART IRRIGATION MODEL v3.0
================================================================================
Enhanced Machine Learning Model for Intelligent Agricultural Management

Features:
- Multi-Output Classification for 3 irrigation zones
- Weather-aware decision making (temperature, humidity, pressure, rain)
- Evapotranspiration (ET) calculation
- Storm prediction based on barometric pressure
- Time-of-day awareness for optimal watering schedules
- Crop stress index calculation
- Water conservation optimization

Author: Agro AI System
Version: 3.0
================================================================================
"""

import pandas as pd
import numpy as np
import traceback
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.multioutput import MultiOutputClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
import pickle
import json
from datetime import datetime

print("=" * 60)
print("AGRO AI - ADVANCED MODEL TRAINING v3.0")
print("=" * 60)

# ============================================================================
# CONFIGURATION
# ============================================================================
CONFIG = {
    "n_samples": 10000,          # Training samples
    "n_estimators": 100,         # Random Forest trees
    "test_size": 0.2,            # Test split ratio
    "random_state": 42,          # Reproducibility seed
    "model_path": "model.pkl",
    "metadata_path": "model_metadata.json"
}

# ============================================================================
# AGRICULTURAL CONSTANTS (Based on FAO Guidelines)
# ============================================================================
AGRO_CONSTANTS = {
    # Soil moisture thresholds (%)
    "CRITICAL_DRY": 20,          # Wilting point risk
    "DRY_THRESHOLD": 30,         # Irrigation trigger
    "OPTIMAL_LOW": 40,           # Optimal range start
    "OPTIMAL_HIGH": 70,          # Optimal range end
    "SATURATED": 85,             # Over-watering risk
    
    # Temperature thresholds (°C)
    "FROST_RISK": 5,             # Frost protection needed
    "COLD": 15,                  # Reduced ET
    "OPTIMAL_TEMP_LOW": 20,      # Optimal growth
    "OPTIMAL_TEMP_HIGH": 30,     # Optimal growth
    "HEAT_STRESS": 35,           # Plant stress begins
    "EXTREME_HEAT": 40,          # Critical stress
    
    # Pressure thresholds (hPa)
    "STORM_IMMINENT": 1000,      # Storm likely within hours
    "LOW_PRESSURE": 1005,        # Unsettled weather
    "NORMAL_PRESSURE": 1013,     # Standard atmosphere
    "HIGH_PRESSURE": 1020,       # Stable, clear weather
    
    # Humidity thresholds (%)
    "VERY_DRY_AIR": 30,          # High evaporation
    "DRY_AIR": 40,               # Increased ET
    "COMFORTABLE": 60,           # Normal conditions
    "HUMID": 80,                 # Reduced ET
    "VERY_HUMID": 90             # Disease risk
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_evapotranspiration(temp, humidity, wind_speed=2.0):
    """
    Simplified Penman-Monteith ET0 calculation
    Returns: ET rate (mm/day equivalent factor)
    """
    # Saturation vapor pressure (simplified)
    es = 0.6108 * np.exp((17.27 * temp) / (temp + 237.3))
    # Actual vapor pressure
    ea = es * (humidity / 100)
    # Vapor pressure deficit
    vpd = es - ea
    
    # Simplified ET factor (0-1 scale)
    et_factor = (vpd * (1 + 0.34 * wind_speed)) / 10
    return np.clip(et_factor, 0, 1)

def calculate_crop_stress_index(temp, humidity, soil_moisture):
    """
    Calculate plant stress index (0-100)
    Higher = More stress = More urgent irrigation
    """
    stress = 0
    
    # Temperature stress
    if temp > AGRO_CONSTANTS["HEAT_STRESS"]:
        stress += (temp - AGRO_CONSTANTS["HEAT_STRESS"]) * 5
    elif temp < AGRO_CONSTANTS["COLD"]:
        stress += (AGRO_CONSTANTS["COLD"] - temp) * 2
    
    # Moisture stress
    if soil_moisture < AGRO_CONSTANTS["CRITICAL_DRY"]:
        stress += (AGRO_CONSTANTS["CRITICAL_DRY"] - soil_moisture) * 3
    elif soil_moisture < AGRO_CONSTANTS["DRY_THRESHOLD"]:
        stress += (AGRO_CONSTANTS["DRY_THRESHOLD"] - soil_moisture) * 1.5
    
    # Humidity stress (VPD effect)
    if humidity < AGRO_CONSTANTS["VERY_DRY_AIR"]:
        stress += (AGRO_CONSTANTS["VERY_DRY_AIR"] - humidity) * 0.5
    
    return np.clip(stress, 0, 100)

def get_weather_condition(pressure, rain, humidity):
    """
    Classify weather conditions for decision making
    Returns: condition code (0-4)
    """
    if rain == 1:
        return 4  # Raining
    elif pressure < AGRO_CONSTANTS["STORM_IMMINENT"]:
        return 3  # Storm imminent
    elif pressure < AGRO_CONSTANTS["LOW_PRESSURE"]:
        return 2  # Unsettled
    elif humidity > AGRO_CONSTANTS["VERY_HUMID"]:
        return 1  # Very humid
    else:
        return 0  # Clear/Normal

def calculate_irrigation_priority(soil_moisture, temp, humidity, pressure, rain):
    """
    Calculate irrigation priority score (0-100)
    Higher = More urgent need for irrigation
    """
    if rain == 1:
        return 0  # No irrigation during rain
    
    priority = 0
    
    # Base priority from soil moisture (inverted - lower moisture = higher priority)
    moisture_deficit = max(0, AGRO_CONSTANTS["OPTIMAL_LOW"] - soil_moisture)
    priority += moisture_deficit * 1.5
    
    # Temperature modifier
    if temp > AGRO_CONSTANTS["HEAT_STRESS"]:
        priority += (temp - AGRO_CONSTANTS["HEAT_STRESS"]) * 2
    
    # ET modifier
    et = calculate_evapotranspiration(temp, humidity)
    priority += et * 20
    
    # Weather forecast modifier (reduce if rain coming)
    if pressure < AGRO_CONSTANTS["LOW_PRESSURE"]:
        priority *= 0.5  # Halve priority if storm approaching
    
    return np.clip(priority, 0, 100)

# ============================================================================
# DATA GENERATION
# ============================================================================

def generate_advanced_training_data(n_samples):
    """
    Generate sophisticated synthetic training data with realistic scenarios
    """
    print(f"\n📊 Generating {n_samples} training samples...")
    data = []
    
    for i in range(n_samples):
        # ---- INPUT FEATURES ----
        # Soil moisture (3 zones with some correlation)
        base_moisture = np.random.randint(10, 90)
        s1 = np.clip(base_moisture + np.random.randint(-20, 20), 0, 100)
        s2 = np.clip(base_moisture + np.random.randint(-20, 20), 0, 100)
        s3 = np.clip(base_moisture + np.random.randint(-20, 20), 0, 100)
        
        # Temperature (with realistic distribution)
        temp = int(np.random.normal(28, 8))
        temp = np.clip(temp, 5, 48)
        
        # Humidity (inversely correlated with temp somewhat)
        base_humidity = 70 - (temp - 25) * 1.5
        humidity = int(np.clip(base_humidity + np.random.randint(-20, 20), 15, 98))
        
        # Barometric pressure
        pressure = int(np.random.normal(1013, 12))
        pressure = np.clip(pressure, 980, 1035)
        
        # Rain (more likely if low pressure)
        rain_probability = 0.1 if pressure > 1010 else 0.4 if pressure > 1000 else 0.7
        rain = 1 if np.random.random() < rain_probability else 0
        
        # Light level (LDR) - 0-4095, higher = darker
        hour = np.random.randint(0, 24)
        if 6 <= hour <= 18:  # Daytime
            ldr = np.random.randint(100, 1500)
        else:  # Nighttime
            ldr = np.random.randint(2500, 4000)
        
        # ---- DERIVED FEATURES ----
        et_factor = calculate_evapotranspiration(temp, humidity)
        stress_index = np.mean([
            calculate_crop_stress_index(temp, humidity, s1),
            calculate_crop_stress_index(temp, humidity, s2),
            calculate_crop_stress_index(temp, humidity, s3)
        ])
        weather_code = get_weather_condition(pressure, rain, humidity)
        
        # ---- OUTPUT LABELS (Intelligent Logic) ----
        # Dynamic threshold based on conditions
        base_threshold = AGRO_CONSTANTS["DRY_THRESHOLD"]
        
        # Adjust threshold based on conditions
        if temp > AGRO_CONSTANTS["HEAT_STRESS"]:
            base_threshold += 15  # Water earlier in heat
        elif temp > AGRO_CONSTANTS["OPTIMAL_TEMP_HIGH"]:
            base_threshold += 8
        
        if humidity < AGRO_CONSTANTS["DRY_AIR"]:
            base_threshold += 10  # High evaporation
        elif humidity > AGRO_CONSTANTS["HUMID"]:
            base_threshold -= 10  # Low evaporation
        
        if et_factor > 0.6:
            base_threshold += 5  # High ET conditions
        
        # Determine pump actions
        if rain == 1:
            # RULE 1: Never water during rain
            p1, p2, p3 = 0, 0, 0
        elif pressure < AGRO_CONSTANTS["STORM_IMMINENT"]:
            # RULE 2: Storm imminent - hold irrigation (save water)
            p1, p2, p3 = 0, 0, 0
        elif hour >= 22 or hour <= 5:
            # RULE 3: Prefer night watering (reduced evaporation)
            # Lower threshold at night for efficiency
            night_threshold = base_threshold - 5
            p1 = 1 if s1 < night_threshold else 0
            p2 = 1 if s2 < night_threshold else 0
            p3 = 1 if s3 < night_threshold else 0
        else:
            # RULE 4: Standard daytime operation
            p1 = 1 if s1 < base_threshold else 0
            p2 = 1 if s2 < base_threshold else 0
            p3 = 1 if s3 < base_threshold else 0
        
        # RULE 5: Critical override - always water if critically dry
        if s1 < AGRO_CONSTANTS["CRITICAL_DRY"] and rain == 0:
            p1 = 1
        if s2 < AGRO_CONSTANTS["CRITICAL_DRY"] and rain == 0:
            p2 = 1
        if s3 < AGRO_CONSTANTS["CRITICAL_DRY"] and rain == 0:
            p3 = 1
        
        # RULE 6: Never over-water
        if s1 > AGRO_CONSTANTS["SATURATED"]:
            p1 = 0
        if s2 > AGRO_CONSTANTS["SATURATED"]:
            p2 = 0
        if s3 > AGRO_CONSTANTS["SATURATED"]:
            p3 = 0
        
        data.append([
            s1, s2, s3, temp, humidity, rain, pressure, ldr, hour,
            round(et_factor, 3), round(stress_index, 1), weather_code,
            p1, p2, p3
        ])
    
    columns = [
        'soil1', 'soil2', 'soil3', 'temp', 'humidity', 'rain', 'pressure', 'ldr', 'hour',
        'et_factor', 'stress_index', 'weather_code',
        'p1', 'p2', 'p3'
    ]
    
    return pd.DataFrame(data, columns=columns)

# ============================================================================
# MODEL TRAINING
# ============================================================================

try:
    # Step 1: Generate Data
    print("\n" + "=" * 60)
    print("STEP 1: DATA GENERATION")
    print("=" * 60)
    
    df = generate_advanced_training_data(CONFIG["n_samples"])
    print(f"✅ Generated {len(df)} samples")
    print(f"\nData Distribution:")
    print(f"   - Rain samples: {df['rain'].sum()} ({df['rain'].mean()*100:.1f}%)")
    print(f"   - Avg Temperature: {df['temp'].mean():.1f}°C")
    print(f"   - Avg Humidity: {df['humidity'].mean():.1f}%")
    print(f"   - Pump 1 ON: {df['p1'].sum()} ({df['p1'].mean()*100:.1f}%)")
    print(f"   - Pump 2 ON: {df['p2'].sum()} ({df['p2'].mean()*100:.1f}%)")
    print(f"   - Pump 3 ON: {df['p3'].sum()} ({df['p3'].mean()*100:.1f}%)")
    
    # Step 2: Feature Engineering
    print("\n" + "=" * 60)
    print("STEP 2: FEATURE ENGINEERING")
    print("=" * 60)
    
    # Core features for the model
    feature_columns = ['soil1', 'soil2', 'soil3', 'temp', 'humidity', 'rain', 'pressure']
    target_columns = ['p1', 'p2', 'p3']
    
    X = df[feature_columns]
    y = df[target_columns]
    
    print(f"✅ Features: {feature_columns}")
    print(f"✅ Targets: {target_columns}")
    
    # Step 3: Train-Test Split
    print("\n" + "=" * 60)
    print("STEP 3: DATA SPLITTING")
    print("=" * 60)
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, 
        test_size=CONFIG["test_size"], 
        random_state=CONFIG["random_state"],
        stratify=y['p1']  # Stratify by first pump to maintain distribution
    )
    
    print(f"✅ Training samples: {len(X_train)}")
    print(f"✅ Testing samples: {len(X_test)}")
    
    # Step 4: Model Training
    print("\n" + "=" * 60)
    print("STEP 4: MODEL TRAINING")
    print("=" * 60)
    
    # Create the model
    base_classifier = RandomForestClassifier(
        n_estimators=CONFIG["n_estimators"],
        max_depth=15,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=CONFIG["random_state"],
        n_jobs=-1  # Use all CPU cores
    )
    
    model = MultiOutputClassifier(base_classifier, n_jobs=1)
    
    print(f"🔄 Training Random Forest with {CONFIG['n_estimators']} trees...")
    model.fit(X_train, y_train)
    print("✅ Model training complete!")
    
    # Step 5: Evaluation
    print("\n" + "=" * 60)
    print("STEP 5: MODEL EVALUATION")
    print("=" * 60)
    
    y_pred = model.predict(X_test)
    
    # Overall accuracy
    exact_match = accuracy_score(y_test, y_pred)
    print(f"\n📊 PERFORMANCE METRICS:")
    print(f"   Global Exact Match Accuracy: {exact_match * 100:.2f}%")
    
    # Individual pump accuracy
    pump_names = ["Zone Alpha (Div 1)", "Zone Beta (Div 2)", "Paddy Field (Div 3)"]
    for i, name in enumerate(pump_names):
        acc = accuracy_score(y_test.iloc[:, i], y_pred[:, i])
        print(f"   {name}: {acc * 100:.2f}%")
    
    # Feature Importance
    print(f"\n📊 FEATURE IMPORTANCE (Zone Alpha):")
    importances = model.estimators_[0].feature_importances_
    for feat, imp in sorted(zip(feature_columns, importances), key=lambda x: x[1], reverse=True):
        bar = "█" * int(imp * 50)
        print(f"   {feat:12} {imp:.3f} {bar}")
    
    # Cross-validation
    print(f"\n📊 CROSS-VALIDATION (5-Fold):")
    cv_model = MultiOutputClassifier(
        RandomForestClassifier(n_estimators=50, random_state=42), 
        n_jobs=1
    )
    # For multi-output, we validate on first output as proxy
    cv_scores = cross_val_score(cv_model.estimators_[0] if hasattr(cv_model, 'estimators_') else 
                                 RandomForestClassifier(n_estimators=50, random_state=42), 
                                 X, y['p1'], cv=5)
    print(f"   Mean CV Score: {cv_scores.mean() * 100:.2f}% (+/- {cv_scores.std() * 2 * 100:.2f}%)")
    
    # Step 6: Save Model
    print("\n" + "=" * 60)
    print("STEP 6: SAVING MODEL")
    print("=" * 60)
    
    with open(CONFIG["model_path"], 'wb') as f:
        pickle.dump(model, f)
    print(f"✅ Model saved to {CONFIG['model_path']}")
    
    # Save metadata
    metadata = {
        "version": "3.0",
        "created_at": datetime.now().isoformat(),
        "n_samples": CONFIG["n_samples"],
        "n_estimators": CONFIG["n_estimators"],
        "features": feature_columns,
        "targets": target_columns,
        "accuracy": {
            "exact_match": round(exact_match * 100, 2),
            "pump1": round(accuracy_score(y_test.iloc[:, 0], y_pred[:, 0]) * 100, 2),
            "pump2": round(accuracy_score(y_test.iloc[:, 1], y_pred[:, 1]) * 100, 2),
            "pump3": round(accuracy_score(y_test.iloc[:, 2], y_pred[:, 2]) * 100, 2)
        },
        "feature_importance": dict(zip(feature_columns, [round(x, 4) for x in importances])),
        "thresholds": AGRO_CONSTANTS
    }
    
    with open(CONFIG["metadata_path"], 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"✅ Metadata saved to {CONFIG['metadata_path']}")
    
    print("\n" + "=" * 60)
    print("🎉 TRAINING COMPLETE!")
    print("=" * 60)
    print(f"\nModel ready for deployment. Load with:")
    print(f"   with open('{CONFIG['model_path']}', 'rb') as f:")
    print(f"       model = pickle.load(f)")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    traceback.print_exc()
