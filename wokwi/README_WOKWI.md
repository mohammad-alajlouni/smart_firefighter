# Wokwi Hardware Simulation — Smart Firefighter Wearable System

Wokwi is used in this project to **represent and validate the simulated ESP32 hardware circuit and component wiring**.
MQTT is used separately as a software-level communication mechanism to emulate the logical data flow of LoRa communication.
This setup does **not** test real LoRa RF behaviour (range, signal attenuation, wall penetration, or antenna gain).

---

## What Wokwi Provides

| Role | Tool |
|---|---|
| Hardware circuit representation | Wokwi — `wokwi/diagram.json` |
| ESP32 firmware | Wokwi — `wokwi/sketch.ino` |
| Live MQTT + Python simulation | `python/simulated_wearable.py` |
| Web dashboard with live data | FastAPI — `uvicorn web.main:app --reload` |

---

## Component Support Table

| Component | Wokwi Part | Support in Wokwi |
|---|---|---|
| ESP32 DevKit V1 | `wokwi-esp32-devkit-v1` | ● Full hardware simulation |
| SSD1306 OLED 128×64 | `wokwi-ssd1306` | ● Full I2C simulation (addr 0x3C) |
| MPU6050 IMU | `wokwi-mpu6050` | ● Full I2C simulation (addr 0x68) — rotate to trigger fall |
| DS18B20 Temperature | `wokwi-ds18b20` | ● Full 1-Wire simulation on GPIO4 |
| MQ-7 CO Gas Sensor | `wokwi-potentiometer` | ◐ Partial — potentiometer as analog substitute |
| MAX30102 Heart Rate | *(no Wokwi part)* | ○ Software-generated in `readHeartRate()` |
| Green LED (OK) | `wokwi-led` | ● Full GPIO simulation — GPIO27 |
| Yellow LED (WARNING) | `wokwi-led` | ● Full GPIO simulation — GPIO26 |
| Red LED (DANGER/FALL) | `wokwi-led` | ● Full GPIO simulation — GPIO25 |
| Piezo Buzzer | `wokwi-buzzer` | ● Full PWM simulation — GPIO18 |
| 4.7 kΩ DS18B20 pull-up | `wokwi-resistor` | ● Full simulation |
| 220 Ω LED series (×3) | `wokwi-resistor` | ● Full simulation |

---

## GPIO Pin Assignment

| GPIO | Signal | Component | Notes |
|---|---|---|---|
| GPIO4 | 1-Wire DATA | DS18B20 | 4.7 kΩ pull-up to 3V3 |
| GPIO18 | Buzzer PWM | Buzzer | Active HIGH |
| GPIO21 | I2C SDA | MPU6050 + SSD1306 OLED | Shared bus |
| GPIO22 | I2C SCL | MPU6050 + SSD1306 OLED | Shared clock |
| GPIO25 | LED Red | DANGER / FALL indicator | 220 Ω series |
| GPIO26 | LED Yellow | WARNING indicator | 220 Ω series |
| GPIO27 | LED Green | OK indicator | 220 Ω series |
| GPIO34 | ADC Input | MQ-7 (Potentiometer in Wokwi) | Input-only pin |

---

## How to Open in Wokwi

### Method 1 — Paste files manually (recommended)

1. Open [https://wokwi.com/projects/new/esp32](https://wokwi.com/projects/new/esp32)
2. Click the **diagram.json** tab → select all → paste contents of `wokwi/diagram.json`
3. Click the **sketch.ino** tab → select all → paste contents of `wokwi/sketch.ino`
4. Click **+** → add a file named `libraries.txt` → paste contents of `wokwi/libraries.txt`
5. Press the green **▶ Play** button to start the simulation

### Method 2 — From the web dashboard

1. Start the web server: `py -m uvicorn web.main:app --reload`
2. Open [http://127.0.0.1:8000/simulation](http://127.0.0.1:8000/simulation)
3. In the **Wokwi Hardware Simulation** section, click **⬇ diagram.json** and **⬇ sketch.ino** to download
4. Follow Method 1 above to paste them into Wokwi

---

## What You Will See in Wokwi

After pressing **▶ Play**:

- **OLED display** shows live sensor readings and the current status string
- **Green LED** lights when status is OK
- **Yellow LED** lights on WARNING (heart rate 110–130 BPM, temp 38–39.5°C, CO 50–200 ppm)
- **Red LED** lights on DANGER or FALL_DETECTED
- **Buzzer** pulses slowly on WARNING, rapidly on DANGER/FALL
- **Serial Monitor** prints one JSON-formatted reading every 2 seconds
- **Potentiometer** (MQ-7 substitute) — turn the knob to change CO ppm (0→500)
- **MPU6050** — right-click the part and rotate it rapidly to trigger fall detection

---

## Limitations in Wokwi

| Limitation | Explanation |
|---|---|
| No WiFi / MQTT | Wokwi free tier cannot reach external servers. Telemetry is printed to Serial only. |
| No MAX30102 part | Wokwi has no heart-rate sensor model. Heart rate is generated as a random walk in `readHeartRate()`. |
| MQ-7 substitute | A `wokwi-potentiometer` replaces the MQ-7. Turn the knob to simulate CO levels 0–500 ppm. |
| DS18B20 default temp | Wokwi's DS18B20 starts at ~27°C. This triggers no alarm unless you configure it differently. |
| No NTP time | `timestamp` field is set to `"wokwi-sim"` because the ESP32 cannot reach an NTP server. |

---

## Using Wokwi Alongside the Python Simulation

Wokwi and the Python MQTT simulation are **independent**. They share:
- The same JSON payload structure
- The same classification thresholds
- The same GPIO/alert mapping

They do **not** share data — the Wokwi sketch uses Serial output only, while
`python/simulated_wearable.py` sends data to the real MQTT broker and the FastAPI dashboard.

---

## Flashing to Real Hardware

To deploy to a physical ESP32:

1. Install [Arduino IDE](https://www.arduino.cc/en/software) with ESP32 board support
2. Install all libraries from `wokwi/libraries.txt` via Library Manager
3. Edit `sketch.ino` — set your WiFi credentials:
   ```c
   const char* WIFI_SSID     = "YourNetworkName";
   const char* WIFI_PASSWORD = "YourPassword";
   ```
4. Select **Board: ESP32 Dev Module** and the correct COM port
5. Click **Upload**
6. Open **Serial Monitor** at 115200 baud to see readings and MQTT status

On real hardware, the ESP32 will connect to `broker.emqx.io:1883` and publish
telemetry to `smart_firefighter/ff01/telemetry` — the same topic watched by
`python/logger_analyzer.py` and the FastAPI web dashboard.
