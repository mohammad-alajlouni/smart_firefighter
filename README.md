# Smart Firefighter Wearable System
### Design and Development Using IoT and LoRa Communication — Software Simulation

**Academic Final-Year Engineering Project**

---

## Project Overview

This project presents a complete simulation of a **Smart Firefighter Wearable System** — a wearable device designed to protect firefighters during active operations by continuously monitoring their physiological condition and the surrounding environment.

The system monitors four critical parameters in real time:

| Parameter | Sensor | Purpose |
|---|---|---|
| Heart Rate | MAX30102 | Detects cardiac stress or incapacitation |
| Body Temperature | DS18B20 | Monitors hyperthermia risk |
| Carbon Monoxide Level | MQ-7 | Detects toxic gas exposure |
| Fall / Incapacitation | MPU6050 | Detects sudden collapse or loss of movement |

All readings are continuously classified into four severity levels: **OK**, **WARNING**, **DANGER**, and **FALL DETECTED**. The system triggers appropriate local alerts on the wearable device and transmits live data to a command-side dashboard over MQTT — which emulates the logical behaviour of LoRa long-range wireless communication.

---

## Problem Statement

Firefighters face simultaneous threats from extreme heat, toxic gases, physical exhaustion, and the risk of sudden incapacitation during active operations. Command teams currently have limited real-time visibility into individual firefighter health and environmental exposure once personnel enter a structure. Without continuous monitoring, dangerous conditions may go undetected until intervention is no longer possible.

---

## Simulation Approach

This project demonstrates the full end-to-end behaviour of a smart wearable system entirely in software, without requiring physical hardware. The simulation generates realistic sensor readings for each of the six test scenarios, runs the classification logic, produces wearable device outputs (LED colour, buzzer state, OLED display), and transmits structured telemetry to a live web dashboard.

> **Note on MQTT and LoRa:**
> MQTT is used in this project as a software-level emulation of the logical data flow of LoRa communication. It does **not** simulate LoRa physical-layer characteristics (RF range, signal attenuation, wall penetration, or antenna gain). In a real deployment, the ESP32 would use a LoRa radio module to reach a LoRa gateway, which would then forward data via MQTT to the cloud.

---

## System Architecture

```
Simulated Sensor Unit (ESP32 wearable)
         │
         │  MQTT publish — emulates LoRa → gateway → cloud
         ▼
    MQTT Broker (broker.emqx.io)
         │
    ┌────┴────┐
    ▼         ▼
Web Dashboard   Logger / Analyzer
(FastAPI)       (CSV + Reports + Charts)
```

**Data flow through the wearable unit (13 steps per cycle):**

1. Read heart rate from MAX30102
2. Read body temperature from DS18B20
3. Read CO level from MQ-7
4. Read IMU / fall state from MPU6050
5. ESP32 processes all four readings
6. Classify status: OK / WARNING / DANGER / FALL DETECTED
7. Update SSD1306 OLED display
8. Set LEDs and Buzzer output
9. Publish JSON payload via MQTT
10. FastAPI dashboard receives telemetry
11. WebSocket broadcast to browser
12. Logger writes CSV record
13. Session report counters updated

---

## How to Run

**Requirements:** Python 3.10 or newer, internet connection.

```
py run.py
```

That is the only command needed. The launcher automatically checks which packages are missing, installs only those, then starts the server.

Once running, open your browser at:

**http://127.0.0.1:8000**

---

## Web Dashboard Pages

| Page | URL | What it Shows |
|---|---|---|
| **Dashboard** | `/` | Live sensor readings, real-time charts, status indicator, wearable alert panel |
| **Simulation Lab** | `/simulation` | Step-by-step process flow, circuit diagram, per-component live status, JSON payload |
| **Logs** | `/logs` | Full event log, filterable by status, exportable as CSV |
| **Reports** | `/reports` | Session statistics: total readings, warning/danger/fall counts, peak values |

---

## Test Scenarios

Six scenarios are provided to demonstrate the full range of system responses. Select the scenario from the dropdown on the dashboard or the simulation lab, then press **Start Simulation**.

| Scenario | What it Simulates | Expected System Response |
|---|---|---|
| **Normal** | All parameters within safe limits | Status: OK — Green LED on, no alarm |
| **High Temperature** | Firefighter developing hyperthermia | Status: WARNING then DANGER — Yellow/Red LED, buzzer |
| **High CO** | Carbon monoxide accumulation in structure | Status: WARNING then DANGER — Red LED, fast buzzer |
| **High Heart Rate** | Extreme physical exertion | Status: DANGER — Red LED, fast buzzer |
| **Fall Detected** | Sudden incapacitation or collapse | Status: FALL DETECTED — Red LED, fast buzzer, OLED alert |
| **Multiple Hazards** | All hazards simultaneously | Status: DANGER/FALL — All alerts active simultaneously |

---

## Classification Thresholds

| Parameter | OK | WARNING | DANGER |
|---|---|---|---|
| Heart Rate | < 110 BPM | 110 – 130 BPM | > 130 BPM |
| Body Temperature | < 38.0 °C | 38.0 – 39.5 °C | > 39.5 °C |
| CO Level | < 50 ppm | 50 – 200 ppm | > 200 ppm |
| Fall Detection | — | — | Immediate FALL DETECTED (highest priority) |

---

## Wearable Alert Logic

| Status | Green LED | Yellow LED | Red LED | Buzzer | OLED |
|---|---|---|---|---|---|
| OK | ON | OFF | OFF | OFF | OK — Safe |
| WARNING | OFF | ON | OFF | Slow beep | WARN — Check readings |
| DANGER | OFF | OFF | ON | Fast beep | DANGER — Evacuate |
| FALL DETECTED | OFF | OFF | ON | Fast beep | FALL — Send rescue |

---

## Hardware Design (Wokwi Simulation)

The circuit design is implemented and documented for the **Wokwi** browser-based ESP32 simulator. The following components are connected to the ESP32 DevKit V1:

| Component | Interface | GPIO |
|---|---|---|
| MAX30102 Heart Rate Sensor | I2C (SDA/SCL) | GPIO 21 / 22 |
| DS18B20 Temperature Sensor | 1-Wire + 4.7 kΩ pull-up | GPIO 4 |
| MQ-7 Carbon Monoxide Sensor | Analog (ADC) | GPIO 34 |
| MPU6050 IMU / Fall Sensor | I2C (SDA/SCL) | GPIO 21 / 22 |
| SSD1306 OLED Display | I2C (SDA/SCL) | GPIO 21 / 22 |
| Green LED + 220 Ω | Digital output | GPIO 27 |
| Yellow LED + 220 Ω | Digital output | GPIO 26 |
| Red LED + 220 Ω | Digital output | GPIO 25 |
| Buzzer | PWM | GPIO 18 |

The Wokwi circuit files (`diagram.json`, `sketch.ino`, `libraries.txt`) are available via the `/api/wokwi/` endpoints and can be downloaded directly from the Simulation Lab page.

---

## Limitations

- All sensor readings are mathematically generated — no physical hardware is used.
- MQTT is a software substitute for LoRa and does not test RF propagation, range, or signal quality.
- The simulation covers a single firefighter unit; multi-unit team monitoring is not implemented.
- The public MQTT broker (`broker.emqx.io`) is used without encryption or authentication.

---

## Future Work

1. **Hardware deployment** — Flash the firmware to a real ESP32 with connected sensors.
2. **LoRa integration** — Replace MQTT direct publish with ESP32 LoRa → gateway → cloud pipeline.
3. **Multi-unit support** — Extend to a team dashboard tracking multiple firefighters simultaneously.
4. **GPS tracking** — Add location coordinates to the telemetry payload and display on a floor plan.
5. **Machine learning** — Train an anomaly detection model to predict health deterioration before threshold breaches.

---

## License

Academic final-year engineering project. All code is original work unless otherwise cited.
