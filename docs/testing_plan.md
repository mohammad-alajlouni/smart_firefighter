# Testing Plan

## Overview

This testing plan covers verification of the Smart Firefighter Wearable
System simulation at four levels: unit, integration, system, and acceptance.
All tests are executable on a single laptop without physical hardware.

---

## 1. Unit Testing

Unit tests verify individual functions in isolation, without MQTT or file I/O.

### 1.1 Status Classification (`utils.py → classify_status`)

| Test ID | Input | Expected Status |
|---|---|---|
| UT-01 | HR=80, Temp=37.0, CO=20, Fall=False | OK |
| UT-02 | HR=115, Temp=37.0, CO=20, Fall=False | WARNING |
| UT-03 | HR=135, Temp=37.0, CO=20, False | DANGER |
| UT-04 | HR=80, Temp=38.5, CO=20, False | WARNING |
| UT-05 | HR=80, Temp=40.0, CO=20, False | DANGER |
| UT-06 | HR=80, Temp=37.0, CO=100, False | WARNING |
| UT-07 | HR=80, Temp=37.0, CO=250, False | DANGER |
| UT-08 | HR=80, Temp=37.0, CO=20, Fall=True | FALL_DETECTED |
| UT-09 | HR=160, Temp=41.0, CO=400, Fall=True | FALL_DETECTED (priority) |

**How to run:**

```bash
python -c "
from python.utils import classify_status
tests = [
    ({'heart_rate':80,'body_temp':37.0,'co_level':20,'fall_detected':False}, 'OK'),
    ({'heart_rate':115,'body_temp':37.0,'co_level':20,'fall_detected':False}, 'WARNING'),
    ({'heart_rate':135,'body_temp':37.0,'co_level':20,'fall_detected':False}, 'DANGER'),
    ({'heart_rate':80,'body_temp':40.0,'co_level':20,'fall_detected':False}, 'DANGER'),
    ({'heart_rate':80,'body_temp':37.0,'co_level':250,'fall_detected':False}, 'DANGER'),
    ({'heart_rate':80,'body_temp':37.0,'co_level':20,'fall_detected':True}, 'FALL_DETECTED'),
]
for readings, expected in tests:
    result = classify_status(readings)
    status = 'PASS' if result == expected else 'FAIL'
    print(f'[{status}] Expected={expected}, Got={result}')
"
```

### 1.2 Alert Message Generation (`utils.py → generate_alert_message`)

| Test ID | Status | Expected Output Contains |
|---|---|---|
| UT-10 | OK | "normal range" |
| UT-11 | FALL_DETECTED | "Fall detected" |
| UT-12 | DANGER (high CO) | "CO level" |
| UT-13 | WARNING (high temp) | "body temperature" |

### 1.3 Payload Construction (`simulated_wearable.py → build_payload`)

Verify the JSON payload contains all required fields:
- `firefighter_id` (string)
- `heart_rate` (number)
- `body_temp` (number)
- `co_level` (number)
- `fall_detected` (boolean)
- `status` (string, one of OK / WARNING / DANGER / FALL_DETECTED)
- `alert_message` (string)
- `timestamp` (ISO 8601 format string)

### 1.4 Dry-Run Mode

```bash
python python/simulated_wearable.py --scenario normal --dry-run --count 3
```

**Expected:** 3 JSON payloads printed. No MQTT connection attempted. Script exits cleanly.

---

## 2. Integration Testing

Integration tests verify that two or more components work together correctly.

### 2.1 Publisher → MQTT Broker

**Precondition:** Internet connection available.

```bash
python python/simulated_wearable.py --scenario normal --count 5 --interval 1
```

**Expected:**
- `[MQTT] Connected successfully` message displayed
- 5 payloads published and confirmed
- Script exits after 5 readings

### 2.2 Logger → MQTT Broker → CSV File

**Steps:**
1. Start logger: `python python/logger_analyzer.py`
2. In a second terminal: `python python/simulated_wearable.py --scenario normal --count 10`
3. Stop logger with Ctrl+C

**Expected:**
- Logger receives and prints 10 readings
- CSV file created in `data/logs/` with 10 data rows and header
- Session summary printed showing total=10, warning=0, danger=0

### 2.3 Alert Topic Propagation

```bash
python python/simulated_wearable.py --scenario high_co --count 5
```

**Expected:** Alert payloads published to `smart_firefighter/ff01/alerts` for
each DANGER reading. Verify using an MQTT client such as MQTT Explorer or by
adding a second subscriber in the logger.

---

## 3. System Testing

System tests verify the complete end-to-end pipeline including Node-RED.

### 3.1 Full Pipeline — Normal Scenario

**Steps:**
1. Start Node-RED and import the flow
2. Open dashboard at `http://localhost:1880/ui`
3. Start logger: `python python/logger_analyzer.py`
4. Start wearable: `python python/simulated_wearable.py --scenario normal`

**Expected:**
- Dashboard gauges update every 2 seconds
- All gauges show green zone values
- Status indicator shows green "OK"
- Logger CSV grows in real time

### 3.2 Full Pipeline — Hazard Escalation

**Steps:**
1. Run normal scenario for 30 seconds
2. Switch to `--scenario multiple_hazards`

**Expected:**
- Dashboard status instantly changes to red "DANGER"
- Gauges move to red zones
- Alert message updates with multiple hazard descriptions
- Events appear in the Node-RED event log table
- Logger counts reflect WARNING/DANGER events in summary

### 3.3 Scenario Switching

Run each scenario in sequence and verify the status classification changes
correctly between scenarios:

```bash
python python/simulated_wearable.py --scenario normal           --count 5
python python/simulated_wearable.py --scenario high_temperature --count 5
python python/simulated_wearable.py --scenario high_co          --count 5
python python/simulated_wearable.py --scenario high_heart_rate  --count 5
python python/simulated_wearable.py --scenario fall_detection   --count 5
python python/simulated_wearable.py --scenario multiple_hazards --count 5
```

---

## 4. Acceptance Testing

Acceptance tests verify that the system meets the stated project requirements.

| Test ID | Requirement | Verification Method | Pass Criterion |
|---|---|---|---|
| AT-01 | Wearable simulates 7 sensor/data fields | Inspect JSON payload output | All 7 fields present in every payload |
| AT-02 | Four status levels implemented | Run all 6 scenarios | Each status observed at least once |
| AT-03 | Configurable thresholds | Change `.env` values, re-run | Status changes reflect new thresholds |
| AT-04 | MQTT publish works | Run publisher + MQTT Explorer | Messages appear on broker |
| AT-05 | MQTT subscribe + CSV logging | Run logger for 60 s | CSV file exists with correct columns |
| AT-06 | Summary report generated | Stop logger | Report printed and saved to `data/reports/` |
| AT-07 | Charts generated | Stop logger | PNG file saved to `data/charts/` |
| AT-08 | Node-RED dashboard receives data | Full pipeline test | All widgets update in real time |
| AT-09 | All 6 scenarios runnable | Run each via CLI | No Python errors for any scenario |
| AT-10 | Dry-run mode works offline | `--dry-run` flag | JSON printed without MQTT connection |
| AT-11 | Local alert output correct | Observe terminal output | Correct LED/buzzer/OLED text per status |
| AT-12 | Folder structure correct | Inspect project directory | All specified folders and files present |
