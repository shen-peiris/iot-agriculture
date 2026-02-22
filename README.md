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

## 🔌 ESP32 Hardware & Pin Assignments

The system uses standard ESP32 DevKit wiring alongside I2C expansions.

### I2C Bus Devices (SDA = GPIO 21, SCL = GPIO 22)
* **ADS1115 (Address `0x48`)**: 16-bit ADC for high-precision analog readings.
* **MCP23017 (Address `0x20`)**: 16-channel I2C I/O Expander for managing the heavy 4-channel relay load.
* **BME280 (Address `0x76/0x77`)**: Precision environmental sensor (Temperature, Humidity, Barometric Pressure).

### Directly Connected Sensors (ESP32 GPIO)
| Component | Pin | Type | Note |
| :--- | :--- | :--- | :--- |
| **White Lamp 1** | `GPIO 12` | Digital Out | Night illumination, controlled by LDR |
| **White Lamp 2** | `GPIO 13` | Digital Out | Night illumination, controlled by LDR |
| **White Lamp 3** | `GPIO 14` | Digital Out | Night illumination, controlled by LDR |
| **White Lamp 4** | `GPIO 32` | Digital Out | Night illumination, controlled by LDR |
| **Red Alert LED** | `GPIO 26` | Digital Out | Triggers upon PIR security motion |
| **Buzzer** | `GPIO 33` | Digital Out | Lockdown / Alarm |
| **Rain Sensor** | `GPIO 27` | Digital In | Active LOW |
| **LDR (Light)** | `GPIO 34` | Analog In | Day/Night detection |
| **PIR Motion** | `GPIO 25` | Digital In | Perimeter security |
| **Ultrasonic TRIG** | `GPIO 18` | Digital Out | Tank water level |
| **Ultrasonic ECHO** | `GPIO 19` | Digital In | Tank water level |
| **DHT11 (Backup)**| `GPIO 4`  | Digital In | Backup if BME280 fails |

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

### How to Change Pin Assignments 🛠
If you are building your own iteration and need to alter pins:
1. Open `sketch_jan8a/sketch_jan8a.ino`.
2. Locate the **ESP32 DIRECT PIN DEFINITIONS** section around line 70.
3. Modify the `#define` macros (e.g., `#define PIN_LED1 12` -> `#define PIN_LED1 15`).
4. Re-compile and flash the firmware using the Arduino IDE.
*(Note: Always respect standard ESP32 strapping pins restrictions when rewiring!)*

---

## 🚀 Getting Started

### 1. Hardware Setup
* Flash `sketch_jan8a.ino` onto your ESP32.
* Ensure your WiFi credentials and the Server IP (`http://<SERVER_IP>:8080/api/update_sensors`) are updated in the sketch.

### 2. Server Setup
* Install Python 3.8+
* Install dependencies: `pip install -r requirements.txt` (requires `flask`, `pandas`, `numpy`, `scikit-learn`).
* Run the main server: `python server.py`
* The dashboard will be available locally on port `8080`. 

*(Tip: In development, there is a built-in Simulation Mode you can trigger from the Dashboard Settings to test the UI without having the physical ESP32 connected!)*
