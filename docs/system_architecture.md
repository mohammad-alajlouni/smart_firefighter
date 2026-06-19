# System Architecture

## Overview

The Smart Firefighter Wearable System is composed of six logical modules that
form an end-to-end pipeline from raw sensor data to command-side analysis.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     WEARABLE UNIT (on firefighter)                  │
│                                                                     │
│  ┌──────────────┐   ┌──────────────────┐   ┌─────────────────────┐ │
│  │ Sensor Module│──▶│ Processing Module│──▶│   Alert Module      │ │
│  │  HR / Temp   │   │ Threshold logic  │   │ LED / Buzzer / OLED │ │
│  │  CO / Fall   │   │ Status classify  │   │                     │ │
│  └──────────────┘   └────────┬─────────┘   └─────────────────────┘ │
│                              │                                      │
│                   ┌──────────▼──────────┐                           │
│                   │ Communication Module│                           │
│                   │  MQTT publish (JSON)│                           │
│                   │  [emulates LoRa TX] │                           │
│                   └──────────┬──────────┘                           │
└──────────────────────────────┼──────────────────────────────────────┘
                               │ MQTT over TCP/IP
                               │ (public broker: broker.emqx.io:1883)
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      COMMAND SIDE                                    │
│                                                                      │
│  ┌──────────────────┐        ┌──────────────────────────────────┐   │
│  │  Dashboard Module│        │   Logger / Analyzer Module       │   │
│  │  Node-RED UI     │        │   Python logger_analyzer.py      │   │
│  │  Gauges / Charts │        │   CSV logs / Summary report      │   │
│  │  Status / Alerts │        │   Matplotlib charts              │   │
│  └──────────────────┘        └──────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Module Descriptions

### 1. Sensor Module

**Responsibility:** Produce raw sensor readings at a configurable interval.

In the simulation, this is implemented by `utils.py` scenario generators.
In real hardware, this would be hardware driver calls to physical sensors:

| Parameter | Simulated Source | Real-World Sensor Example |
|---|---|---|
| Heart Rate (BPM) | Random values per scenario | MAX30102 optical sensor |
| Body Temperature (°C) | Random values per scenario | MLX90614 IR thermometer |
| CO Level (ppm) | Random values per scenario | MQ-7 or MQ-9 gas sensor |
| Fall Detection (bool) | Random / scenario | MPU-6050 accelerometer + threshold |

**Outputs:** Raw numeric readings as a Python dictionary (simulation) or
struct (firmware).

---

### 2. Processing Module

**Responsibility:** Classify the current situation and construct the telemetry
payload.

Implemented in:
- `utils.py → classify_status()` and `generate_alert_message()`
- `simulated_wearable.py → build_payload()`
- `sketch.ino → classifyStatus()` (firmware)

**Classification logic (priority order):**

```
if fall_detected          → FALL_DETECTED
elif any value in DANGER  → DANGER
elif any value in WARNING → WARNING
else                      → OK
```

**Outputs:** A status string and a structured JSON payload.

---

### 3. Alert Module

**Responsibility:** Provide immediate local feedback to the firefighter and
nearby personnel, independent of any network connection.

In the simulation:
- `utils.py → print_local_alert()` prints colour-coded terminal output

In firmware:
- Green/Yellow/Red LEDs indicate status
- Buzzer pattern changes with severity (off / slow-beep / fast-beep)
- OLED display shows numeric readings and status text

| Status | LED | Buzzer | OLED Text |
|---|---|---|---|
| OK | Green ON | OFF | STATUS OK |
| WARNING | Yellow ON | Slow beep (800 ms) | WARNING |
| DANGER | Red ON | Fast beep (250 ms) | DANGER |
| FALL_DETECTED | Red ON | Fast beep (250 ms) | FALL DETECTED |

---

### 4. Communication Module

**Responsibility:** Transmit the telemetry payload to the command side.

In the simulation: `paho-mqtt` Python library publishes JSON to a public
MQTT broker.

In firmware: `PubSubClient` Arduino library publishes JSON over WiFi to
the same MQTT broker.

> **Design note:** MQTT is used here to **emulate the logical data flow** of
> a LoRa communication link. In a production deployment, the ESP32 would
> transmit via LoRa radio to a LoRa gateway, which would forward data to
> a cloud MQTT broker. The JSON payload format, topic structure, and QoS
> settings are designed to be directly compatible with such a deployment.

**Topics:**

| Topic | Purpose |
|---|---|
| `smart_firefighter/ff01/telemetry` | Full sensor readings (published every interval) |
| `smart_firefighter/ff01/alerts` | Alert-only payloads (published when status ≠ OK) |

---

### 5. Dashboard Module

**Responsibility:** Provide real-time visual monitoring for command personnel.

Implemented as a Node-RED flow (`node-red/flows_smart_firefighter.json`)
using the `node-red-dashboard` palette.

**Components:**

| Widget | Type | Data Shown |
|---|---|---|
| Firefighter ID | Text | Unique device identifier |
| Last Updated | Text | ISO 8601 timestamp of latest reading |
| Status Indicator | Colour template | OK / WARNING / DANGER / FALL_DETECTED |
| Alert Message | Text | Human-readable alert description |
| Heart Rate Gauge | Gauge (0–200 BPM) | Current heart rate with threshold markers |
| Body Temp Gauge | Gauge (35–42 °C) | Current body temperature |
| CO Level Gauge | Gauge (0–500 ppm) | Current carbon monoxide concentration |
| Fall Detection | Text | Normal / FALL DETECTED |
| Heart Rate Chart | Line chart | Time-series history |
| Body Temp Chart | Line chart | Time-series history |
| CO Level Chart | Line chart | Time-series history |
| Event Log Table | Table | All non-OK events with timestamp and message |

---

### 6. Logger / Analyzer Module

**Responsibility:** Persist all telemetry data and provide post-session analysis.

Implemented in `python/logger_analyzer.py`.

**Features:**
- Subscribes to the MQTT telemetry topic
- Writes each reading to a timestamped CSV file in `data/logs/`
- Maintains in-memory statistics (totals, peaks, event counts)
- On exit: prints a session summary report and saves it to `data/reports/`
- Generates four matplotlib charts saved to `data/charts/`:
  - Heart rate over time
  - Body temperature over time
  - CO level over time
  - Alert status timeline (colour-coded scatter plot)
