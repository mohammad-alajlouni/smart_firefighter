# Node-RED Dashboard — Setup Guide

This guide explains how to install Node-RED, import the dashboard flow,
and view the live Smart Firefighter telemetry dashboard.

---

## Prerequisites

| Requirement | Version |
|---|---|
| Node.js | 18 LTS or newer |
| npm | bundled with Node.js |
| Node-RED | 3.x |

---

## Step 1 — Install Node-RED

```bash
npm install -g --unsafe-perm node-red
```

Verify the installation:

```bash
node-red --version
```

---

## Step 2 — Install the Dashboard Palette

Start Node-RED once to create its user directory, then stop it (Ctrl+C).

```bash
node-red
```

Install the official dashboard palette:

```bash
cd %USERPROFILE%\.node-red
npm install node-red-dashboard
```

If you need the table widget used in the event log panel:

```bash
npm install node-red-node-ui-table
```

Restart Node-RED after installing palettes.

---

## Step 3 — Import the Flow

1. Open a browser and navigate to **http://localhost:1880**
2. Click the **hamburger menu** (≡) in the top-right corner
3. Select **Import**
4. Click **select a file to import**
5. Browse to and select:

   ```
   node-red/flows_smart_firefighter.json
   ```

6. Click **Import**
7. Click the **Deploy** button (red button, top-right)

---

## Step 4 — Open the Dashboard

Navigate to:

```
http://localhost:1880/ui
```

The **Firefighter Dashboard** tab will appear.

---

## Dashboard Panels

| Panel | Contents |
|---|---|
| **Firefighter Info** | Firefighter ID, last updated timestamp |
| **Status & Alerts** | Colour-coded status indicator, alert message text |
| **Vital Signs** | Heart rate gauge (BPM), body temperature gauge (°C) |
| **Environmental Sensors** | CO level gauge (ppm), fall detection status |
| **Sensor Trend Charts** | Live line charts — heart rate, body temperature, CO level |
| **Event Log** | Table of all WARNING / DANGER / FALL_DETECTED events |

---

## Status Indicator Colours

| Status | Colour |
|---|---|
| OK | Green `#00b500` |
| WARNING | Amber `#e6a817` |
| DANGER | Red `#ca3838` |
| FALL_DETECTED | Purple `#8b008b` |

---

## Changing the MQTT Broker

1. Double-click the **"Subscribe: Telemetry"** MQTT-in node in the editor
2. Click the pencil icon next to the broker field
3. Update the host / port to match your `.env` settings
4. Click **Update → Done → Deploy**

---

## Troubleshooting

| Problem | Solution |
|---|---|
| No data on dashboard | Ensure `simulated_wearable.py` is running and the MQTT topic matches |
| `ui_table` node missing | Run `npm install node-red-node-ui-table` in `%USERPROFILE%\.node-red` |
| Dashboard at wrong URL | Check `http://localhost:1880/ui` — ensure Node-RED started successfully |
| Connection refused | Verify Node-RED is running and port 1880 is not blocked by firewall |

---

## MQTT Communication Note

The Node-RED flow subscribes to:

```
smart_firefighter/ff01/telemetry
smart_firefighter/ff01/alerts
```

These topics are served by a public MQTT broker (`broker.emqx.io:1883`) which
**emulates the logical data flow of a LoRa network**. Node-RED does not test
real LoRa range, signal strength, or radio propagation characteristics.
