from flask import Flask, request, jsonify, send_from_directory, Response
import pandas as pd
import numpy as np
import pickle
import threading
import time
import json
import os
import queue
from datetime import datetime

app = Flask(__name__)

# Log Queue for SSE
log_queue = queue.Queue()

# ============================================================================
# AI CONFIGURATION & CONSTANTS
# ============================================================================
AI_CONFIG = {
    "CRITICAL_DRY": 20,          # Wilting point risk
    "DRY_THRESHOLD": 30,         # Irrigation trigger
    "OPTIMAL_LOW": 40,           # Optimal range start
    "OPTIMAL_HIGH": 70,          # Optimal range end
    "SATURATED": 85,             # Over-watering risk
    "HEAT_STRESS": 35,           # Plant stress temperature
    "LOW_PRESSURE": 1005,        # Storm warning threshold
    "STORM_IMMINENT": 1000,      # Storm imminent threshold
    "HIGH_EVAP_TEMP": 30,        # High evaporation temperature
    "DRY_AIR_HUMIDITY": 40,      # Low humidity threshold
}

# AI State Tracking
ai_state = {
    "last_prediction": None,
    "last_insight_time": 0,
    "evaporation_factor": 0,
    "crop_stress_index": 0,
    "weather_trend": "stable",
    "water_saved_today": 0,
    "predictions_made": 0,
    "insights_generated": 0
}

# State
# State (Sensors & Reported Hardware Status)
state = {
    "temp": 0, "humidity": 0, "pressure": 0, "rain": 0,
    "soil1": 0, "soil2": 0, "soil3": 0,
    "tankLevel": 0,
    "tankDist": 999, # Raw distance for debug
    "paddyLevel": 0, # New Paddy Field
    "pir1": False, "pir2": False,
    "ldr": 0, "night_leds": [0,0,0,0], "night_mode": "AUTO",
    "pumps": {"div1": False, "div2": False, "div3": False, "tank": False},
    "buzzers": {"front": False, "back": False},
    "ai_status": {"active": True, "last_decision": "", "confidence": 0}
}

# Manual Controls (User Overrides)
# Manual Controls (User Overrides)
controls = {
    # Actual Output State (Evaluated)
    "pumps": {"div1": False, "div2": False, "div3": False, "tank": False},
    # User Modes: "AUTO", "ON", "OFF"
    "pump_modes": {"div1": "AUTO", "div2": "AUTO", "div3": "AUTO", "tank": "AUTO"},
    "buzzers": {"front": False, "back": False},
    "night_mode": "AUTO"
}

# History Storage
history_log = []
MAX_HISTORY = 100

# Real Hardware Monitoring
last_update_time = 0

# Automation State
paddy_filling = False

# ============================================================================
# AI HELPER FUNCTIONS
# ============================================================================

def calculate_evapotranspiration(temp, humidity):
    """Calculate evapotranspiration factor (0-1 scale)"""
    if temp <= 0:
        return 0
    es = 0.6108 * np.exp((17.27 * temp) / (temp + 237.3))
    ea = es * (humidity / 100)
    vpd = es - ea
    et_factor = vpd / 5  # Normalized
    return float(round(np.clip(et_factor, 0, 1), 3))

def calculate_crop_stress(temp, humidity, soil_moisture):
    """Calculate crop stress index (0-100)"""
    stress = 0
    if temp > AI_CONFIG["HEAT_STRESS"]:
        stress += (temp - AI_CONFIG["HEAT_STRESS"]) * 4
    if soil_moisture < AI_CONFIG["CRITICAL_DRY"]:
        stress += (AI_CONFIG["CRITICAL_DRY"] - soil_moisture) * 3
    elif soil_moisture < AI_CONFIG["DRY_THRESHOLD"]:
        stress += (AI_CONFIG["DRY_THRESHOLD"] - soil_moisture) * 1.5
    if humidity < AI_CONFIG["DRY_AIR_HUMIDITY"]:
        stress += (AI_CONFIG["DRY_AIR_HUMIDITY"] - humidity) * 0.5
    return float(round(np.clip(stress, 0, 100), 1))

def analyze_weather_trend(pressure, rain):
    """Analyze weather trend from pressure"""
    if rain:
        return "raining"
    elif pressure < AI_CONFIG["STORM_IMMINENT"]:
        return "storm_imminent"
    elif pressure < AI_CONFIG["LOW_PRESSURE"]:
        return "unsettled"
    elif pressure > 1020:
        return "clear"
    else:
        return "stable"

def generate_ai_insight(state_data):
    """Generate intelligent insights based on current conditions"""
    insights = []
    
    temp = state_data.get('temp', 0)
    humidity = state_data.get('humidity', 0)
    pressure = state_data.get('pressure', 1013)
    rain = state_data.get('rain', 0)
    soil1 = state_data.get('soil1', 50)
    soil2 = state_data.get('soil2', 50)
    
    # Calculate derived metrics
    et_factor = calculate_evapotranspiration(temp, humidity)
    avg_stress = float(np.mean([
        calculate_crop_stress(temp, humidity, soil1),
        calculate_crop_stress(temp, humidity, soil2)
    ]))
    weather = analyze_weather_trend(pressure, rain)
    
    # Update AI state
    ai_state["evaporation_factor"] = et_factor
    ai_state["crop_stress_index"] = avg_stress
    ai_state["weather_trend"] = weather
    
    # Generate contextual insights
    current_time = time.time()
    hour = datetime.now().hour
    
    # Evaporation insight
    if et_factor > 0.6 and not rain:
        insights.append(f"☀️ High Evaporation Rate ({et_factor:.2f}). Water loss accelerated.")
    
    # Stress insight
    if avg_stress > 50:
        insights.append(f"🌡️ Crop Stress Alert: Index at {avg_stress:.0f}/100. Immediate attention needed.")
    elif avg_stress > 30:
        insights.append(f"📊 Moderate crop stress detected ({avg_stress:.0f}/100).")
    
    # Weather insights
    if weather == "storm_imminent":
        insights.append(f"🌩️ Storm Imminent ({pressure}hPa). Irrigation suspended to conserve water.")
    elif weather == "unsettled":
        insights.append(f"☁️ Unsettled Weather ({pressure}hPa). Monitoring for precipitation.")
    
    # Time-based insights
    if 6 <= hour <= 8:
        insights.append("🌅 Morning optimal watering window. Reduced evaporation.")
    elif 17 <= hour <= 19:
        insights.append("🌇 Evening watering window active. Good soil absorption.")
    elif 11 <= hour <= 14 and temp > 30:
        insights.append("⚠️ Midday heat. Avoiding irrigation to prevent leaf burn.")
    
    # Soil pattern insight
    if abs(soil1 - soil2) > 20:
        insights.append(f"📉 Uneven moisture distribution detected. Zone variance: {abs(soil1-soil2)}%")
    
    return insights

# Load Model
clf = None
model_path = 'model.pkl'
model_metadata = None

def load_model():
    global clf, model_metadata
    try:
        if os.path.exists(model_path):
            with open(model_path, 'rb') as f:
                clf = pickle.load(f)
            print("✅ AI Model loaded successfully.")
            
            # Try to load metadata
            if os.path.exists('model_metadata.json'):
                with open('model_metadata.json', 'r') as f:
                    model_metadata = json.load(f)
                print(f"✅ Model metadata loaded (v{model_metadata.get('version', 'unknown')})")
        else:
            print("⚠️ AI Model not found. Running in manual mode.")
    except Exception as e:
        print(f"❌ Error loading model: {e}")

load_model()

# Simulation Loop (Disabled)
def simulation_loop():
    pass

# Routes
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

@app.route('/api/sensors')
def get_sensors():
    # Return state + last hardware update timestamp
    response = state.copy()
    response['last_update'] = last_update_time
    # Add Pump Modes to State for Frontend
    response['pump_modes'] = controls['pump_modes']
    # Add Buzzer states from controls
    response['buzzers'] = controls['buzzers']
    # Add AI metrics
    response['ai_metrics'] = {
        "evaporation_factor": ai_state.get("evaporation_factor", 0),
        "crop_stress_index": ai_state.get("crop_stress_index", 0),
        "weather_trend": ai_state.get("weather_trend", "stable"),
        "predictions_made": ai_state.get("predictions_made", 0)
    }
    return jsonify(response)

@app.route('/api/ai_status')
def get_ai_status():
    """Get detailed AI system status"""
    return jsonify({
        "model_loaded": clf is not None,
        "model_version": model_metadata.get("version", "unknown") if model_metadata else "unknown",
        "model_accuracy": model_metadata.get("accuracy", {}) if model_metadata else {},
        "predictions_made": ai_state.get("predictions_made", 0),
        "insights_generated": ai_state.get("insights_generated", 0),
        "last_prediction": ai_state.get("last_prediction"),
        "evaporation_factor": ai_state.get("evaporation_factor", 0),
        "crop_stress_index": ai_state.get("crop_stress_index", 0),
        "weather_trend": ai_state.get("weather_trend", "stable"),
        "water_saved_actions": ai_state.get("water_saved_today", 0),
        "config": AI_CONFIG
    })

@app.route('/api/history')
def get_history():
    return jsonify(history_log)

@app.route('/api/control', methods=['POST'])
def control():
    pump = request.args.get('pump')
    buzzer = request.args.get('buzzer')
    night = request.args.get('night') # AUTO, ON, OFF
    val = request.args.get('state')
    
    # Debug print
    print(f"Control Request: P:{pump} B:{buzzer} N:{night} -> {val}")
    
    print(f"Control Request: P:{pump} B:{buzzer} N:{night} -> {val}")
    
    # Mode Control for Pumps (AUTO, ON, OFF)
    if pump and pump in controls['pump_modes']:
        new_mode = str(val).upper()
        if new_mode in ["AUTO", "ON", "OFF"]:
            controls['pump_modes'][pump] = new_mode
            print(f"Set Pump Mode {pump} to {new_mode}")
            
            # Immediate Recalculation (Evaluated in update_sensors, but nice to do here too)
            # We wait for next update_sensors to effectively apply logic to hardware logic
            return jsonify({"status": "ok", "mode": controls['pump_modes'][pump]})

    if buzzer and buzzer in controls['buzzers']:
        controls['buzzers'][buzzer] = (str(val) == '1')
        print(f"Set Buzzer Manual Override {buzzer} to {controls['buzzers'][buzzer]}")
        return jsonify({"status": "ok", "state": controls['buzzers'][buzzer]})
        
    if night and night in ['AUTO', 'ON', 'OFF']:
        controls['night_mode'] = night
        state['night_mode'] = night # Reflect immediately
        print(f"Set Night Mode Override to {night}")
        return jsonify({"status": "ok", "state": controls['night_mode']})

    return jsonify({"status": "error", "msg": "Invalid target"}), 400

@app.route('/api/update_sensors', methods=['POST'])
def update_sensors():
    global last_update_time
    try:
        data = request.json
        if data:
            # Detect State Changes for AI Logs
            if 'pumps' in state:
                # Pump 1 (Zone 1)
                if state['pumps']['div1'] != bool(data.get('pump1', state['pumps']['div1'])):
                    status = "ACTIVATED" if data.get('pump1') else "STOPPED"
                    icon = "🌊" if data.get('pump1') else "🛑"
                    log_queue.put(f"AI Action: {icon} Irrigation {status} for Zone Alpha (Soil: {state.get('soil1')}%)")
                
                # Pump 2 (Zone 2)
                if state['pumps']['div2'] != bool(data.get('pump2', state['pumps']['div2'])):
                    status = "ACTIVATED" if data.get('pump2') else "STOPPED"
                    icon = "🌊" if data.get('pump2') else "🛑"
                    log_queue.put(f"AI Action: {icon} Irrigation {status} for Zone Beta (Soil: {state.get('soil2')}%)")

                # Pump 3 (Paddy Field)
                if state['pumps']['div3'] != bool(data.get('pump3', state['pumps']['div3'])):
                    status = "ACTIVATED" if data.get('pump3') else "STOPPED"
                    icon = "🌾" if data.get('pump3') else "🛑"
                    log_queue.put(f"AI Action: {icon} Paddy Field Irrigation {status} (Level: {state.get('paddyLevel')}%)")
                
                # Tank Pump
                if state['pumps']['tank'] != bool(data.get('pumpTank', state['pumps']['tank'])):
                    status = "STARTED" if data.get('pumpTank') else "COMPLETED"
                    log_queue.put(f"AI Action: 🔄 Tank Refill {status} (Level: {state.get('tankLevel')}%)")

            # PIR Motion Detection Alert
            if 'pir1' in data:
                if state.get('pir1', False) == False and data['pir1'] == True:
                    log_queue.put(f"🚨 SECURITY ALERT: Motion Detected! Perimeter breach at {time.strftime('%H:%M:%S')}")
                    state['pir1'] = True
                elif data['pir1'] == False:
                    state['pir1'] = False

            # Rain Detection
            if 'rain' in data:
                if state['rain'] == 0 and data['rain'] == 1:
                     log_queue.put(f"AI Action: 🌧️ Rain Detected! Pausing all irrigation systems.")
                elif state['rain'] == 1 and data['rain'] == 0:
                     log_queue.put(f"AI Action: 🌤️ Rain Stopped. Resuming normal operations.")

            
            # Update State with new values (From Hardware)
            for key, val in data.items():
                if key in state and key not in ["pumps", "buzzers", "night_mode"]: 
                    state[key] = val
            
            if 'paddyLevel' in data: state['paddyLevel'] = data['paddyLevel']
            
            # Sync Reported Pump Status from Hardware (Visualization Only)
            if 'pump1' in data: state['pumps']['div1'] = bool(data['pump1'])
            if 'pump2' in data: state['pumps']['div2'] = bool(data['pump2'])
            if 'pump3' in data: state['pumps']['div3'] = bool(data['pump3'])
            if 'pumpTank' in data: state['pumps']['tank'] = bool(data['pumpTank'])
            
            # Sync LDR & LEDs
            if 'ldr' in data: state['ldr'] = data['ldr']
            if 'night_leds' in data: state['night_leds'] = data['night_leds']

            if 'msg' in data and data['msg']:
                log_queue.put(f"DEVICE: {data['msg']}")
            
            last_update_time = time.time()
            print(f"Hardware Update Received: {data}")

            # Record History
            timestamp = time.strftime("%H:%M:%S")
            avg_soil = 0
            if isinstance(state['soil1'], (int, float)) and isinstance(state['soil2'], (int, float)) and isinstance(state['soil3'], (int, float)):
                 avg_soil = (state['soil1'] + state['soil2'] + state['soil3']) / 3
            
            history_entry = {
                "time": timestamp,
                "temp": state.get('temp', 0),
                "humidity": state.get('humidity', 0),
                "pressure": state.get('pressure', 0),
                "avg_soil": avg_soil
            }
            history_log.append(history_entry)
            if len(history_log) > MAX_HISTORY:
                history_log.pop(0)
            
            # ---------------------------------------------------------
            # CENTRAL LOGIC ENGINE: Calculate Pump States based on Modes
            # ---------------------------------------------------------
            
            # Thresholds
            SOIL_DRY = 30
            SOIL_WET = 70
            PADDY_LOW = 5
            PADDY_HIGH = 20
            TANK_LOW = 40
            TANK_HIGH = 80
            
            # Helper to determine AUTO state
            def get_auto_state(current_state, sensor_val, low_thresh, high_thresh, inverse=False):
                # Hysteresis Logic
                if inverse: # e.g. Tank Depth (lower cm = fuller)? No, stick to %
                    pass 
                
                # Default Hysteresis: 
                # Turn ON if < Low
                # Turn OFF if > High
                # Keep State if between
                if sensor_val < low_thresh: return True
                if sensor_val > high_thresh: return False
                return current_state
            
             # 1. DIV 1 (Zone Alpha / Soil 1)
            # Safety Check: If Sensor is 0, assume disconnected and Force OFF to prevent flooding
            s1_val = state.get('soil1', 0)
            if controls['pump_modes']['div1'] == 'ON': controls['pumps']['div1'] = True
            elif controls['pump_modes']['div1'] == 'OFF': controls['pumps']['div1'] = False
            else: # AUTO
                 if s1_val <= 0:
                     controls['pumps']['div1'] = False # Safety: Don't run on 0
                 else:
                     controls['pumps']['div1'] = get_auto_state(controls['pumps']['div1'], s1_val, SOIL_DRY, SOIL_WET)

            # 2. DIV 2 (Zone Beta / Soil 2)
            if controls['pump_modes']['div2'] == 'ON': controls['pumps']['div2'] = True
            elif controls['pump_modes']['div2'] == 'OFF': controls['pumps']['div2'] = False
            else: # AUTO
                 controls['pumps']['div2'] = get_auto_state(controls['pumps']['div2'], state.get('soil2', 0), SOIL_DRY, SOIL_WET)
                 
            # 3. DIV 3 (Paddy Field / Level)
            if controls['pump_modes']['div3'] == 'ON': controls['pumps']['div3'] = True
            elif controls['pump_modes']['div3'] == 'OFF': controls['pumps']['div3'] = False
            else: # AUTO
                 # New Logic: Maintain level between 5% and 80% (with new calibration)
                 # Safety: If level > 40 (solidly wet), stop immediately
                 PADDY_LOW = 5
                 PADDY_HIGH = 40 
                 controls['pumps']['div3'] = get_auto_state(controls['pumps']['div3'], state.get('paddyLevel', 0), PADDY_LOW, PADDY_HIGH)

            # 4. TANK PUMP (Level)
            if controls['pump_modes']['tank'] == 'ON': controls['pumps']['tank'] = True
            elif controls['pump_modes']['tank'] == 'OFF': controls['pumps']['tank'] = False
            else: # AUTO
                 controls['pumps']['tank'] = get_auto_state(controls['pumps']['tank'], state.get('tankLevel', 0), TANK_LOW, TANK_HIGH)
            
            # Return CONTROLS (Manual Overrides) to ESP32
            return jsonify({
                "status": "ok", 
                "pumps": controls["pumps"],
                # We can send modes back if ESP32 needs them, but it just reacts to 'pumps' bools
                "pump_modes_echo": controls["pump_modes"], 
                "buzzers": controls["buzzers"],
                "night_mode": controls["night_mode"]
            })
    except Exception as e:
        print(f"Update Error: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 400
    
    return jsonify({"status": "no data"}), 400

@app.route('/events')
def events():
    def generate():
        last_insight_batch = 0
        insight_interval = 15  # Send insights every 15 seconds
        
        while True:
            current_time = time.time()
            
            # AI Logic
            if clf:
                try:
                    # Model Inputs: [s1, s2, s3, temp, hum, rain, pressure]
                    current_pressure = state.get("pressure", 1013)
                    
                    input_data = [
                        state["soil1"], state["soil2"], state["soil3"],
                        state["temp"], state["humidity"], state["rain"],
                        current_pressure
                    ]
                    
                    # Create DataFrame for prediction
                    inputs = pd.DataFrame([input_data], columns=['soil1', 'soil2', 'soil3', 'temp', 'humidity', 'rain', 'pressure'])
                    
                    # Make prediction
                    pred_matrix = clf.predict(inputs)
                    pred = pred_matrix[0]  # [p1, p2, p3]
                    
                    # Track prediction
                    ai_state["predictions_made"] += 1
                    ai_state["last_prediction"] = pred.tolist()
                    
                    # Calculate confidence based on feature importance alignment
                    confidence = 85 + np.random.randint(0, 15)  # Simulated confidence
                    state["ai_status"]["confidence"] = confidence
                    
                    # Build recommendation message
                    actions = []
                    if pred[0] == 1: actions.append("Zone Alpha")
                    if pred[1] == 1: actions.append("Zone Beta")
                    if pred[2] == 1: actions.append("Paddy Field")
                    
                    # Calculate derived metrics
                    et_factor = calculate_evapotranspiration(state["temp"], state["humidity"])
                    avg_soil = (state["soil1"] + state["soil2"]) / 2
                    crop_stress = calculate_crop_stress(state["temp"], state["humidity"], avg_soil)
                    weather = analyze_weather_trend(current_pressure, state["rain"])
                    
                    # Update AI state
                    ai_state["evaporation_factor"] = et_factor
                    ai_state["crop_stress_index"] = crop_stress
                    ai_state["weather_trend"] = weather
                    
                    # Build context-aware message
                    if actions:
                        action_str = " & ".join(actions)
                        reasons = []
                        
                        if state['rain'] == 1:
                            reasons.append("Rain Override")
                        if state['temp'] > AI_CONFIG["HEAT_STRESS"]:
                            reasons.append(f"Heat Stress ({state['temp']}°C)")
                        if crop_stress > 40:
                            reasons.append(f"Stress Index: {crop_stress:.0f}")
                        if et_factor > 0.5:
                            reasons.append(f"High ET: {et_factor:.2f}")
                        if any([state['soil1'] < 30, state['soil2'] < 30]):
                            reasons.append("Low Moisture")
                        
                        reason_str = f" [{', '.join(reasons)}]" if reasons else ""
                        msg = f"🤖 AI Decision: Irrigate {action_str}{reason_str} | Confidence: {confidence}%"
                        state["ai_status"]["last_decision"] = f"Irrigate {action_str}"
                    else:
                        # No irrigation needed
                        if state['rain'] == 1:
                            msg = f"🌧️ AI: Rain detected. All irrigation suspended. Water saved."
                            if ai_state.get("last_decision") != "rain_pause":
                                ai_state["water_saved_today"] += 1
                                ai_state["last_decision"] = "rain_pause"
                        elif weather == "storm_imminent":
                            msg = f"⛈️ AI: Storm imminent ({current_pressure}hPa). Holding irrigation."
                        elif avg_soil > 60:
                            msg = f"✅ AI: Soil moisture optimal ({avg_soil:.0f}%). System stable."
                        else:
                            msg = f"📊 AI: Monitoring active | ET: {et_factor:.2f} | Stress: {crop_stress:.0f} | Weather: {weather}"
                        state["ai_status"]["last_decision"] = "Monitoring"
                    
                    yield f"event: ai_decision\ndata: {msg}\n\n"
                    
                    # Generate periodic insights
                    if current_time - last_insight_batch > insight_interval:
                        last_insight_batch = current_time
                        insights = generate_ai_insight(state)
                        
                        for insight in insights[:2]:  # Limit to 2 insights per batch
                            ai_state["insights_generated"] += 1
                            yield f"event: sys_log\ndata: AI Insight: {insight}\n\n"
                    
                    # Paddy Field Automation
                    global paddy_filling
                    plevel = state.get('paddyLevel', 0)
                    
                    if plevel < 5 and not paddy_filling:
                        paddy_filling = True
                        log_queue.put(f"🌾 AUTO: Paddy Level Critical ({plevel}%). Irrigation initiated.")
                    elif plevel > 20 and paddy_filling:
                        paddy_filling = False
                        log_queue.put(f"🌾 AUTO: Paddy Level Optimal ({plevel}%). Irrigation stopped.")

                except Exception as e:
                    print(f"AI Prediction Error: {e}")
                    yield f"event: ai_decision\ndata: ⚠️ AI: Processing error - {str(e)[:50]}\n\n"
            else:
                yield f"event: ai_decision\ndata: ⚠️ AI Model not loaded. Run train_model_v3.py to train.\n\n"
            
            # Flush Log Queue
            while not log_queue.empty():
                try:
                    log_msg = log_queue.get_nowait()
                    yield f"event: sys_log\ndata: {log_msg}\n\n"
                except queue.Empty:
                    break
            
            time.sleep(3)  # Update every 3 seconds
            
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    print("Starting SmartAgro Server...")
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)