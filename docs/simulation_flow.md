# Simulation Flow — Smart Firefighter Wearable System

## Overview

Each simulation cycle produces one telemetry reading. The cycle consists of
13 sequential steps, visible in the Simulation Lab page's Process Flow panel.

---

## Step-by-Step Runtime Flow

### Step 1 — Read Heart Rate (MAX30102)

**Component:** MAX30102 pulse oximeter / heart rate sensor  
**Interface:** I2C (SDA=GPIO21, SCL=GPIO22, address 0x57)  
**Simulation:** `generate_scenario_readings(scenario)` in `python/utils.py`  
**Range by scenario:**

| Scenario | Heart Rate Range |
|---|---|
| normal | 72–95 BPM |
| high_heart_rate | 135–180 BPM |
| high_temperature | 100–118 BPM |
| fall_detection | 60–100 BPM |
| multiple_hazards | 140–185 BPM |

On real hardware: `particleSensor.getHeartRate()` from SparkFun MAX3010x library.

---

### Step 2 — Read Body Temperature (DS18B20)

**Component:** DS18B20 digital temperature sensor  
**Interface:** 1-Wire (GPIO4, with 4.7 kΩ pull-up to 3V3)  
**Simulation:** `_high_temperature()` or other scenario functions in `utils.py`  

On real hardware: `sensors.getTempCByIndex(0)` from DallasTemperature library.

---

### Step 3 — Read CO Level (MQ-7)

**Component:** MQ-7 carbon monoxide gas sensor  
**Interface:** Analog output → GPIO34 (ADC)  
**Simulation:** Random float in range appropriate to scenario

On real hardware: `analogRead(PIN_MQ7_ADC)`, then convert using:
```
voltage = (raw / 4095.0) * 3.3;
RS = ((3.3 - voltage) / voltage) * RL;   // RL = load resistance
ppm = A * pow(RS / R0, B);               // from datasheet curve
```

---

### Step 4 — Read IMU / Fall State (MPU6050)

**Component:** MPU6050 6-axis IMU  
**Interface:** I2C (GPIO21/22, address 0x68)  
**Fall detection logic:** Monitor |total acceleration| over a time window. A sudden spike followed by near-zero acceleration indicates a fall event.  
**Simulation:** `random.choice([True, False])` for `multiple_hazards`, always `True` for `fall_detection` scenario.

---

### Step 5 — ESP32 Assembles Readings

All four raw sensor values are combined into a `readings` dictionary:
```python
readings = {
    "heart_rate":    <float>,
    "body_temp":     <float>,
    "co_level":      <float>,
    "fall_detected": <bool>,
}
```

---

### Step 6 — Classify Status

`classify_status(readings)` in `python/utils.py` applies this priority logic:

```
if fall_detected       → FALL_DETECTED   (highest priority)
elif any param > warn  → DANGER
elif any param >= ok   → WARNING
else                   → OK
```

**Threshold table:**

| Parameter | OK boundary | WARNING boundary | DANGER boundary |
|---|---|---|---|
| Heart Rate | < 110 BPM | 110–130 BPM | > 130 BPM |
| Body Temp | < 38.0 °C | 38.0–39.5 °C | > 39.5 °C |
| CO Level | < 50 ppm | 50–200 ppm | > 200 ppm |
| Fall | no | — | FALL_DETECTED immediately |

Thresholds are defined in `python/config.py` and mirrored in `wokwi/sketch.ino`.

---

### Step 7 — Update OLED Display

The SSD1306 OLED (I2C, GPIO21/22, addr 0x3C) is updated with:
- Firefighter ID
- Heart rate, body temperature, CO level, fall state
- Current status string

In the web simulation, the SVG OLED element and the alert panel OLED mockup
both update to reflect the current status text and colour.

---

### Step 8 — Set LEDs and Buzzer

| Status | GPIO27 (Green) | GPIO26 (Yellow) | GPIO25 (Red) | GPIO18 (Buzzer) |
|---|---|---|---|---|
| OK | HIGH | LOW | LOW | OFF |
| WARNING | LOW | HIGH | LOW | SLOW BEEP (800 ms) |
| DANGER | LOW | LOW | HIGH | FAST BEEP (250 ms) |
| FALL_DETECTED | LOW | LOW | HIGH | FAST BEEP (250 ms) |

---

### Step 9 — Publish MQTT Payload

The JSON payload is serialised and published to the MQTT broker:

**Broker:** `broker.emqx.io:1883`  
**Topic:** `smart_firefighter/ff01/telemetry`  
**QoS:** 1  
**Retain:** False

```json
{
  "firefighter_id": "FF-01",
  "heart_rate": 126.4,
  "body_temp": 39.2,
  "co_level": 180.0,
  "fall_detected": false,
  "status": "WARNING",
  "alert_message": "Elevated heart rate (126.4 BPM); High body temperature (39.2 C)",
  "timestamp": "2026-01-01T10:30:00Z"
}
```

If `status != "OK"`, an additional alert message is also published to:  
`smart_firefighter/ff01/alerts`

**LoRa emulation note:** In a production LoRaWAN deployment, the ESP32 would
use a LoRa radio module (e.g., SX1276/SX1278) to transmit the payload to a
LoRa gateway. The gateway would forward via HTTPS or MQTT to the cloud. This
simulation collapses that path to a direct MQTT publish while preserving the
identical JSON format and topic hierarchy.

---

### Step 10 — FastAPI Receives Telemetry

`SimulationManager._handle_payload()` in `web/simulation_manager.py`:
- Stores the payload in `last_payload` and `records`
- Increments session counters
- Writes to the CSV log file
- Calls `asyncio.run_coroutine_threadsafe(broadcast(payload), loop)`

`MQTTService` in `web/mqtt_service.py` also subscribes to the broker topic
and forwards any externally-published readings (e.g. from the CLI script).

---

### Step 11 — Dashboard WebSocket Broadcast

The `broadcast()` coroutine in `web/main.py` sends the JSON payload to every
connected WebSocket client (`/ws/telemetry`). The browser's `simulation.js`
receives it and updates:
- SVG circuit component highlights and live-value text nodes
- Component status cards (bottom-left panel)
- Alert output panel (OLED, LEDs, Buzzer)
- Communication flow animation
- JSON payload display
- Process flow step highlighting

---

### Step 12 — Logger Writes CSV Record

`SimulationManager._write_csv()` appends a row to:
```
data/logs/web_telemetry_YYYYMMDD_HHMMSS.csv
```

Columns: `timestamp, firefighter_id, heart_rate, body_temp, co_level, fall_detected, status, alert_message`

The CLI `python/logger_analyzer.py` subscribes to MQTT independently and
writes its own separate CSV (`data/logs/telemetry_*.csv`).

---

### Step 13 — Report Counters Updated

Session-level counters maintained by `SimulationManager`:
- `total_readings`
- `warning_count`
- `danger_count`
- `fall_count`

These are exposed via `GET /api/status` and displayed in the control bar.
The `/api/report/summary` endpoint combines in-memory records with any
existing CSV records for a full session summary.

---

## Sequence Diagram

```
Browser (simulation.js)
    │
    │ POST /api/simulation/start
    ▼
SimulationManager._run()  [background thread]
    │ generate_scenario_readings(scenario)  ← utils.py
    │ classify_status(readings)             ← utils.py
    │ generate_alert_message(...)           ← utils.py
    │
    │── _write_csv(payload)                 → data/logs/*.csv
    │── _mqtt_publish(payload)              → broker.emqx.io
    │── broadcast(payload)                  → asyncio loop
    │
    ▼
FastAPI WebSocket (/ws/telemetry)
    │── send_text(json)  →  Browser WebSocket
    │
    ▼
simulation.js: onPayloadReceived(payload)
    │── updateComponentCards(p)
    │── updateAlertPanel(p)
    │── updateCommunicationPanel(p)
    │── updateJsonDisplay(p)
    │── updateCircuitState(p)
    └── startStepCycle(p)  →  step-by-step animation
```

---

## How Sensor Generation Works (Software)

`python/utils.py` contains scenario generator functions that return raw readings:

```python
def _high_co() -> dict:
    return {
        "heart_rate":    round(random.uniform(85, 115), 1),
        "body_temp":     round(random.uniform(37.0, 38.5), 1),
        "co_level":      round(random.uniform(150, 400), 1),
        "fall_detected": False,
    }
```

Each reading is independently sampled within the scenario's defined range,
producing realistic variation within each cycle. No physical sensor noise,
drift, warm-up effects, or ADC quantisation error are modelled.

---

## How Alert Logic Works

Priority order (highest to lowest):

1. `fall_detected = True` → always `FALL_DETECTED` regardless of other values
2. Any value above the DANGER threshold → `DANGER`
3. Any value at or above the WARNING threshold → `WARNING`
4. All values below WARNING threshold → `OK`

This mirrors the logic in the ESP32 sketch (`classifyStatus()`) and
ensures the web simulation and hardware produce identical classifications.
