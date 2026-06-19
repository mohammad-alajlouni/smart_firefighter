/**
 * Smart Firefighter Wearable System — ESP32 Firmware (Wokwi Edition)
 *
 * COMPONENT SUPPORT IN THIS WOKWI BUILD:
 *   Component       Wokwi Part              Status
 *   ─────────────── ────────────────────── ──────────────────────────────
 *   ESP32 DevKit    wokwi-esp32-devkit-v1   Full hardware simulation
 *   SSD1306 OLED    wokwi-ssd1306           Full I2C simulation (0x3C)
 *   MPU6050 IMU     wokwi-mpu6050           Full I2C simulation (0x68)
 *   DS18B20 Temp    wokwi-ds18b20           Full 1-Wire simulation
 *   MQ-7 CO sensor  wokwi-potentiometer     Analog substitute (turn knob = CO ppm)
 *   MAX30102 HR     (no Wokwi part)         Software-generated plausible values
 *   Green LED       wokwi-led               Full GPIO simulation
 *   Yellow LED      wokwi-led               Full GPIO simulation
 *   Red LED         wokwi-led               Full GPIO simulation
 *   Buzzer          wokwi-buzzer            Full PWM simulation
 *   Resistors       wokwi-resistor          Full simulation (4.7 kΩ pull-up + 3×220 Ω)
 *
 * GPIO ASSIGNMENTS (match wokwi/diagram.json and web SVG circuit):
 *   GPIO4  = DS18B20 DATA (1-Wire, 4.7 kΩ pull-up to 3V3)
 *   GPIO18 = Buzzer positive terminal
 *   GPIO21 = I2C SDA — shared: MPU6050 (0x68) + SSD1306 OLED (0x3C)
 *   GPIO22 = I2C SCL — shared I2C clock
 *   GPIO25 = Red    LED anode (+ 220 Ω series resistor) → DANGER / FALL
 *   GPIO26 = Yellow LED anode (+ 220 Ω series resistor) → WARNING
 *   GPIO27 = Green  LED anode (+ 220 Ω series resistor) → OK
 *   GPIO34 = MQ-7 analog output (ADC input) → potentiometer in Wokwi
 *
 * HOW TO USE IN WOKWI:
 *   1. Go to https://wokwi.com/projects/new/esp32
 *   2. Paste wokwi/diagram.json into the diagram tab
 *   3. Paste this file into the sketch.ino tab
 *   4. Add libraries via Library Manager (see wokwi/libraries.txt)
 *   5. Press ▶ Play — OLED, LEDs, and buzzer respond in real time
 *   6. Rotate the MPU6050 part to trigger fall detection
 *   7. Turn the potentiometer to adjust simulated CO ppm
 *
 * ACADEMIC DISCLAIMER:
 *   MQTT is used to emulate the LOGICAL data flow of LoRa communication.
 *   It does NOT test LoRa physical-layer properties (RF range, signal
 *   attenuation, wall penetration, antenna gain, or interference).
 *   WiFi/MQTT will not connect inside the free Wokwi simulator.
 *   Use python/simulated_wearable.py for real MQTT communication.
 */

#include <Arduino.h>
#include <Wire.h>

// ── OLED ─────────────────────────────────────────────────────────────────────
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ── DS18B20 (real 1-Wire simulation in Wokwi) ─────────────────────────────
#include <OneWire.h>
#include <DallasTemperature.h>

// ── MPU6050 (real I2C simulation in Wokwi) ───────────────────────────────
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// ── MQTT (WiFi disabled in Wokwi; works on real hardware) ───────────────
#include <ArduinoJson.h>
#include <WiFi.h>
#include <PubSubClient.h>

// ═════════════════════════════════════════════════════════════════════════════
//   PIN DEFINITIONS  (must match wokwi/diagram.json)
// ═════════════════════════════════════════════════════════════════════════════
#define PIN_LED_GREEN   27
#define PIN_LED_YELLOW  26
#define PIN_LED_RED     25
#define PIN_BUZZER      18
#define PIN_DS18B20      4   // 1-Wire DATA, 4.7 kΩ pull-up to 3V3
#define PIN_MQ7_ADC     34   // Potentiometer SIG in Wokwi; real MQ-7 on hardware
// I2C: GPIO21 = SDA, GPIO22 = SCL (shared bus: MPU6050 + SSD1306)

// ═════════════════════════════════════════════════════════════════════════════
//   SENSOR OBJECTS
// ═════════════════════════════════════════════════════════════════════════════
OneWire           oneWire(PIN_DS18B20);
DallasTemperature ds18b20(&oneWire);

Adafruit_MPU6050  mpu;

#define OLED_W   128
#define OLED_H    64
#define OLED_ADDR 0x3C
Adafruit_SSD1306  display(OLED_W, OLED_H, &Wire, -1);

// ═════════════════════════════════════════════════════════════════════════════
//   WIFI / MQTT  (gracefully disabled in Wokwi)
// ═════════════════════════════════════════════════════════════════════════════
const char* WIFI_SSID       = "YOUR_SSID";
const char* WIFI_PASSWORD   = "YOUR_PASSWORD";
const char* MQTT_BROKER     = "broker.emqx.io";
const int   MQTT_PORT       = 1883;
const char* MQTT_TOPIC_TEL  = "smart_firefighter/ff01/telemetry";
const char* MQTT_TOPIC_ALT  = "smart_firefighter/ff01/alerts";
const char* FIREFIGHTER_ID  = "FF-01";

WiFiClient   wifiClient;
PubSubClient mqttClient(wifiClient);

// ═════════════════════════════════════════════════════════════════════════════
//   ALERT THRESHOLDS  (must match python/config.py)
// ═════════════════════════════════════════════════════════════════════════════
const float HR_OK_MAX    = 110.0f;   // BPM
const float HR_WARN_MAX  = 130.0f;
const float TMP_OK_MAX   = 38.0f;   // °C
const float TMP_WARN_MAX = 39.5f;
const float CO_OK_MAX    = 50.0f;   // ppm
const float CO_WARN_MAX  = 200.0f;
const float FALL_ACCEL   = 20.0f;   // m/s² spike → fall
const float FREE_FALL    =  3.0f;   // m/s² below → free-fall

// ═════════════════════════════════════════════════════════════════════════════
//   RUNTIME STATE
// ═════════════════════════════════════════════════════════════════════════════
float  heartRate    = 72.0f;
float  bodyTemp     = 37.0f;
float  coLevel      = 10.0f;
bool   fallDetected = false;
String statusStr    = "OK";
String alertMsg     = "All parameters normal";

unsigned long lastPublish  = 0;
const unsigned long PUB_MS = 2000UL;

unsigned long buzzerToggle = 0;
bool   buzzerState = false;
int    buzzerMode  = 0;   // 0=off, 1=slow (800 ms), 2=fast (250 ms)

unsigned long readingCount = 0;

// MAX30102 software simulation state (no Wokwi part available)
float simHR = 76.0f;

bool mpuOk   = false;
bool oledOk  = false;


// ═════════════════════════════════════════════════════════════════════════════
//   SETUP
// ═════════════════════════════════════════════════════════════════════════════
void setup() {
    Serial.begin(115200);
    Serial.println("\n[BOOT] Smart Firefighter — Wokwi Edition");

    // Output pins
    pinMode(PIN_LED_GREEN,  OUTPUT);
    pinMode(PIN_LED_YELLOW, OUTPUT);
    pinMode(PIN_LED_RED,    OUTPUT);
    pinMode(PIN_BUZZER,     OUTPUT);
    allLedsOff();
    digitalWrite(PIN_BUZZER, LOW);

    // I2C bus (shared: MPU6050 + SSD1306)
    Wire.begin(21, 22);

    // ── OLED ────────────────────────────────────────────────────────────────
    oledOk = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
    if (!oledOk) {
        Serial.println("[ERROR] SSD1306 OLED not found at 0x3C");
    } else {
        display.clearDisplay();
        display.setTextColor(SSD1306_WHITE);
        display.display();
        showSplash();
    }

    // ── MPU6050 (real Wokwi simulation) ─────────────────────────────────────
    mpuOk = mpu.begin();
    if (!mpuOk) {
        Serial.println("[ERROR] MPU6050 not found at 0x68");
    } else {
        mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
        mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
        Serial.println("[MPU6050] Ready (wokwi-mpu6050: rotate part to simulate fall)");
    }

    // ── DS18B20 (real Wokwi simulation) ─────────────────────────────────────
    ds18b20.begin();
    int dsCount = ds18b20.getDeviceCount();
    if (dsCount == 0) {
        Serial.println("[WARN] DS18B20 not found — check 4.7 kΩ pull-up on GPIO4");
    } else {
        Serial.printf("[DS18B20] %d device(s) found on 1-Wire bus\n", dsCount);
    }

    // ── MQ-7 pin (potentiometer in Wokwi) ────────────────────────────────────
    // GPIO34 is input-only on ESP32; analogRead() reads the pot wiper in Wokwi
    Serial.println("[MQ-7] ADC on GPIO34 (potentiometer in Wokwi; turn knob = CO ppm)");

    // ── MAX30102 note ────────────────────────────────────────────────────────
    Serial.println("[MAX30102] No Wokwi part — HR generated in software (readHeartRate)");

    // ── WiFi / MQTT (will fail gracefully in Wokwi) ────────────────────────
    connectWiFi();
    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    mqttClient.setKeepAlive(60);
    connectMQTT();

    Serial.println("[BOOT] Initialisation complete. Entering main loop...\n");
}


// ═════════════════════════════════════════════════════════════════════════════
//   MAIN LOOP
// ═════════════════════════════════════════════════════════════════════════════
void loop() {
    // Keep MQTT alive when connected
    if (WiFi.status() == WL_CONNECTED && !mqttClient.connected()) connectMQTT();
    if (mqttClient.connected()) mqttClient.loop();

    unsigned long now = millis();
    if (now - lastPublish >= PUB_MS) {
        lastPublish = now;
        readingCount++;

        readSensors();      // Steps 1-4: acquire readings
        classifyStatus();   // Steps 5-6: ESP32 logic + classification
        updateLocalAlerts();// Steps 7-8: OLED, LEDs, Buzzer
        publishTelemetry(); // Step 9:    MQTT (real hardware) or Serial (Wokwi)
        printSerial();
    }

    handleBuzzer();         // Non-blocking buzzer pattern
}


// ═════════════════════════════════════════════════════════════════════════════
//   SENSOR READING
// ═════════════════════════════════════════════════════════════════════════════
void readSensors() {
    readHeartRate();    // MAX30102  — software simulation (no Wokwi part)
    readBodyTemp();     // DS18B20   — real wokwi-ds18b20 simulation
    readCO();           // MQ-7      — potentiometer on GPIO34 in Wokwi
    readIMU();          // MPU6050   — real wokwi-mpu6050 simulation
}

// MAX30102: no Wokwi part — generate plausible realistic heart-rate variation
void readHeartRate() {
    float delta = ((float)random(-30, 31)) / 10.0f;  // ±3.0 BPM
    simHR = constrain(simHR + delta, 55.0f, 185.0f);
    heartRate = simHR;
}

// DS18B20: real wokwi-ds18b20 reading via OneWire + DallasTemperature
void readBodyTemp() {
    ds18b20.requestTemperatures();
    float t = ds18b20.getTempCByIndex(0);
    if (t == DEVICE_DISCONNECTED_C || t < -10.0f) {
        // Wokwi DS18B20 default is ~27°C; fallback if disconnected
        bodyTemp = 37.0f;
    } else {
        bodyTemp = t;
    }
}

// MQ-7: potentiometer wiper on GPIO34
// Turn the knob clockwise to simulate increasing CO concentration
void readCO() {
    int raw = analogRead(PIN_MQ7_ADC);          // 0 – 4095
    coLevel = (raw / 4095.0f) * 500.0f;         // Map to 0 – 500 ppm
}

// MPU6050: real wokwi-mpu6050 — detect fall via acceleration magnitude
// In Wokwi: right-click the MPU6050 part and rotate it rapidly to simulate a fall
void readIMU() {
    if (!mpuOk) {
        fallDetected = false;
        return;
    }
    sensors_event_t accel, gyro, temp;
    mpu.getEvent(&accel, &gyro, &temp);

    float mag = sqrtf(
        accel.acceleration.x * accel.acceleration.x +
        accel.acceleration.y * accel.acceleration.y +
        accel.acceleration.z * accel.acceleration.z
    );
    // Impact spike (>20 m/s²) or free-fall (<3 m/s²) → fall
    fallDetected = (mag > FALL_ACCEL || mag < FREE_FALL);
}


// ═════════════════════════════════════════════════════════════════════════════
//   STATUS CLASSIFICATION  (mirrors python/utils.py classify_status)
// ═════════════════════════════════════════════════════════════════════════════
void classifyStatus() {
    if (fallDetected) {
        statusStr = "FALL_DETECTED";
        alertMsg  = "Fall detected — immediate assistance required";
        return;
    }
    bool danger = (heartRate > HR_WARN_MAX || bodyTemp > TMP_WARN_MAX || coLevel > CO_WARN_MAX);
    if (danger) { statusStr = "DANGER";  alertMsg = buildAlertMsg(); return; }

    bool warning = (heartRate >= HR_OK_MAX || bodyTemp >= TMP_OK_MAX || coLevel >= CO_OK_MAX);
    if (warning) { statusStr = "WARNING"; alertMsg = buildAlertMsg(); return; }

    statusStr = "OK";
    alertMsg  = "All parameters within normal range";
}

String buildAlertMsg() {
    String m = "";
    if      (heartRate > HR_WARN_MAX)  m += "Critical HR ("  + String(heartRate, 0) + " BPM); ";
    else if (heartRate >= HR_OK_MAX)   m += "Elevated HR ("  + String(heartRate, 0) + " BPM); ";
    if      (bodyTemp > TMP_WARN_MAX)  m += "Critical Temp ("+ String(bodyTemp,  1) + " C); ";
    else if (bodyTemp >= TMP_OK_MAX)   m += "High Temp ("    + String(bodyTemp,  1) + " C); ";
    if      (coLevel > CO_WARN_MAX)    m += "Dangerous CO (" + String(coLevel,   0) + " ppm); ";
    else if (coLevel >= CO_OK_MAX)     m += "Elevated CO ("  + String(coLevel,   0) + " ppm); ";
    return m.length() ? m : "Condition requires monitoring";
}


// ═════════════════════════════════════════════════════════════════════════════
//   LOCAL ALERT OUTPUT
// ═════════════════════════════════════════════════════════════════════════════
void allLedsOff() {
    digitalWrite(PIN_LED_GREEN,  LOW);
    digitalWrite(PIN_LED_YELLOW, LOW);
    digitalWrite(PIN_LED_RED,    LOW);
}

void updateLocalAlerts() {
    updateOLED();
    allLedsOff();

    if (statusStr == "OK") {
        digitalWrite(PIN_LED_GREEN, HIGH);
        buzzerMode = 0;
    } else if (statusStr == "WARNING") {
        digitalWrite(PIN_LED_YELLOW, HIGH);
        buzzerMode = 1;    // slow beep 800 ms
    } else {
        // DANGER or FALL_DETECTED
        digitalWrite(PIN_LED_RED, HIGH);
        buzzerMode = 2;    // fast beep 250 ms
    }
}

void handleBuzzer() {
    if (buzzerMode == 0) { digitalWrite(PIN_BUZZER, LOW); buzzerState = false; return; }
    unsigned long period = (buzzerMode == 1) ? 800UL : 250UL;
    unsigned long now    = millis();
    if (now - buzzerToggle >= period) {
        buzzerToggle = now;
        buzzerState  = !buzzerState;
        digitalWrite(PIN_BUZZER, buzzerState ? HIGH : LOW);
    }
}


// ═════════════════════════════════════════════════════════════════════════════
//   OLED DISPLAY  (SSD1306, I2C GPIO21/22, addr 0x3C)
// ═════════════════════════════════════════════════════════════════════════════
void showSplash() {
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("Smart Firefighter");
    display.println("Wearable System v2.0");
    display.println("---- Wokwi Edition -");
    display.println(FIREFIGHTER_ID);
    display.println("Initialising...");
    display.display();
    delay(1200);
}

void updateOLED() {
    if (!oledOk) return;
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);

    // Header row
    display.print("ID:");
    display.print(FIREFIGHTER_ID);
    display.print("  #");
    display.println(readingCount);

    display.drawLine(0, 9, 127, 9, SSD1306_WHITE);

    // Sensor values
    display.setCursor(0, 12);
    display.printf("HR  : %.0f BPM\n", heartRate);
    display.printf("Temp: %.1f C\n",   bodyTemp);
    display.printf("CO  : %.0f ppm\n", coLevel);
    display.printf("Fall: %s\n",       fallDetected ? "YES!" : "No");

    display.drawLine(0, 53, 127, 53, SSD1306_WHITE);

    // Status
    display.setCursor(0, 56);
    display.setTextSize(1);
    display.print("> ");
    display.print(statusStr);

    display.display();
}


// ═════════════════════════════════════════════════════════════════════════════
//   MQTT PUBLISH  (JSON matches python/simulated_wearable.py format)
// ═════════════════════════════════════════════════════════════════════════════
void publishTelemetry() {
    StaticJsonDocument<320> doc;
    doc["firefighter_id"] = FIREFIGHTER_ID;
    doc["heart_rate"]     = round(heartRate * 10.0f) / 10.0f;
    doc["body_temp"]      = round(bodyTemp  * 10.0f) / 10.0f;
    doc["co_level"]       = round(coLevel   * 10.0f) / 10.0f;
    doc["fall_detected"]  = fallDetected;
    doc["status"]         = statusStr;
    doc["alert_message"]  = alertMsg;
    doc["timestamp"]      = "wokwi-sim";
    doc["reading_number"] = readingCount;

    if (mqttClient.connected()) {
        char buf[320];
        serializeJson(doc, buf);
        mqttClient.publish(MQTT_TOPIC_TEL, buf, false);
        if (statusStr != "OK") {
            StaticJsonDocument<160> alert;
            alert["firefighter_id"] = FIREFIGHTER_ID;
            alert["status"]         = statusStr;
            alert["alert_message"]  = alertMsg;
            char ab[160];
            serializeJson(alert, ab);
            mqttClient.publish(MQTT_TOPIC_ALT, ab, false);
        }
    }
}


// ═════════════════════════════════════════════════════════════════════════════
//   SERIAL DEBUG
// ═════════════════════════════════════════════════════════════════════════════
void printSerial() {
    Serial.printf("[#%lu] HR=%.0f BPM  Temp=%.1fC  CO=%.0f ppm  Fall=%s  >> %s\n",
        readingCount, heartRate, bodyTemp, coLevel,
        fallDetected ? "YES" : "no", statusStr.c_str());
}


// ═════════════════════════════════════════════════════════════════════════════
//   WIFI + MQTT HELPERS
// ═════════════════════════════════════════════════════════════════════════════
void connectWiFi() {
    Serial.print("[WiFi] Connecting to: ");
    Serial.print(WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    int tries = 0;
    while (WiFi.status() != WL_CONNECTED && tries < 15) {
        delay(400); Serial.print("."); tries++;
    }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) {
        Serial.print("[WiFi] Connected. IP: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("[WiFi] Not connected — MQTT disabled (normal in Wokwi).");
    }
}

void connectMQTT() {
    if (WiFi.status() != WL_CONNECTED) return;
    String cid = "esp32_ff_" + String(random(0xffff), HEX);
    if (mqttClient.connect(cid.c_str())) {
        Serial.println("[MQTT] Connected. Publishing telemetry...");
    } else {
        Serial.printf("[MQTT] Failed, rc=%d\n", mqttClient.state());
    }
}
