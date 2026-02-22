# Agro AI - Smart Agricultural IoT System 🌱

A comprehensive, AI-powered smart agriculture and irrigation system built with an ESP32 microcontroller, a Python Flask local server, a Machine Learning decision engine, and a premium web dashboard.

---

## 🏗 System Architecture

The project consists of three main components working in tandem:

1. **Hardware (ESP32 Controller)**
   Collects data from a vast array of analog and digital sensors. To handle the high number of inputs and outputs, it utilizes an **ADS1115** (16-bit ADC) and an **MCP23017** (I2C GPIO Expander).
2. **Server (Python Flask)**
   Acts as the central brain. It receives telemetry from the ESP32 via HTTP POST requests, archives historical data, and serves the web interface.
3. **AI Engine (Scikit-Learn)**
   A pre-trained Multi-Output Random Forest Classifier that analyzes environmental factors (temperature, humidity, pressure, soil moisture, and rain) to make intelligent decisions regarding automated irrigation.
4. **Web Dashboard (HTML/JS/CSS)**
   A sleek, modern, glassmorphism-styled dashboard that provides real-time monitoring of all sensors, interactive charts, and manual overrides for the system.

---

## 🧠 AI Model Engine

The Smart Irrigation System is powered by a **Multi-Output Random Forest Classifier** (`model.pkl`).

### Features & Inputs
The model evaluates the following 6 inputs every few seconds:
* `soil1`, `soil2`, `soil3` (0-100%): Moisture levels across different agricultural zones.
* `temp` (°C): Ambient temperature.
* `humidity` (%): Ambient relative humidity.
* `rain` (Binary): 1 if raining, 0 if not.
* `pressure` (hPa): Atmospheric pressure to determine weather trends.

### Decision Logic
Based on agronomic rules mimicking real-world constraints:
* **Rain Override**: All pumps shut off automatically if rain is detected.
* **Dynamic Thresholds**: Calculates evapotranspiration and crop stress indexes. Base moisture thresholds adjust dynamically (e.g., higher heat = plants need water sooner, high humidity = threshold decreases). 
* **Outputs**: Predicts independent required states for Pump 1 (Zone Alpha), Pump 2 (Zone Beta), and Pump 3 (Paddy Field).

---

## 🌡️ Sensors & Hardware Used
This project uses a multitude of sensors to capture complete environmental states.

| Sensor Name | Purpose | Interface / Pin |
| :--- | :--- | :--- |
| **BME280** | High-precision ambient Temperature, Humidity, and Pressure | I2C (0x76/0x77) |
| **DHT11** | Backup Temperature & Humidity sensor if BME280 fails | Digital `GPIO 4` |
| **PIR Sensor** | Perimeter security & motion detection | Digital `GPIO 25` |
| **Rain Sensor Module** | Immediate precipitation detection to halt irrigation | Digital `GPIO 27` |
| **HC-SR04** (Ultrasonic) | Measure water level distance in the main tank | `TRIG: 18`, `ECHO: 19` |
| **LDR (Photoresistor)** | Ambient light detection to trigger night illumination | Analog `GPIO 34` |
| **3x Analog Soil Moisture**| Measure moisture levels independently across 3 zones | via **ADS1115** |
| **1x Analog Water Level** | Detect exact submersion levels for the Paddy Field | via **ADS1115** |
| **ADS1115** | 16-bit ADC expansion for analog sensors | I2C (0x48) |
| **MCP23017** | 16-channel I/O expansion for Relay switching | I2C (0x20) |

---

## 🔌 ESP32 Pin Assignments

The system uses standard ESP32 DevKit wiring alongside I2C expansions.

### I2C Bus Devices (SDA = GPIO 21, SCL = GPIO 22)

### ADS1115 Analog Multiplexer Channels
Because the ESP32 has limited ADC pins, critical analog sensors are routed through the ADS1115:
* `A0`: Water Level Sensor (Paddy Field)
* `A1`: Soil Sensor 2 (Zone Beta)
* `A2`: Soil Sensor 3 (Average Monitoring)
* `A3`: Soil Sensor 1 (Zone Alpha)

### MCP23017 Relay Expander Channels
Used to safely isolate and trigger high-power 5V/12V pumps:
* `GPA0`: Relay 1 -> Pump 1 (Zone Alpha)
* `GPA1`: Relay 2 -> Pump 2 (Zone Beta)
* `GPA2`: Relay 3 -> Pump 3 (Paddy Field)
* `GPA3`: Relay 4 -> Tank Refill Pump

### Outputs (ESP32 Direct)
* **White Lamps 1-3:** `GPIO 12`, `GPIO 13`, `GPIO 14` (LDR Controlled)
* **White Lamp 4:** `GPIO 32` (LDR Controlled)
* **Red Alert LED:** `GPIO 26` (PIR Controlled)
* **Buzzer/Alarm:** `GPIO 33`

---

## 🚀 Getting Started & Configuration

### 1. Hardware Configuration (ESP32)
Before flashing the code to your ESP32, you must modify the WiFi and Server details to match your network.
Open `sketch_jan8a/sketch_jan8a.ino` and locate lines 61-68:
```cpp
// WiFi Credentials (UPDATE THESE)
const char* ssid = "YOUR_WIFI_SSID_HERE";
const char* password = "YOUR_WIFI_PASSWORD_HERE";

// Server Configuration
// Change this to the local IPv4 address of the computer running server.py
const char* serverUrl = "http://YOUR_SERVER_IP:8080/api/update_sensors";
```
Compile and flash the firmware to your ESP32.

### 2. Server Setup & Dependencies
* Install Python 3.8+
* Install required dependencies by running:
  ```bash
  pip install -r requirements.txt
  ```
  *(Dependencies: `flask`, `pandas`, `numpy`, `scikit-learn`)*
* Start the backend server:
  ```bash
  python server.py
  ```

### 3. Web Dashboard Login & Usage
Once the server is running, navigate to `http://localhost:8080` (or your chosen IP) in your browser.

**Default Administrator Credentials**:
* **Operator ID**: `admin`
* **Security Key**: `admin123`

#### Changing Default Credentials:
For security in production deployments, update these default credentials:
1. Open `script.js` in a code editor.
2. Locate the `AUTH` constant around line 283:
```javascript
const AUTH = {
    user: 'admin', // DEFAULT - CHANGE BEFORE PRODUCTION
    pass: 'admin123' // DEFAULT - CHANGE BEFORE PRODUCTION
};
```
3. Change these to your highly secure login details.

*(Tip: In development, there is a built-in Simulation Mode you can trigger from the Dashboard Settings to test the UI without having the physical ESP32 connected!)*
