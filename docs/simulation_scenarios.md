# Simulation Scenarios

This document describes each test scenario, the sensor values generated,
the expected system behaviour, and the expected output at each layer of
the architecture.

---

## Scenario 1 — Normal Condition

**Command:** `python python/simulated_wearable.py --scenario normal`

**Purpose:** Verify baseline operation. All sensors within safe thresholds.
No alerts should be raised.

### Input Values

| Parameter | Range |
|---|---|
| Heart Rate | 72 – 95 BPM |
| Body Temperature | 36.5 – 37.5 °C |
| CO Level | 5 – 30 ppm |
| Fall Detected | False |

### Expected Status: `OK`

### Expected Local Alert

```
LED: GREEN    BUZZER: OFF    OLED: STATUS OK
```

### Expected Dashboard Behaviour

- Status indicator: green, text "OK"
- All gauges in the green zone
- Alert message: "All parameters within normal range"
- No entries added to the event log table

### Expected Log Output

```
[2026-01-01T10:00:00Z] FF-01  HR=  82.0 BPM  Temp= 37.1°C  CO=  18.0 ppm  Fall=  no  ► OK
```

---

## Scenario 2 — High Temperature

**Command:** `python python/simulated_wearable.py --scenario high_temperature`

**Purpose:** Simulate a firefighter developing hyperthermia. Body temperature
rises above warning and danger thresholds.

### Input Values

| Parameter | Range |
|---|---|
| Heart Rate | 100 – 118 BPM (mildly elevated due to heat) |
| Body Temperature | 39.0 – 41.0 °C |
| CO Level | 10 – 40 ppm |
| Fall Detected | False |

### Expected Status: `WARNING` → `DANGER`

At 39.0–39.5 °C: WARNING  
Above 39.5 °C: DANGER

### Expected Local Alert

```
WARNING: LED: YELLOW   BUZZER: SLOW BEEP   OLED: WARNING
DANGER:  LED: RED      BUZZER: FAST BEEP   OLED: DANGER
```

### Expected Dashboard Behaviour

- Status indicator: amber (WARNING) or red (DANGER)
- Body temperature gauge needle in the amber/red zone
- Alert message: "High body temperature (39.2°C)" or "Critical body temperature (40.1°C)"
- Events logged to the event log table

### Expected Log Output

```
[2026-01-01T10:01:00Z] FF-01  HR= 107.0 BPM  Temp= 39.8°C  CO=  22.0 ppm  Fall=  no  ► DANGER
   Alert: Critical body temperature (39.8°C)
```

---

## Scenario 3 — High CO Level

**Command:** `python python/simulated_wearable.py --scenario high_co`

**Purpose:** Simulate accumulation of carbon monoxide in the firefighter's
environment, representing a risk of poisoning.

### Input Values

| Parameter | Range |
|---|---|
| Heart Rate | 85 – 115 BPM |
| Body Temperature | 37.0 – 38.5 °C |
| CO Level | 150 – 400 ppm |
| Fall Detected | False |

### Expected Status: `WARNING` → `DANGER`

At 150–200 ppm: WARNING  
Above 200 ppm: DANGER

### Expected Local Alert

```
DANGER: LED: RED   BUZZER: FAST BEEP   OLED: DANGER
```

### Expected Dashboard Behaviour

- CO level gauge needle in the amber/red zone
- Alert message: "Dangerous CO level (320 ppm)"
- Status indicator: red

### Expected Log Output

```
[2026-01-01T10:02:00Z] FF-01  HR=  98.0 BPM  Temp= 37.9°C  CO= 320.0 ppm  Fall=  no  ► DANGER
   Alert: Dangerous CO level (320.0 ppm)
```

---

## Scenario 4 — High Heart Rate

**Command:** `python python/simulated_wearable.py --scenario high_heart_rate`

**Purpose:** Simulate a firefighter under extreme physical exertion, with
heart rate elevated to dangerous levels.

### Input Values

| Parameter | Range |
|---|---|
| Heart Rate | 135 – 180 BPM |
| Body Temperature | 37.5 – 39.0 °C |
| CO Level | 10 – 45 ppm |
| Fall Detected | False |

### Expected Status: `DANGER`

Heart rate above 130 BPM → DANGER

### Expected Local Alert

```
LED: RED   BUZZER: FAST BEEP   OLED: DANGER
```

### Expected Dashboard Behaviour

- Heart rate gauge needle deep in the red zone
- Status indicator: red
- Alert message: "Critical heart rate (158 BPM)"

### Expected Log Output

```
[2026-01-01T10:03:00Z] FF-01  HR= 158.0 BPM  Temp= 38.3°C  CO=  27.0 ppm  Fall=  no  ► DANGER
   Alert: Critical heart rate (158.0 BPM)
```

---

## Scenario 5 — Fall Detection

**Command:** `python python/simulated_wearable.py --scenario fall_detection`

**Purpose:** Simulate a firefighter losing consciousness or being incapacitated
by a structural collapse.

### Input Values

| Parameter | Range |
|---|---|
| Heart Rate | 60 – 100 BPM (normal pre-fall) |
| Body Temperature | 36.0 – 37.5 °C |
| CO Level | 5 – 25 ppm |
| Fall Detected | **True** |

### Expected Status: `FALL_DETECTED`

Fall detection flag overrides all other sensors — FALL_DETECTED takes
the highest priority in the classification logic.

### Expected Local Alert

```
LED: RED   BUZZER: FAST BEEP   OLED: FALL DETECTED
```

### Expected Dashboard Behaviour

- Status indicator: purple, text "FALL_DETECTED"
- Fall detection text widget: "⚠ FALL DETECTED"
- Alert message: "Fall detected — immediate assistance required"
- Event logged to the table immediately

### Expected Log Output

```
[2026-01-01T10:04:00Z] FF-01  HR=  78.0 BPM  Temp= 37.0°C  CO=  15.0 ppm  Fall= YES  ► FALL_DETECTED
   Alert: Fall detected — immediate assistance required
```

---

## Scenario 6 — Multiple Hazards

**Command:** `python python/simulated_wearable.py --scenario multiple_hazards`

**Purpose:** Simulate the worst-case scenario where a firefighter faces
simultaneous extreme heat, toxic gas, and cardiac stress.

### Input Values

| Parameter | Range |
|---|---|
| Heart Rate | 140 – 185 BPM |
| Body Temperature | 39.8 – 41.5 °C |
| CO Level | 220 – 450 ppm |
| Fall Detected | 50% chance True |

### Expected Status: `DANGER` or `FALL_DETECTED`

All parameters exceed danger thresholds. If fall_detected is True, the
status is FALL_DETECTED (highest priority).

### Expected Local Alert

```
LED: RED   BUZZER: FAST BEEP   OLED: DANGER  (or FALL DETECTED)
```

### Expected Dashboard Behaviour

- All three gauges in the red zone simultaneously
- Status indicator: red
- Alert message lists multiple hazards:
  "Critical heart rate (165 BPM); Critical body temperature (40.5°C); Dangerous CO level (380 ppm)"
- Multiple rapid entries in the event log

### Expected Log Output

```
[2026-01-01T10:05:00Z] FF-01  HR= 165.0 BPM  Temp= 40.5°C  CO= 380.0 ppm  Fall=  no  ► DANGER
   Alert: Critical heart rate (165.0 BPM); Critical body temperature (40.5°C); Dangerous CO level (380.0 ppm)
```

---

## Dry-Run Mode (Any Scenario)

**Command:** `python python/simulated_wearable.py --scenario high_co --dry-run`

No MQTT connection is made. All JSON payloads are printed to the terminal
only. Useful for verifying payload format and threshold logic without a
network connection.
