#!/usr/bin/env python3
"""
logger_analyzer.py — Smart Firefighter MQTT Logger and Data Analyzer

Subscribes to the telemetry MQTT topic, logs all incoming readings to a
timestamped CSV file, and on exit produces a statistical summary report
plus optional matplotlib charts saved to data/charts/.

NOTE: MQTT is used to emulate the logical data-flow of LoRa communication.
It does not test real LoRa physical-layer properties.

Usage:
    python logger_analyzer.py
    python logger_analyzer.py --no-charts
    python logger_analyzer.py --topic smart_firefighter/ff01/telemetry
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from config import Config

# matplotlib is imported lazily so the script still runs if it is unavailable
try:
    import matplotlib
    matplotlib.use("Agg")   # non-interactive backend, safe on all platforms
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    _MPL_AVAILABLE = True
except ImportError:
    _MPL_AVAILABLE = False


# ─── Globals ─────────────────────────────────────────────────────────────────

_records: list[dict] = []          # in-memory copy of every received reading
_csv_path: Path | None = None
_csv_writer: csv.DictWriter | None = None
_csv_file = None

CSV_COLUMNS = [
    "timestamp",
    "firefighter_id",
    "heart_rate",
    "body_temp",
    "co_level",
    "fall_detected",
    "status",
    "alert_message",
]

_STATUS_COLORS = {
    "OK": "\033[92m",
    "WARNING": "\033[93m",
    "DANGER": "\033[91m",
    "FALL_DETECTED": "\033[95m",
}
_RESET = "\033[0m"


# ─── CSV Initialisation ───────────────────────────────────────────────────────

def _open_csv() -> None:
    global _csv_path, _csv_writer, _csv_file
    Config.ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    _csv_path = Config.LOGS_DIR / f"telemetry_{ts}.csv"
    _csv_file = open(_csv_path, "w", newline="", encoding="utf-8")
    _csv_writer = csv.DictWriter(_csv_file, fieldnames=CSV_COLUMNS)
    _csv_writer.writeheader()
    _csv_file.flush()
    print(f"[LOG] Writing to: {_csv_path}")


def _write_row(record: dict) -> None:
    if _csv_writer is None:
        return
    row = {col: record.get(col, "") for col in CSV_COLUMNS}
    _csv_writer.writerow(row)
    _csv_file.flush()


# ─── MQTT Callbacks ───────────────────────────────────────────────────────────

def _on_connect(client, userdata, connect_flags, reason_code, properties):
    if reason_code == 0:
        topic = userdata["topic"]
        print(f"[MQTT] Connected -> {Config.BROKER_HOST}:{Config.BROKER_PORT}")
        print(f"[MQTT] Subscribed to: {topic}\n")
        client.subscribe(topic, qos=1)
    else:
        print(f"[MQTT] Connection failed (reason={reason_code})", file=sys.stderr)


def _on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"[WARN] Malformed message ignored: {exc}")
        return

    _records.append(payload)
    _write_row(payload)

    status = payload.get("status", "OK")
    color = _STATUS_COLORS.get(status, "")
    ts = payload.get("timestamp", "?")
    ff_id = payload.get("firefighter_id", "?")

    print(
        f"{color}"
        f"[{ts}] {ff_id}  "
        f"HR={payload.get('heart_rate'):>5} BPM  "
        f"Temp={payload.get('body_temp'):>5}C  "
        f"CO={payload.get('co_level'):>6} ppm  "
        f"Fall={'YES' if payload.get('fall_detected') else ' no'}  "
        f">> {status}"
        f"{_RESET}"
    )
    if status != "OK":
        print(f"   Alert: {payload.get('alert_message', '')}")


def _on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    if reason_code != 0:
        print(f"\n[MQTT] Unexpected disconnection (rc={reason_code})", file=sys.stderr)


# ─── Summary Report ───────────────────────────────────────────────────────────

def _generate_report() -> None:
    if not _records:
        print("[REPORT] No data received.")
        return

    total = len(_records)
    warnings = sum(1 for r in _records if r.get("status") == "WARNING")
    dangers = sum(1 for r in _records if r.get("status") == "DANGER")
    falls = sum(1 for r in _records if r.get("status") == "FALL_DETECTED")
    hr_vals = [r["heart_rate"] for r in _records if "heart_rate" in r]
    temp_vals = [r["body_temp"] for r in _records if "body_temp" in r]
    co_vals = [r["co_level"] for r in _records if "co_level" in r]

    report_lines = [
        "=" * 60,
        "  SMART FIREFIGHTER WEARABLE — SESSION SUMMARY",
        "=" * 60,
        f"  Firefighter ID      : {_records[0].get('firefighter_id', '?')}",
        f"  Session start       : {_records[0].get('timestamp', '?')}",
        f"  Session end         : {_records[-1].get('timestamp', '?')}",
        f"  Total readings      : {total}",
        "",
        "  Status Breakdown:",
        f"    OK readings       : {total - warnings - dangers - falls}",
        f"    WARNING events    : {warnings}",
        f"    DANGER events     : {dangers}",
        f"    FALL events       : {falls}",
        "",
        "  Peak Values:",
        f"    Max heart rate    : {max(hr_vals):.1f} BPM" if hr_vals else "",
        f"    Max body temp     : {max(temp_vals):.1f} °C" if temp_vals else "",
        f"    Max CO level      : {max(co_vals):.1f} ppm" if co_vals else "",
        "=" * 60,
    ]
    report_text = "\n".join(line for line in report_lines if line is not None)
    print(f"\n{report_text}\n")

    # Save report to file
    Config.ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Config.REPORTS_DIR / f"report_{ts}.txt"
    report_path.write_text(report_text, encoding="utf-8")
    print(f"[REPORT] Saved to: {report_path}")


# ─── Chart Generation ─────────────────────────────────────────────────────────

def _generate_charts() -> None:
    if not _MPL_AVAILABLE:
        print("[CHARTS] matplotlib not available — skipping chart generation.")
        return
    if not _records:
        return

    Config.ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Parse timestamps
    import pandas as pd

    df = pd.DataFrame(_records)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])

    _STATUS_CHART_COLORS = {
        "OK": "green",
        "WARNING": "orange",
        "DANGER": "red",
        "FALL_DETECTED": "purple",
    }

    fig, axes = plt.subplots(4, 1, figsize=(12, 14), sharex=True)
    fig.suptitle(
        "Smart Firefighter Wearable — Session Analysis",
        fontsize=14,
        fontweight="bold",
    )

    # Heart Rate
    axes[0].plot(
        df["timestamp"], df["heart_rate"], color="#1f77b4", linewidth=1.5, marker="o", markersize=3
    )
    axes[0].axhline(Config.HR_OK_MAX, color="orange", linestyle="--", linewidth=0.8, label=f"Warning >{Config.HR_OK_MAX}")
    axes[0].axhline(Config.HR_WARNING_MAX, color="red", linestyle="--", linewidth=0.8, label=f"Danger >{Config.HR_WARNING_MAX}")
    axes[0].set_ylabel("Heart Rate (BPM)")
    axes[0].legend(fontsize=8)
    axes[0].set_title("Heart Rate Over Time")
    axes[0].grid(True, alpha=0.3)

    # Body Temperature
    axes[1].plot(
        df["timestamp"], df["body_temp"], color="#d62728", linewidth=1.5, marker="o", markersize=3
    )
    axes[1].axhline(Config.TEMP_OK_MAX, color="orange", linestyle="--", linewidth=0.8, label=f"Warning >{Config.TEMP_OK_MAX}°C")
    axes[1].axhline(Config.TEMP_WARNING_MAX, color="red", linestyle="--", linewidth=0.8, label=f"Danger >{Config.TEMP_WARNING_MAX}°C")
    axes[1].set_ylabel("Body Temp (°C)")
    axes[1].legend(fontsize=8)
    axes[1].set_title("Body Temperature Over Time")
    axes[1].grid(True, alpha=0.3)

    # CO Level
    axes[2].plot(
        df["timestamp"], df["co_level"], color="#ff7f0e", linewidth=1.5, marker="o", markersize=3
    )
    axes[2].axhline(Config.CO_OK_MAX, color="orange", linestyle="--", linewidth=0.8, label=f"Warning >{Config.CO_OK_MAX} ppm")
    axes[2].axhline(Config.CO_WARNING_MAX, color="red", linestyle="--", linewidth=0.8, label=f"Danger >{Config.CO_WARNING_MAX} ppm")
    axes[2].set_ylabel("CO Level (ppm)")
    axes[2].legend(fontsize=8)
    axes[2].set_title("CO Level Over Time")
    axes[2].grid(True, alpha=0.3)

    # Status Timeline
    status_nums = []
    status_colors_list = []
    for _, row in df.iterrows():
        status = row.get("status", "OK")
        num = {"OK": 0, "WARNING": 1, "DANGER": 2, "FALL_DETECTED": 3}.get(status, 0)
        status_nums.append(num)
        status_colors_list.append(_STATUS_CHART_COLORS.get(status, "grey"))

    axes[3].scatter(df["timestamp"], status_nums, c=status_colors_list, s=50, zorder=3)
    axes[3].set_yticks([0, 1, 2, 3])
    axes[3].set_yticklabels(["OK", "WARNING", "DANGER", "FALL"])
    axes[3].set_ylabel("Alert Status")
    axes[3].set_title("Alert Status Timeline")
    axes[3].grid(True, alpha=0.3)

    # X-axis formatting
    axes[3].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate(rotation=30)

    plt.tight_layout()
    chart_path = Config.CHARTS_DIR / f"session_charts_{ts}.png"
    plt.savefig(chart_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[CHARTS] Saved to: {chart_path}")


# ─── Main ────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smart Firefighter — MQTT Logger and Analyzer"
    )
    parser.add_argument(
        "--topic",
        default=Config.TELEMETRY_TOPIC,
        help=f"MQTT topic to subscribe to (default: {Config.TELEMETRY_TOPIC})",
    )
    parser.add_argument(
        "--no-charts",
        action="store_true",
        help="Skip matplotlib chart generation on exit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    _open_csv()

    client = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        client_id=f"logger_{datetime.now().strftime('%H%M%S')}",
        clean_session=True,
        userdata={"topic": args.topic},
    )
    client.on_connect = _on_connect
    client.on_message = _on_message
    client.on_disconnect = _on_disconnect

    print(f"[LOGGER] Connecting to {Config.BROKER_HOST}:{Config.BROKER_PORT} ...")
    try:
        client.connect(Config.BROKER_HOST, Config.BROKER_PORT, keepalive=60)
    except OSError as exc:
        print(f"[ERROR] Cannot reach MQTT broker: {exc}", file=sys.stderr)
        sys.exit(1)

    print("[LOGGER] Waiting for telemetry. Press Ctrl+C to stop and generate report.\n")
    print(
        f"  {'Timestamp':<22}  {'ID':<7}  {'HR':>5}  {'Temp':>6}  "
        f"{'CO':>7}  {'Fall':>4}  Status"
    )
    print("-" * 75)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        if _csv_file:
            _csv_file.close()

        _generate_report()
        if not args.no_charts:
            _generate_charts()


if __name__ == "__main__":
    main()
