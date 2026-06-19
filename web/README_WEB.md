# Web Dashboard — Setup and Usage Guide

The web dashboard provides a browser-based interface for the Smart Firefighter
Wearable System. It replaces the need to manage multiple terminal windows while
keeping the existing CLI scripts fully functional.

---

## What the Web Dashboard Does

- Starts and stops the firefighter simulation from the browser
- Selects and switches simulation scenarios in real time
- Displays live telemetry via WebSocket (heart rate, temperature, CO, fall status)
- Simulates the wearable's local alert output (LED, buzzer, OLED)
- Renders real-time Chart.js line charts for all three sensor streams
- Shows a live event log table updated as readings arrive
- Provides a filterable log viewer (by status, firefighter ID, limit)
- Generates and exports session summary reports
- Exports the latest CSV log for download

---

## Installation

From the project root folder:

```bash
pip install -r requirements.txt
```

---

## How to Run

From the **project root** folder (not inside `web/`):

```bash
uvicorn web.main:app --reload
```

Then open a browser at:

```
http://127.0.0.1:8000
```

---

## Available Pages

| URL | Page |
|---|---|
| `http://127.0.0.1:8000/` | Main dashboard (live telemetry, charts, controls) |
| `http://127.0.0.1:8000/logs` | Log viewer with filters |
| `http://127.0.0.1:8000/reports` | Summary statistics and export |

---

## API Endpoints

### Simulation Control

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/status` | Current simulation state and statistics |
| POST | `/api/simulation/start` | Start simulation with `{"scenario": "normal"}` |
| POST | `/api/simulation/stop` | Stop simulation |
| POST | `/api/simulation/set-scenario` | Change scenario while running |
| POST | `/api/simulation/publish-once` | Publish a single reading manually |

### Logs

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/logs` | Returns log records as JSON |
| GET | `/api/logs?limit=100` | Limit number of records returned |
| GET | `/api/logs?status=DANGER` | Filter by status |
| GET | `/api/logs?firefighter_id=FF-01` | Filter by firefighter |

### Reports

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/report/summary` | Session statistics as JSON |
| GET | `/api/report/export-csv` | Download latest CSV log |
| GET | `/api/report/export-summary` | Save TXT report to data/reports/ |

---

## WebSocket Endpoint

```
ws://127.0.0.1:8000/ws/telemetry
```

The browser connects automatically. Every telemetry reading is pushed as JSON:

```json
{
  "firefighter_id": "FF-01",
  "heart_rate": 128.0,
  "body_temp": 39.2,
  "co_level": 180.0,
  "fall_detected": false,
  "status": "WARNING",
  "alert_message": "High body temperature (39.2 deg C)",
  "timestamp": "2026-01-01T10:30:00Z"
}
```

---

## How to Start and Stop the Simulation

**From the browser:**
1. Select a scenario from the dropdown
2. Click **Start Simulation**
3. Live readings appear on cards, charts, and the log table
4. Click **Stop** to halt the simulation

**Change scenario while running:**
Select a different scenario from the dropdown — the next reading will use it.

**Publish Once:**
Click **Publish Once** to generate and broadcast a single reading without
starting the continuous loop.

---

## How to View Logs and Reports

**Logs page** (`/logs`):
- Select a status filter (OK / WARNING / DANGER / FALL_DETECTED)
- Enter a firefighter ID to narrow results
- Click **Refresh** to reload
- Click **Export CSV** to download the latest log file

**Reports page** (`/reports`):
- Statistics are loaded automatically from all CSV files in `data/logs/`
- Click **Refresh** to recalculate
- Click **Save Report File** to write a `.txt` summary to `data/reports/`
- Click **Export CSV** to download the latest log

---

## Using the CLI Scripts Alongside the Web Dashboard

The web dashboard and the CLI scripts can run simultaneously:

- **Web publishes, CLI receives:** Start the web simulation and run
  `py python/logger_analyzer.py` to log to a second CSV.

- **CLI publishes, web receives:** Run `py python/simulated_wearable.py --scenario high_co`
  and the web dashboard will display readings via its MQTT subscriber.

---

## Troubleshooting MQTT Connection Issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| MQTT badge shows "No MQTT" | Public broker unreachable | Check internet connection; try `broker.hivemq.com` in `.env` |
| Dashboard shows data but MQTT badge is red | Simulation publishes directly to WS; MQTT failed | Data still displays; restart to retry MQTT |
| No data appears after Start | WebSocket not connected | Check browser console for WS errors; reload page |
| "No CSV log file found" on export | Simulation not yet started | Start simulation and wait for at least one reading |

**Change the MQTT broker** by editing `.env`:
```
MQTT_BROKER_HOST=broker.hivemq.com
MQTT_BROKER_PORT=1883
```

---

## Notes

- Data directories (`data/logs/`, `data/reports/`, `data/charts/`) are created
  automatically on first run.
- Each web simulation session creates a new CSV file named
  `web_telemetry_YYYYMMDD_HHMMSS.csv`.
- The `--reload` flag in the uvicorn command restarts the server automatically
  when source files change.
