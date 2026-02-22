
# Mock Logic from Server.py
controls = {
    "pumps": {"div1": False},
    "pump_modes": {"div1": "AUTO"}
}
state = {"soil1": 0}
SOIL_DRY = 30
SOIL_WET = 70

def get_auto_state(current_state, sensor_val, low_thresh, high_thresh):
    if sensor_val < low_thresh: return True
    if sensor_val > high_thresh: return False
    return current_state

def run_logic(s1_val, current_state):
    controls['pumps']['div1'] = current_state
    
    # New Logic Block
    if controls['pump_modes']['div1'] == 'ON': controls['pumps']['div1'] = True
    elif controls['pump_modes']['div1'] == 'OFF': controls['pumps']['div1'] = False
    else: # AUTO
         if s1_val <= 0:
             controls['pumps']['div1'] = False # Safety: Don't run on 0
         else:
             controls['pumps']['div1'] = get_auto_state(controls['pumps']['div1'], s1_val, SOIL_DRY, SOIL_WET)
    
    return controls['pumps']['div1']

# Test Cases
print(f"Test 1 (Soil=0): {run_logic(0, False)} (Expected: False)")
print(f"Test 2 (Soil=20): {run_logic(20, False)} (Expected: True)")
print(f"Test 3 (Soil=80): {run_logic(80, True)} (Expected: False)")
print(f"Test 4 (Soil=40, State=True): {run_logic(40, True)} (Expected: True)")
print(f"Test 5 (Soil=40, State=False): {run_logic(40, False)} (Expected: False)")
