# Wokwi Integration — Smart Firefighter Wearable System

Wokwi (wokwi.com) is the browser-based hardware simulator used in this project to represent and validate the ESP32 circuit design. It provides real simulation of I2C, 1-Wire, ADC, GPIO, and PWM — matching the firmware logic of `wokwi/sketch.ino` without requiring physical hardware.

---

## Role of Wokwi in this Project

| Layer | Tool |
|---|---|
| Hardware circuit + firmware | Wokwi — `wokwi/diagram.json` + `wokwi/sketch.ino` |
| Live telemetry + MQTT | `python/simulated_wearable.py` |
| Web dashboard | FastAPI — `uvicorn web.main:app --reload` |

Wokwi and the Python simulation run **independently**. They share the same JSON payload structure and classification thresholds, but data does not flow between them.

MQTT is used in this project as a **software-level emulation** of the logical data flow of LoRa communication. It does not simulate LoRa physical-layer characteristics (RF range, signal attenuation, wall penetration, antenna gain). In a production deployment the ESP32 would use a LoRa radio module to reach a LoRa gateway, which forwards data via MQTT to the cloud.

---

## Component Support

| Component | Wokwi Part | Support |
|---|---|---|
| ESP32 DevKit V1 | `wokwi-esp32-devkit-v1` | Full simulation |
| SSD1306 OLED 128×64 | `wokwi-ssd1306` | Full I2C simulation (addr 0x3C) |
| MPU6050 IMU | `wokwi-mpu6050` | Full I2C simulation (addr 0x68) |
| DS18B20 Temperature | `wokwi-ds18b20` | Full 1-Wire simulation on GPIO4 |
| MQ-7 CO Gas Sensor | `wokwi-potentiometer` | Partial — potentiometer as analog substitute |
| MAX30102 Heart Rate | *(no Wokwi part)* | Software random-walk in `readHeartRate()` |
| 3× LEDs + 220 Ω | `wokwi-led` + `wokwi-resistor` | Full GPIO simulation |
| Piezo Buzzer | `wokwi-buzzer` | Full PWM simulation |
| 4.7 kΩ DS18B20 pull-up | `wokwi-resistor` | Full simulation |

---

## GPIO Pin Assignment

| GPIO | Signal | Component |
|---|---|---|
| GPIO4 | 1-Wire DATA | DS18B20 (4.7 kΩ pull-up to 3V3) |
| GPIO18 | Buzzer PWM | Piezo Buzzer |
| GPIO21 | I2C SDA | MPU6050 + SSD1306 (shared bus) |
| GPIO22 | I2C SCL | MPU6050 + SSD1306 (shared clock) |
| GPIO25 | LED Red | DANGER / FALL indicator (220 Ω series) |
| GPIO26 | LED Yellow | WARNING indicator (220 Ω series) |
| GPIO27 | LED Green | OK indicator (220 Ω series) |
| GPIO34 | ADC Input | MQ-7 / Potentiometer (input-only pin) |

---

## How to Open in Wokwi

### From the Web Dashboard (recommended)

1. Start the server: `py -m uvicorn web.main:app --reload`
2. Open [http://127.0.0.1:8000/simulation](http://127.0.0.1:8000/simulation)
3. In the **Wokwi Hardware Simulation** panel:
   - Click **Open in Wokwi ↗** to open a blank ESP32 project on wokwi.com
   - Download `diagram.json`, `sketch.ino`, and `libraries.txt` using the three download buttons
4. In the Wokwi project:
   - Paste `diagram.json` into the **diagram.json** tab (select all, replace)
   - Paste `sketch.ino` into the **sketch.ino** tab (select all, replace)
   - Click **+**, name the new file `libraries.txt`, paste the contents
5. Press **▶ Play** to start the simulation

### Directly from Files

1. Open [https://wokwi.com/projects/new/esp32](https://wokwi.com/projects/new/esp32)
2. Paste the contents of `wokwi/diagram.json` into the diagram tab
3. Paste the contents of `wokwi/sketch.ino` into the sketch tab
4. Create `libraries.txt` and paste the contents of `wokwi/libraries.txt`
5. Press **▶ Play**

---

## Interacting with the Wokwi Simulation

| Interaction | Effect |
|---|---|
| Turn the **potentiometer knob** | Changes CO ppm (0 → 500 ppm). Simulates MQ-7 output. |
| Right-click **MPU6050** → Rotate rapidly | Triggers fall detection via acceleration magnitude threshold. |
| Watch the **OLED display** | Shows live sensor readings and current status string. |
| Watch the **LEDs** | Green = OK, Yellow = WARNING, Red = DANGER or FALL. |
| Watch the **Buzzer** | Pulses slowly on WARNING, rapidly on DANGER/FALL. |
| Open **Serial Monitor** | Prints one JSON-formatted reading every 2 s. |

---

## Firmware Behaviour

The sketch (`wokwi/sketch.ino`) uses real sensor libraries:

- **DS18B20** — `OneWire` + `DallasTemperature`. Reads actual 1-Wire temperature from the simulated sensor. Wokwi's default temperature is ~27 °C.
- **MPU6050** — `Adafruit_MPU6050`. Reads real accelerometer data. Fall is detected when acceleration magnitude exceeds 25 m/s² or drops below 2 m/s² (free-fall).
- **MQ-7 (Potentiometer)** — `analogRead(GPIO34)` returns 0–4095. Mapped linearly to 0–500 ppm.
- **MAX30102** — No Wokwi part available. Heart rate is generated as a bounded random walk in software.
- **SSD1306 OLED** — `Adafruit_SSD1306`. Displays status, sensor readings, and firefighter ID.
- **WiFi / MQTT** — Disabled in Wokwi (free tier cannot reach external servers). Telemetry appears only in the Serial Monitor.

Classification thresholds in the firmware match those in `python/simulated_wearable.py`:

| Status | Heart Rate | Body Temp | CO Level |
|---|---|---|---|
| OK | < 110 BPM | < 38 °C | < 50 ppm |
| WARNING | 110–130 BPM | 38–39.5 °C | 50–200 ppm |
| DANGER | > 130 BPM | > 39.5 °C | > 200 ppm |
| FALL_DETECTED | Any | Any | Any (fall triggered) |

---

## Wokwi Limitations

| Limitation | Explanation |
|---|---|
| No WiFi / MQTT | Wokwi free tier cannot reach external servers. Use Serial Monitor for output. |
| No MAX30102 part | Heart rate is generated as software random walk inside `readHeartRate()`. |
| MQ-7 substitute | Potentiometer replaces the MQ-7. Turn the knob to simulate CO 0–500 ppm. |
| DS18B20 default | Starts at ~27 °C. Adjust the Wokwi temperature slider to test thresholds. |
| No NTP time | `timestamp` field is set to `"wokwi-sim"` as ESP32 cannot reach NTP. |
| No LoRa RF | Wokwi cannot simulate LoRa radio. MQTT/WiFi represents the logical data path. |

---

## Files

| File | Purpose |
|---|---|
| `wokwi/diagram.json` | Wokwi circuit diagram — all component placements and wire connections |
| `wokwi/sketch.ino` | ESP32 firmware — reads sensors, classifies status, drives outputs |
| `wokwi/libraries.txt` | Wokwi library manifest — paste into `libraries.txt` tab in Wokwi |
| `wokwi/README_WOKWI.md` | Quick-start guide for Wokwi (standalone, no web server required) |

---

## Flashing to Real Hardware

To deploy `sketch.ino` to a physical ESP32:

1. Install [Arduino IDE](https://www.arduino.cc/en/software) with ESP32 board support
2. Install libraries from `wokwi/libraries.txt` via the Library Manager
3. Set WiFi credentials in `sketch.ino`:
   ```cpp
   const char* WIFI_SSID     = "YourNetworkName";
   const char* WIFI_PASSWORD = "YourPassword";
   ```
4. Select **Board: ESP32 Dev Module** and the correct COM port
5. Click **Upload**; open Serial Monitor at 115200 baud
6. On real hardware, MQTT publishes to `broker.emqx.io:1883` on topic `smart_firefighter/ff01/telemetry` — the same topic monitored by the FastAPI dashboard
