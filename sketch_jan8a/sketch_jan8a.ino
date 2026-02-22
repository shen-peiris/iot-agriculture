/*
 * ============================================================
 * AGRO AI - Smart Agricultural IoT System
 * ESP32 Firmware with ADS1115, MCP23017, BME280
 * ============================================================
 * 
 * Hardware Configuration:
 * - ESP32 DevKit
 * - ADS1115 (I2C 16-bit ADC for analog sensors)
 * - MCP23017 (I2C GPIO expander for 4-relay module)
 * - BME280 (I2C sensor for temp, humidity, pressure)
 * - HC-SR04 Ultrasonic (Tank level detection)
 * - PIR Sensor (Motion detection)
 * - Rain Sensor Module (D27)
 * - 4x LEDs (Night lights controlled by LDR)
 * - Buzzer (Alarm)
 * 
 * ADS1115 Channels (4 Analog Inputs):
 * A0 - Soil Sensor 1 (Zone Alpha) -> Pump 1
 * A1 - Soil Sensor 2 (Zone Beta) -> Pump 2
 * A2 - Water Level Sensor (Paddy Field) -> Pump 3
 * A3 - Soil Sensor 3 (Average monitoring, no pump)
 * 
 * 4-Channel Relay Module (via MCP23017):
 * Relay 1 - Pump/Motor 1 (Zone Alpha irrigation)
 * Relay 2 - Pump/Motor 2 (Zone Beta irrigation)
 * Relay 3 - Pump/Motor 3 (Paddy Field irrigation)
 * Relay 4 - Pump/Motor 4 (Tank Refill - ultrasonic based)
 * 
 * ESP32 Direct Pin Connections:
 * D12 - LED 1 (Night Light)
 * D13 - LED 2 (Night Light)
 * D14 - LED 3 (Night Light)
 * D26 - LED 4 (Night Light)
 * D27 - Rain Sensor (Digital)
 * D34 - LDR (Analog)
 * D33 - PIR Motion Sensor
 * D25 - Buzzer
 * D18 - Ultrasonic TRIG
 * D19 - Ultrasonic ECHO
 * D21 - I2C SDA
 * D23 - I2C SCL
 * 
 * I2C Addresses:
 * - ADS1115: 0x48
 * - MCP23017: 0x20
 * - BME280: 0x76
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <Adafruit_MCP23X17.h>
#include <Adafruit_BME280.h>
#include <DHT.h>

// ============================================================
// CONFIGURATION
// ============================================================

// WiFi Credentials (UPDATE THESE)
const char* ssid = "Galaxy A21sB582";
const char* password = "12345678";

// Server Configuration
const char* serverUrl = "http://10.138.147.92:8080/api/update_sensors";

// ============================================================
// ESP32 DIRECT PIN DEFINITIONS
// ============================================================

// I2C Pins (Standard ESP32: SDA=21, SCL=22)
// If your wiring uses different pins, change these
#define I2C_SDA 21
#define I2C_SCL 22  // Standard is GPIO 22, not 23

// 4 White Lamp LEDs (Turn ON when LDR detects darkness - night lights)
#define PIN_LED1 12   // White Lamp 1
#define PIN_LED2 13   // White Lamp 2  
#define PIN_LED3 14   // White Lamp 3
#define PIN_LED4 32   // White Lamp 4 (was 26, swapped with red)

// Red LED (Turn ON when PIR detects motion - security alert)
#define PIN_RED_LED 26  // Red LED for PIR motion (was 32, swapped with white)

// LED Logic: Set to true if LEDs turn ON with LOW signal (relay modules)
//            Set to false if LEDs turn ON with HIGH signal (direct connection)
#define LED_INVERTED false  // Try changing to true if LEDs don't work

// Sensor Pins
#define PIN_RAIN    27  // Rain Sensor (Digital Input)
#define PIN_LDR     34  // LDR (Analog Input - ADC1)
#define PIN_PIR     25  // PIR Motion Sensor (Digital Input) - CONFIRMED GPIO 25

// Ultrasonic Sensor Pins (Tank Level)
#define PIN_TRIG    18
#define PIN_ECHO    19

// Buzzer Pin - TODO: Which GPIO is buzzer on? Currently disabled
#define PIN_BUZZER  33  // Changed from 25 (PIR is on 25) - UPDATE THIS!

// DHT11 Backup Sensor Pin (for when BME280 fails)
#define PIN_DHT11   4   // GPIO 4 for DHT11 data pin - UPDATE if using different pin
#define DHTTYPE     DHT11

// Relay Module Logic: Most relay modules are ACTIVE-LOW (LOW = relay ON)
// Set to true for active-LOW relay modules (common)
// Set to false for active-HIGH relay modules (rare)
#define RELAY_INVERTED true  // LOW = pump ON, HIGH = pump OFF

// ============================================================
// ADS1115 CHANNEL MAPPING (16-bit ADC)
// ============================================================
// UPDATED MAPPING: Swapped A0 and A2 based on user wiring
#define ADS_CHANNEL_PADDY_LEVEL 0   // A0: Water Level Sensor (Paddy Field) -> Pump 3
#define ADS_CHANNEL_SOIL2       1   // A1: Soil Sensor 2 (Zone Beta) -> Pump 2
#define ADS_CHANNEL_SOIL3       2   // A2: Soil Sensor 3 (Average monitoring, no pump) - SWAPPED with Alpha
#define ADS_CHANNEL_SOIL1       3   // A3: Soil Sensor 1 (Zone Alpha) -> Pump 1 - SWAPPED with Avg

// ============================================================
// MCP23017 PIN MAPPING (4-Channel Relay Module)
// ============================================================
// Port A (GPA0-GPA3) - 4 Relay Outputs
#define MCP_PUMP1    0   // GPA0 - Relay 1: Zone Alpha Motor (Soil1 based)
#define MCP_PUMP2    1   // GPA1 - Relay 2: Zone Beta Motor (Soil2 based)
#define MCP_PUMP3    2   // GPA2 - Relay 3: Paddy Field Motor (Water level based)
#define MCP_PUMP4    3   // GPA3 - Relay 4: Tank Refill Pump (Ultrasonic based)
// GPA4-GPA7: Available for expansion

// ============================================================
// SENSOR CALIBRATION VALUES
// ============================================================
// ADS1115 returns 16-bit values (0-32767 for single-ended)
// Soil sensors: High value = Dry, Low value = Wet
#define SOIL_DRY_VALUE  26000   // Calibrate based on your sensor
#define SOIL_WET_VALUE  10000   // Calibrate based on your sensor

// PADDY FIELD SENSOR CALIBRATION (More sensitive range)
// Observation: Wet reading was ~24880 (which is ~7% on old scale)
//We want 24880 to be "High Water" (e.g. >50%)
#define PADDY_DRY_VALUE 26000   // Same dry baseline
#define PADDY_WET_VALUE 22000   // Relaxed slightly to 22000 to ensure 24880 registers well (~35-40%)
// If sensor acts like Soil Sensor (10000 wet), this will just peg at 100%, which is fine.

// ESP32 ADC (12-bit: 0-4095)
// LDR Logic: Set based on your sensor type
// Some LDRs: Higher value = Darker (resistance increases in dark)
// Some LDRs: Lower value = Darker (voltage divider setup)
#define LDR_DARK_THRESHOLD 1000   // Lowered for testing - adjust based on your readings
#define LDR_INVERTED false        // Set to true if your LDR gives LOW when dark

// Ultrasonic Tank dimensions (in cm)
#define TANK_EMPTY_DISTANCE 12  // Distance when tank is empty
#define TANK_FULL_DISTANCE  1   // Distance when tank is full

// ============================================================
// OBJECTS
// ============================================================
Adafruit_ADS1115 ads;
Adafruit_MCP23X17 mcp;
Adafruit_BME280 bme;
DHT dht(PIN_DHT11, DHTTYPE);

// ============================================================
// STATE VARIABLES
// ============================================================
unsigned long lastUpdate = 0;
const long updateInterval = 2000;  // Send data every 2 seconds

// Current states
bool pump1State = false;
bool pump2State = false;
bool pump3State = false;
bool pump4State = false;
bool buzzerState = false;
bool ledStates[4] = {false, false, false, false};
String nightMode = "AUTO";

// Hardware initialization flags
bool adsInitialized = false;
bool mcpInitialized = false;
bool bmeInitialized = false;
bool dhtInitialized = false;
bool usingDHTBackup = false;  // Track if we're using DHT11 as backup

// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(1000);  // Wait for serial monitor
  
  Serial.println("\n============================================================");
  Serial.println("AGRO AI - Smart Agricultural IoT System");
  Serial.println("Initializing Hardware...");
  Serial.println("============================================================\n");

  // Initialize I2C with explicit pins
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(100000);  // 100kHz I2C clock
  delay(100);
  
  // Scan I2C bus to find connected devices
  scanI2CDevices();
  
  // Initialize ESP32 direct GPIO pins
  // Security Lamp LEDs as outputs (GPIO 12, 13, 14, 26)
  // Note: GPIO 12 is a strapping pin - if LED doesn't work, try different pin
  pinMode(PIN_LED1, OUTPUT);
  pinMode(PIN_LED2, OUTPUT);
  pinMode(PIN_LED3, OUTPUT);
  pinMode(PIN_LED4, OUTPUT);
  
  // Red indicator LED
  pinMode(PIN_RED_LED, OUTPUT);
  
  // Buzzer as output
  pinMode(PIN_BUZZER, OUTPUT);
  
  // Ultrasonic pins
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  
  // Sensor inputs
  pinMode(PIN_RAIN, INPUT_PULLUP);  // Use pullup for rain sensor (active LOW)
  pinMode(PIN_PIR, INPUT);           // PIR sensors usually have internal pullup
  // PIN_LDR is analog - no pinMode needed
  
  Serial.println("\nGPIO Pin Configuration:");
  Serial.println("  Lamps: GPIO12, GPIO13, GPIO14, GPIO26 (PIR controlled)");
  Serial.print("  Red LED: GPIO");
  Serial.println(PIN_RED_LED);
  Serial.println("  Buzzer=GPIO25, PIR=GPIO33, Rain=GPIO27, LDR=GPIO34");
  Serial.print("  DHT11 Backup: GPIO");
  Serial.println(PIN_DHT11);
  
  // Initialize I2C devices
  initADS1115();
  initMCP23017();
  initBME280();
  initDHT11();  // Initialize DHT11 backup sensor
  
  // Set all outputs to safe state (OFF)
  setSafeState();
  
  // Connect to WiFi
  connectWiFi();
  
  // Hardware self-test
  hardwareTest();
  
  Serial.println("\n============================================================");
  Serial.println("System Ready!");
  Serial.println("PIN SUMMARY:");
  Serial.println("  White LED 1 = GPIO 12 (LDR controlled)");
  Serial.println("  White LED 2 = GPIO 13 (LDR controlled)");
  Serial.println("  White LED 3 = GPIO 14 (LDR controlled)");
  Serial.println("  White LED 4 = GPIO 26 (LDR controlled)");
  Serial.println("  Red LED     = GPIO 32 (PIR controlled)");
  Serial.println("  Buzzer      = GPIO 33 (PIR controlled)");
  Serial.println("  PIR Sensor  = GPIO 25");
  Serial.println("  LDR Sensor  = GPIO 34");
  Serial.println("============================================================\n");
}

// Hardware self-test function
void hardwareTest() {
  Serial.println("\n============================================================");
  Serial.println("HARDWARE SELF-TEST - Watch each LED carefully!");
  Serial.println("============================================================");
  
  // Test each White LED individually
  Serial.println("\n>>> Testing 4 WHITE LEDs (should be controlled by LDR) <<<");
  
  Serial.println("\n  [1] GPIO 12 - White LED 1...");
  digitalWrite(12, HIGH);
  delay(1000);
  digitalWrite(12, LOW);
  
  Serial.println("  [2] GPIO 13 - White LED 2...");
  digitalWrite(13, HIGH);
  delay(1000);
  digitalWrite(13, LOW);
  
  Serial.println("  [3] GPIO 14 - White LED 3...");
  digitalWrite(14, HIGH);
  delay(1000);
  digitalWrite(14, LOW);
  
  Serial.println("  [4] GPIO 26 - White LED 4...");
  digitalWrite(26, HIGH);
  delay(1000);
  digitalWrite(26, LOW);
  
  // Test Red LED
  Serial.println("\n>>> Testing RED LED (should be controlled by PIR) <<<");
  Serial.println("  [5] GPIO 32 - Red LED...");
  digitalWrite(32, HIGH);
  delay(1000);
  digitalWrite(32, LOW);
  
  // Test Buzzer
  Serial.println("\n>>> Testing BUZZER <<<");
  Serial.println("  [6] GPIO 33 - Buzzer...");
  digitalWrite(33, HIGH);
  delay(500);
  digitalWrite(33, LOW);
  
  Serial.println("\n============================================================");
  Serial.println("TEST COMPLETE! Tell me which numbers lit up which color LED:");
  Serial.println("  [1] GPIO 12 = ?");
  Serial.println("  [2] GPIO 13 = ?");
  Serial.println("  [3] GPIO 14 = ?");
  Serial.println("  [4] GPIO 26 = ?");
  Serial.println("  [5] GPIO 32 = ?");
  Serial.println("============================================================");
  
  // Test LDR reading
  Serial.println("\n[Testing LDR Sensor]");
  int ldr = readLDR();
  Serial.print("  LDR value NOW: ");
  Serial.print(ldr);
  Serial.print(" (threshold: ");
  Serial.print(LDR_DARK_THRESHOLD);
  Serial.println(")");
  Serial.println("  Cover the LDR sensor and tell me what value you see!");
  
  // Test PIR reading
  Serial.println("\n[Testing PIR Sensor]");
  Serial.print("  PIR state NOW: ");
  Serial.println(readPIR() ? "MOTION DETECTED" : "No motion");
}

// ============================================================
// HARDWARE INITIALIZATION FUNCTIONS
// ============================================================

// Scan I2C bus for connected devices
void scanI2CDevices() {
  Serial.println("Scanning I2C bus...");
  Serial.print("  Using SDA=GPIO");
  Serial.print(I2C_SDA);
  Serial.print(", SCL=GPIO");
  Serial.println(I2C_SCL);
  
  byte count = 0;
  
  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    byte error = Wire.endTransmission();
    
    if (error == 0) {
      Serial.print("  Found device at 0x");
      if (addr < 16) Serial.print("0");
      Serial.print(addr, HEX);
      
      // Identify known devices
      if (addr == 0x48) Serial.print(" (ADS1115)");
      else if (addr == 0x49) Serial.print(" (ADS1115 ADDR=VDD)");
      else if (addr == 0x4A) Serial.print(" (ADS1115 ADDR=SDA)");
      else if (addr == 0x4B) Serial.print(" (ADS1115 ADDR=SCL)");
      else if (addr == 0x20) Serial.print(" (MCP23017)");
      else if (addr == 0x76) Serial.print(" (BME280/BMP280)");
      else if (addr == 0x77) Serial.print(" (BME280/BMP280 alt)");
      
      Serial.println();
      count++;
    }
  }
  
  if (count == 0) {
    Serial.println("  *** NO I2C DEVICES FOUND! ***");
    Serial.println("  Check wiring:");
    Serial.println("  - SDA should be on GPIO 21");
    Serial.println("  - SCL should be on GPIO 22 (standard)");
    Serial.println("  - All I2C devices need VCC and GND");
    Serial.println("  - ADS1115 ADDR pin must be connected to GND");
  } else {
    Serial.print("  Found ");
    Serial.print(count);
    Serial.println(" device(s)");
  }
  Serial.println();
}

void initADS1115() {
  Serial.print("Initializing ADS1115... ");
  
  // Try default address 0x48 with explicit Wire object
  if (ads.begin(0x48, &Wire)) {
    ads.setGain(GAIN_ONE);  // +/- 4.096V range
    adsInitialized = true;
    Serial.println("OK at 0x48");
    
    // Test read to verify it's working
    int16_t testRead = ads.readADC_SingleEnded(0);
    Serial.print("  Test read A0: ");
    Serial.println(testRead);
  } else {
    // Try alternate addresses (ADDR pin connected to different pins)
    // 0x48 = ADDR to GND
    // 0x49 = ADDR to VDD
    // 0x4A = ADDR to SDA
    // 0x4B = ADDR to SCL
    byte altAddresses[] = {0x49, 0x4A, 0x4B};
    for (int i = 0; i < 3; i++) {
      if (ads.begin(altAddresses[i], &Wire)) {
        ads.setGain(GAIN_ONE);
        adsInitialized = true;
        Serial.print("OK at 0x");
        Serial.println(altAddresses[i], HEX);
        
        int16_t testRead = ads.readADC_SingleEnded(0);
        Serial.print("  Test read A0: ");
        Serial.println(testRead);
        return;
      }
    }
    Serial.println("FAILED!");
    Serial.println("  Check ADS1115 wiring:");
    Serial.println("  - VDD to 3.3V or 5V");
    Serial.println("  - GND to GND");
    Serial.println("  - SDA to GPIO 21");
    Serial.println("  - SCL to GPIO 23");
    Serial.println("  - ADDR to GND (for 0x48)");
  }
}

void initMCP23017() {
  Serial.print("Initializing MCP23017... ");
  if (mcp.begin_I2C(0x20)) {
    // Configure motor/pump pins as outputs (GPA0-GPA3)
    for (int i = 0; i <= 3; i++) {
      mcp.pinMode(i, OUTPUT);
      mcp.digitalWrite(i, LOW);
    }
    
    mcpInitialized = true;
    Serial.println("OK");
  } else {
    Serial.println("FAILED! Check wiring.");
  }
}

void initBME280() {
  Serial.print("Initializing BME280/BMP280... ");
  
  // Set I2C for BME280
  unsigned status = bme.begin(0x76, &Wire);
  
  if (!status) {
    // Try alternate address 0x77
    status = bme.begin(0x77, &Wire);
  }
  
  if (status) {
    // Check sensor ID to determine if it's BME280 or BMP280
    uint32_t sensorId = bme.sensorID();
    Serial.print("Sensor ID: 0x");
    Serial.println(sensorId, HEX);
    
    if (sensorId == 0x60) {
      Serial.println("  Detected: BME280 (temp + humidity + pressure)");
    } else if (sensorId == 0x56 || sensorId == 0x57 || sensorId == 0x58) {
      Serial.println("  Detected: BMP280 (temp + pressure only, NO humidity)");
    } else {
      Serial.println("  Unknown sensor type");
    }
    
    // Configure for weather monitoring
    bme.setSampling(Adafruit_BME280::MODE_NORMAL,
                    Adafruit_BME280::SAMPLING_X2,   // Temperature
                    Adafruit_BME280::SAMPLING_X16,  // Pressure
                    Adafruit_BME280::SAMPLING_X1,   // Humidity
                    Adafruit_BME280::FILTER_X16,
                    Adafruit_BME280::STANDBY_MS_500);
    bmeInitialized = true;
    
    // Wait for first reading
    delay(100);
    
    // Test read
    float testTemp = bme.readTemperature();
    float testHum = bme.readHumidity();
    float testPres = bme.readPressure() / 100.0F;
    
    Serial.print("  Test read - Temp: ");
    Serial.print(testTemp);
    Serial.print("C, Humidity: ");
    Serial.print(testHum);
    Serial.print("%, Pressure: ");
    Serial.print(testPres);
    Serial.println("hPa");
    
    if (testTemp == 0.0 && testHum == 0.0) {
      Serial.println("  WARNING: Temp/Humidity reading 0 - sensor may need recalibration");
    }
  } else {
    Serial.println("FAILED! Check wiring.");
    Serial.print("  SensorID was: 0x");
    Serial.println(bme.sensorID(), HEX);
    Serial.println("  Expected 0x60 for BME280, 0x56-0x58 for BMP280");
  }
}

void initDHT11() {
  Serial.print("Initializing DHT11 Backup Sensor on GPIO ");
  Serial.print(PIN_DHT11);
  Serial.print("... ");
  
  dht.begin();
  delay(2000);  // DHT11 needs 2 seconds to stabilize
  
  // Test read
  float testTemp = dht.readTemperature();
  float testHum = dht.readHumidity();
  
  if (!isnan(testTemp) && !isnan(testHum)) {
    dhtInitialized = true;
    Serial.println("OK");
    Serial.print("  Test read - Temp: ");
    Serial.print(testTemp);
    Serial.print("C, Humidity: ");
    Serial.print(testHum);
    Serial.println("%");
  } else {
    Serial.println("FAILED or not connected!");
    Serial.println("  DHT11 will not be available as backup.");
  }
}

void setSafeState() {
  Serial.println("Setting all outputs to SAFE state (OFF)...");
  
  // Turn off all pumps (via MCP23017)
  // For inverted relay: HIGH = OFF, LOW = ON
  if (mcpInitialized) {
    int safeState = RELAY_INVERTED ? HIGH : LOW;  // OFF state for relays
    mcp.digitalWrite(MCP_PUMP1, safeState);
    mcp.digitalWrite(MCP_PUMP2, safeState);
    mcp.digitalWrite(MCP_PUMP3, safeState);
    mcp.digitalWrite(MCP_PUMP4, safeState);
    Serial.print("  Pumps: All OFF (MCP pins = ");
    Serial.print(safeState ? "HIGH" : "LOW");
    Serial.println(")");
  }
  
  // Turn off all LEDs (direct ESP32 GPIO)
  int ledOffState = LED_INVERTED ? HIGH : LOW;
  digitalWrite(PIN_LED1, ledOffState);
  digitalWrite(PIN_LED2, ledOffState);
  digitalWrite(PIN_LED3, ledOffState);
  digitalWrite(PIN_LED4, ledOffState);
  
  // Turn off buzzer (direct ESP32 GPIO)
  digitalWrite(PIN_BUZZER, LOW);
  
  pump1State = pump2State = pump3State = pump4State = false;
  buzzerState = false;
  for (int i = 0; i < 4; i++) ledStates[i] = false;
  
  Serial.println("  Safe state complete.");
}

// ============================================================
// WIFI FUNCTIONS
// ============================================================

void connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi Connection Failed! Will retry...");
  }
}

// ============================================================
// SENSOR READING FUNCTIONS
// ============================================================

// Read soil moisture from ADS1115 and convert to percentage
int readSoilMoisture(int channel) {
  if (!adsInitialized) {
    Serial.println("ADS1115 not initialized!");
    return 0;
  }
  
  int16_t rawValue = ads.readADC_SingleEnded(channel);
  
  // Debug output
  Serial.print("  ADS Ch");
  Serial.print(channel);
  Serial.print(" raw: ");
  Serial.print(rawValue);
  
  // Map raw value to percentage (inverse: high raw = dry = low %)
  int moisture = map(rawValue, SOIL_DRY_VALUE, SOIL_WET_VALUE, 0, 100);
  moisture = constrain(moisture, 0, 100);
  
  Serial.print(" -> ");
  Serial.print(moisture);
  Serial.println("%");
  
  return moisture;
}

// DEBUG HELP: Print all raw sensor values to help user identify wiring
void printDebugSensors() {
  if (adsInitialized) {
    int16_t a0 = ads.readADC_SingleEnded(0);
    int16_t a1 = ads.readADC_SingleEnded(1);
    int16_t a2 = ads.readADC_SingleEnded(2);
    int16_t a3 = ads.readADC_SingleEnded(3);
    
    Serial.print("  [DEBUG RAW] A0(Paddy): "); Serial.print(a0);
    Serial.print(" | A1(Soil2): "); Serial.print(a1);
    Serial.print(" | A2(Soil1): "); Serial.print(a2);
    Serial.print(" | A3(Soil3): "); Serial.println(a3);
  }
}

// Read LDR value from ESP32 ADC (D34)
int readLDR() {
  return analogRead(PIN_LDR);  // ESP32 12-bit ADC: 0-4095
}

// Read DHT11 sensor data (backup sensor)
void readDHT11(float &temp, float &humidity) {
  if (dhtInitialized) {
    temp = dht.readTemperature();
    humidity = dht.readHumidity();
    
    if (!isnan(temp) && !isnan(humidity)) {
      Serial.print("  DHT11 Backup: T=");
      Serial.print(temp);
      Serial.print("C, H=");
      Serial.print(humidity);
      Serial.println("%");
    } else {
      Serial.println("  DHT11: Read failed!");
      temp = 0;
      humidity = 0;
    }
  } else {
    temp = 0;
    humidity = 0;
  }
}

// Read BME280 sensor data with DHT11 fallback
void readBME280(float &temp, float &humidity, float &pressure) {
  bool needDHTBackup = false;
  
  if (bmeInitialized) {
    temp = bme.readTemperature();
    humidity = bme.readHumidity();
    pressure = bme.readPressure() / 100.0F;  // Convert to hPa
    
    // Debug output
    Serial.print("  BME280: T=");
    Serial.print(temp);
    Serial.print("C, H=");
    Serial.print(humidity);
    Serial.print("%, P=");
    Serial.print(pressure);
    Serial.println("hPa");
    
    // Check if BME readings are invalid (NaN, 0, or Out of Range)
    // Valid Range: Temp -40 to 85 (Sensor Limit), Humidity 0 to 100
    // User reported 180+ spikes, which this will catch.
    if (isnan(temp) || temp == 0 || temp < -40 || temp > 85 || 
        isnan(humidity) || humidity == 0 || humidity < 0 || humidity > 100) {
      Serial.print("  WARNING: BME280 abnormal reading! T=");
      Serial.print(temp);
      Serial.print(" H=");
      Serial.println(humidity);
      needDHTBackup = true;
    }
    
    // Validate pressure
    if (isnan(pressure) || pressure < 300 || pressure > 1100) {
      pressure = 1013;  // Default atmospheric pressure
    }
  } else {
    Serial.println("  BME280 not initialized!");
    needDHTBackup = true;
    pressure = 1013;
  }
  
  // Use DHT11 as backup if BME280 failed
  if (needDHTBackup && dhtInitialized) {
    Serial.println("  >>> Switching to DHT11 backup sensor...");
    float dhtTemp, dhtHum;
    readDHT11(dhtTemp, dhtHum);
    
    if (dhtTemp != 0 || dhtHum != 0) {
      temp = dhtTemp;
      humidity = dhtHum;
      usingDHTBackup = true;
      Serial.println("  >>> Using DHT11 readings successfully!");
    } else {
      Serial.println("  >>> DHT11 backup also failed!");
      temp = 0;
      humidity = 0;
      usingDHTBackup = false;
    }
  } else if (needDHTBackup) {
    Serial.println("  >>> DHT11 backup not available!");
    temp = 0;
    humidity = 0;
    usingDHTBackup = false;
  } else {
    usingDHTBackup = false;
  }
}

// Read ultrasonic distance for tank level
float readUltrasonicDistance() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  
  long duration = pulseIn(PIN_ECHO, HIGH, 30000);  // 30ms timeout
  
  if (duration == 0) {
    return TANK_EMPTY_DISTANCE;  // Timeout - assume empty
  }
  
  float distance = duration * 0.034 / 2;  // Convert to cm
  return constrain(distance, 0, 400);
}

// Convert distance to tank level percentage
int calculateTankLevel(float distance) {
  int level = map((int)distance, TANK_EMPTY_DISTANCE, TANK_FULL_DISTANCE, 0, 100);
  return constrain(level, 0, 100);
}

// Read rain sensor (digital from D27)
int readRainSensor() {
  // Rain sensor: LOW when wet (rain detected)
  int rainDigital = digitalRead(PIN_RAIN);
  return (rainDigital == LOW) ? 1 : 0;
}

// Read paddy water level sensor from ADS1115 (A2)
int readPaddyWaterLevel() {
  if (!adsInitialized) {
    Serial.println("ADS1115 not initialized for paddy level!");
    return 0;
  }
  
  int16_t rawValue = ads.readADC_SingleEnded(ADS_CHANNEL_PADDY_LEVEL);
  
  // Debug output
  Serial.print("  Paddy (A2) raw: ");
  Serial.print(rawValue);
  
  // Map raw value to percentage (INVERTED like soil sensor)
  // Water level sensor: Higher raw value = DRY/No water = 0%
  //                     Lower raw value = WET/Submerged = 100%
  // Map raw value to percentage (INVERTED like soil sensor)
  // Water level sensor: Higher raw value = DRY/No water = 0%
  //                     Lower raw value = WET/Submerged = 100%
  // Using dedicated PADDY calibration for higher sensitivity
  int level = map(rawValue, PADDY_DRY_VALUE, PADDY_WET_VALUE, 0, 100);
  level = constrain(level, 0, 100);
  
  Serial.print(" -> ");
  Serial.print(level);
  Serial.println("%");
  
  return level;
}

// Read PIR motion sensor (D33)
bool readPIR() {
  bool motion = digitalRead(PIN_PIR) == HIGH;
  if (motion) {
    Serial.println("  *** PIR: Motion Detected! ***");
  }
  return motion;
}

// ============================================================
// ACTUATOR CONTROL FUNCTIONS
// ============================================================

// Control pumps via MCP23017
void setPump(int pumpNum, bool state) {
  if (!mcpInitialized) {
    Serial.println("  MCP23017 not initialized - cannot control pump");
    return;
  }
  
  int pin;
  switch (pumpNum) {
    case 1: pin = MCP_PUMP1; pump1State = state; break;
    case 2: pin = MCP_PUMP2; pump2State = state; break;
    case 3: pin = MCP_PUMP3; pump3State = state; break;
    case 4: pin = MCP_PUMP4; pump4State = state; break;
    default: return;
  }
  
  // Apply inverted logic for relay modules (LOW = ON, HIGH = OFF)
  bool outputState = RELAY_INVERTED ? !state : state;
  mcp.digitalWrite(pin, outputState ? HIGH : LOW);
  
  Serial.print("  Pump");
  Serial.print(pumpNum);
  Serial.print(": ");
  Serial.print(state ? "ON" : "OFF");
  Serial.print(" [MCP pin ");
  Serial.print(pin);
  Serial.print(" = ");
  Serial.print(outputState ? "HIGH" : "LOW");
  Serial.println("]");
}

// Control LEDs via direct ESP32 GPIO (D12, D13, D14, D26)
void setLED(int ledNum, bool state) {
  int pin;
  switch (ledNum) {
    case 1: pin = PIN_LED1; break;
    case 2: pin = PIN_LED2; break;
    case 3: pin = PIN_LED3; break;
    case 4: pin = PIN_LED4; break;
    default: return;
  }
  
  // Apply inverted logic if needed (for relay modules: LOW=ON)
  bool outputState = LED_INVERTED ? !state : state;
  digitalWrite(pin, outputState ? HIGH : LOW);
  
  if (ledNum >= 1 && ledNum <= 4) {
    ledStates[ledNum - 1] = state;
  }
  
  Serial.print("  LED");
  Serial.print(ledNum);
  Serial.print(" (GPIO");
  Serial.print(pin);
  Serial.print("): ");
  Serial.print(state ? "ON" : "OFF");
  Serial.print(" [output=");
  Serial.print(outputState ? "HIGH" : "LOW");
  Serial.println("]");
}

void setAllLEDs(bool state) {
  for (int i = 1; i <= 4; i++) {
    setLED(i, state);
  }
}

// Control buzzer via direct ESP32 GPIO (D25)
void setBuzzer(bool state) {
  digitalWrite(PIN_BUZZER, state ? HIGH : LOW);
  buzzerState = state;
  Serial.print("  Buzzer (GPIO");
  Serial.print(PIN_BUZZER);
  Serial.print("): ");
  Serial.println(state ? "ON" : "OFF");
}

// Auto control LEDs based on LDR
static bool lastLedState = false;  // Track LED state to reduce spam

void autoControlLEDs() {
  int ldrValue = readLDR();
  bool isDark = false;
  bool shouldBeOn = false;
  
  // Determine if it's dark based on LDR reading
  // If LDR_INVERTED: LOW value = dark
  // If not inverted: HIGH value = dark
  if (LDR_INVERTED) {
    isDark = (ldrValue < LDR_DARK_THRESHOLD);  // LOW = dark
  } else {
    isDark = (ldrValue > LDR_DARK_THRESHOLD);  // HIGH = dark
  }
  
  if (nightMode == "ON") {
    shouldBeOn = true;
  } else if (nightMode == "OFF") {
    shouldBeOn = false;
  } else {  // AUTO mode
    shouldBeOn = isDark;
  }
  
  // Only update and print when state changes
  if (shouldBeOn != lastLedState) {
    Serial.print("\n[LDR AUTO] Value: ");
    Serial.print(ldrValue);
    Serial.print(" | Threshold: ");
    Serial.print(LDR_DARK_THRESHOLD);
    Serial.print(" | Dark: ");
    Serial.print(isDark ? "YES" : "NO");
    Serial.print(" | Mode: ");
    Serial.print(nightMode);
    Serial.print(" -> 4 White Lamps: ");
    Serial.println(shouldBeOn ? "ON" : "OFF");
    
    setAllLEDs(shouldBeOn);
    lastLedState = shouldBeOn;
  }
}

// ============================================================
// MAIN LOOP
// ============================================================

// Variables for PIR motion detection (red LED)
unsigned long lastMotionTime = 0;
const unsigned long motionAlertDuration = 5000;  // Red LED stays on for 5 seconds after motion
bool pirAlertActive = false;

// Debug timer
unsigned long lastDebugPrint = 0;

void loop() {
  // Reconnect WiFi if disconnected
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected. Reconnecting...");
    connectWiFi();
  }

  // Periodic debug output (every 5 seconds)
  if (millis() - lastDebugPrint > 5000) {
    int ldrVal = readLDR();
    Serial.print("[DEBUG] LDR=");
    Serial.print(ldrVal);
    Serial.print(" (threshold=");
    Serial.print(LDR_DARK_THRESHOLD);
    Serial.print(") | PIR=");
    Serial.print(readPIR() ? "MOTION" : "none");
    Serial.print(" | NightMode=");
    Serial.println(nightMode);
    
    // Print raw sensor values for debugging
    printDebugSensors();
    
    lastDebugPrint = millis();
  }

  // =============================================
  // LDR -> Controls 4 White Lamp LEDs (night lights)
  // =============================================
  autoControlLEDs();  // Uses LDR to turn on/off 4 white lamps
  
  // =============================================
  // PIR -> Controls Red LED (motion alert)
  // =============================================
  bool motion = readPIR();
  
  if (motion) {
    // Motion detected - turn on RED LED
    if (!pirAlertActive) {
      Serial.println("*** PIR MOTION - Red LED ON ***");
    }
    pirAlertActive = true;
    lastMotionTime = millis();
    digitalWrite(PIN_RED_LED, HIGH);  // Red LED ON
    setBuzzer(true);  // Buzzer alert
  }
  
  // Turn off red LED and buzzer after duration (no motion for 5 sec)
  if (pirAlertActive) {
    // Turn off buzzer after 3 seconds
    if (millis() - lastMotionTime > 3000) {
      setBuzzer(false);
    }
    // Turn off red LED after 5 seconds
    if (millis() - lastMotionTime > motionAlertDuration) {
      pirAlertActive = false;
      digitalWrite(PIN_RED_LED, LOW);  // Red LED OFF
      Serial.println("*** No motion - Red LED OFF ***");
    }
  }

  // Periodic sensor update
  if (millis() - lastUpdate >= updateInterval) {
    sendSensorData();
    lastUpdate = millis();
  }
  
  // Small delay to prevent overwhelming
  delay(100);
}

// ============================================================
// DATA TRANSMISSION
// ============================================================

void sendSensorData() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Cannot send data - WiFi not connected");
    return;
  }

  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(5000);

  // Read all sensors
  float temp, humidity, pressure;
  readBME280(temp, humidity, pressure);
  
  // ADS1115 Sensors:
  // A0: Soil 1 (Zone Alpha) - controls Pump 1
  // A1: Soil 2 (Zone Beta) - controls Pump 2
  // A2: Water Level (Paddy Field) - controls Pump 3
  // A3: Soil 3 (Average monitoring only)
  int soil1 = readSoilMoisture(ADS_CHANNEL_SOIL1);       // Zone Alpha
  int soil2 = readSoilMoisture(ADS_CHANNEL_SOIL2);       // Zone Beta
  int paddyLevel = readPaddyWaterLevel();                 // Paddy Field water level
  int soil3 = readSoilMoisture(ADS_CHANNEL_SOIL3);       // Average monitoring sensor
  
  // Calculate average soil moisture from all 3 soil sensors
  int avgSoil = (soil1 + soil2 + soil3) / 3;
  
  int ldr = readLDR();
  
  float tankDist = readUltrasonicDistance();
  int tankLevel = calculateTankLevel(tankDist);
  
  int rain = readRainSensor();
  bool pir = readPIR();

  // Build JSON payload
  StaticJsonDocument<512> doc;
  
  // Environmental sensors (BME280 with DHT11 backup)
  doc["temp"] = round(temp * 10) / 10.0;
  doc["humidity"] = round(humidity * 10) / 10.0;
  doc["pressure"] = round(pressure);
  doc["tempSource"] = usingDHTBackup ? "DHT11" : "BME280";  // Report which sensor is active
  
  // Soil moisture sensors (ADS1115 A0, A1, A3)
  doc["soil1"] = soil1;         // Zone Alpha (A0) -> Pump 1
  doc["soil2"] = soil2;         // Zone Beta (A1) -> Pump 2
  doc["soil3"] = soil3;         // Monitoring sensor (A3)
  doc["avgSoil"] = avgSoil;     // Average of all 3 soil sensors
  
  // Paddy Field water level (ADS1115 A2) -> Pump 3
  doc["paddyLevel"] = paddyLevel;
  
  // Other sensors
  doc["rain"] = rain;
  doc["tankLevel"] = tankLevel;  // Ultrasonic -> Pump 4 (refill)
  doc["tankDist"] = (int)tankDist;
  doc["ldr"] = ldr;
  
  // Motion detection
  doc["pir1"] = pir;
  doc["pir2"] = false;  // Reserved for second PIR if needed
  
  // Report current actuator states
  doc["pump1"] = pump1State;
  doc["pump2"] = pump2State;
  doc["pump3"] = pump3State;
  doc["pumpTank"] = pump4State;
  
  // Report LED states
  JsonArray ledsArray = doc.createNestedArray("night_leds");
  for (int i = 0; i < 4; i++) {
    ledsArray.add(ledStates[i] ? 1 : 0);
  }

  // Serialize and send
  String jsonStr;
  serializeJson(doc, jsonStr);

  Serial.print("TX: ");
  Serial.println(jsonStr);

  int httpCode = http.POST(jsonStr);
  
  if (httpCode > 0) {
    String response = http.getString();
    Serial.print("RX: ");
    Serial.println(response);
    processServerResponse(response);
  } else {
    Serial.print("HTTP Error: ");
    Serial.println(httpCode);
  }
  
  http.end();
}

// ============================================================
// SERVER RESPONSE PROCESSING
// ============================================================

void processServerResponse(String response) {
  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, response);

  if (error) {
    Serial.print("JSON Parse Error: ");
    Serial.println(error.c_str());
    return;
  }

  // Process pump commands
  if (doc.containsKey("pumps")) {
    Serial.println("\n[Processing Pump Commands from Server]");
    JsonObject pumps = doc["pumps"];
    
    if (pumps.containsKey("div1")) {
      bool cmd = pumps["div1"].as<bool>();
      Serial.print("  Server says Pump1 (div1): ");
      Serial.println(cmd ? "ON" : "OFF");
      setPump(1, cmd);
    }
    if (pumps.containsKey("div2")) {
      bool cmd = pumps["div2"].as<bool>();
      Serial.print("  Server says Pump2 (div2): ");
      Serial.println(cmd ? "ON" : "OFF");
      setPump(2, cmd);
    }
    if (pumps.containsKey("div3")) {
      bool cmd = pumps["div3"].as<bool>();
      Serial.print("  Server says Pump3 (div3): ");
      Serial.println(cmd ? "ON" : "OFF");
      setPump(3, cmd);
    }
    if (pumps.containsKey("tank")) {
      bool cmd = pumps["tank"].as<bool>();
      Serial.print("  Server says Pump4 (tank): ");
      Serial.println(cmd ? "ON" : "OFF");
      setPump(4, cmd);
    }
  }

  // Process buzzer commands
  if (doc.containsKey("buzzers")) {
    JsonObject buzzers = doc["buzzers"];
    bool anyBuzzer = buzzers["front"].as<bool>() || buzzers["back"].as<bool>();
    setBuzzer(anyBuzzer);
  }

  // Process night mode
  if (doc.containsKey("night_mode")) {
    nightMode = doc["night_mode"].as<String>();
    Serial.print("Night Mode: ");
    Serial.println(nightMode);
  }
}
