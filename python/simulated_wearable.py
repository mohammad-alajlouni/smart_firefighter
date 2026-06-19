#!/usr/bin/env python3
"""
simulated_wearable.py — Smart Firefighter Wearable Simulator

Generates synthetic sensor readings for a firefighter wearable device,
classifies the health/hazard status, and publishes JSON telemetry to an
MQTT broker that acts as the logical equivalent of a LoRa gateway.

NOTE: MQTT is used here to emulate the data-flow behaviour of LoRa
communication. It does NOT simulate LoRa physical-layer characteristics
such as range, signal strength, wall penetration, or antenna behaviour.

Usage:
    python simulated_wearable.py --scenario normal
    python simulated_wearable.py --scenario high_co
    python simulated_wearable.py --scenario fall_detection --interval 1
    python simulated_wearable.py --scenario multiple_hazards --count 20
    python simulated_wearable.py --scenario random --dry-run
"""

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from config import Config
from utils import (
    classify_status,
    generate_alert_message,
    generate_scenario_readings,
    print_local_alert,
)

VALID_SCENARIOS = [
    "normal",
    "high_temperature",
    "high_co",
    "high_heart_rate",
    "fall_detection",
    "multiple_hazards",
    "random",
]

# Track whether we are currently connected
_connected = False


# ─── MQTT Callbacks (paho-mqtt v2 signatures) ────────────────────────────────

def _on_connect(client, userdata, connect_flags, reason_code, properties):
    global _connected
    if reason_code == 0:
        _connected = True
        print(f"[MQTT] Connected successfully -> {Config.BROKER_HOST}:{Config.BROKER_PORT}")
    else:
        print(f"[MQTT] Connection refused (reason={reason_code})", file=sys.stderr)


def _on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    global _connected
    _connected = False
    if reason_code != 0:
        print(f"[MQTT] Unexpected disconnection (rc={reason_code})", file=sys.stderr)
    else:
        print("[MQTT] Disconnected cleanly.")


def _on_publish(client, userdata, mid, reason_code, properties):
    pass  # suppress per-message noise


# ─── Payload Construction ─────────────────────────────────────────────────────

def build_payload(readings: dict) -> dict:
    """Combine raw sensor readings with derived status and alert message."""
    status = classify_status(readings)
    alert_msg = generate_alert_message(readings, status)
    return {
        "firefighter_id": Config.FIREFIGHTER_ID,
        "heart_rate": readings["heart_rate"],
        "body_temp": readings["body_temp"],
        "co_level": readings["co_level"],
        "fall_detected": readings["fall_detected"],
        "status": status,
        "alert_message": alert_msg,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ─── MQTT Client Setup ────────────────────────────────────────────────────────

def create_mqtt_client() -> mqtt.Client:
    client_id = f"wearable_{Config.FIREFIGHTER_ID}_{uuid.uuid4().hex[:6]}"
    client = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        client_id=client_id,
        clean_session=True,
    )
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_publish = _on_publish
    return client


def connect_mqtt(client: mqtt.Client) -> None:
    try:
        client.connect(Config.BROKER_HOST, Config.BROKER_PORT, keepalive=60)
        client.loop_start()
        # Wait up to 5 seconds for the broker to confirm the connection
        for _ in range(50):
            if _connected:
                break
            time.sleep(0.1)
        if not _connected:
            print("[WARN] Broker did not confirm connection within 5 s — continuing anyway.")
    except OSError as exc:
        print(f"[ERROR] Cannot reach MQTT broker: {exc}", file=sys.stderr)
        sys.exit(1)


def _safe_publish(client: mqtt.Client, topic: str, payload: str, qos: int = 1) -> bool:
    """Publish and wait for delivery; return True on success, False on failure."""
    if not _connected:
        print("[WARN] Not connected — skipping publish.", file=sys.stderr)
        return False
    try:
        result = client.publish(topic, payload, qos=qos)
        result.wait_for_publish(timeout=5.0)
        return True
    except (RuntimeError, ValueError) as exc:
        print(f"[WARN] Publish failed: {exc}", file=sys.stderr)
        return False


# ─── Main Simulation Loop ─────────────────────────────────────────────────────

def run_simulation(
    scenario: str,
    dry_run: bool,
    interval: float,
    count: int,
) -> None:
    client = None

    if not dry_run:
        client = create_mqtt_client()
        connect_mqtt(client)
    else:
        print("[DRY-RUN] No MQTT connection. Payloads will be printed only.\n")

    print(f"[SIM] Scenario        : {scenario}")
    print(f"[SIM] Firefighter ID  : {Config.FIREFIGHTER_ID}")
    print(f"[SIM] Broker          : {Config.BROKER_HOST}:{Config.BROKER_PORT}")
    print(f"[SIM] Telemetry topic : {Config.TELEMETRY_TOPIC}")
    print(f"[SIM] Alert topic     : {Config.ALERT_TOPIC}")
    print(f"[SIM] Interval        : {interval}s")
    print(f"[SIM] Count           : {'unlimited' if not count else count}")
    print("-" * 70)

    published = 0
    try:
        while True:
            readings = generate_scenario_readings(scenario)
            payload = build_payload(readings)
            payload_json = json.dumps(payload, indent=2, ensure_ascii=False)

            print(f"\n[{payload['timestamp']}]")
            print(payload_json)
            print_local_alert(payload["status"])

            if not dry_run and client:
                ok = _safe_publish(client, Config.TELEMETRY_TOPIC, payload_json)
                if ok:
                    published += 1

                # Publish to alert topic for non-OK statuses
                if payload["status"] != "OK":
                    alert = {
                        "firefighter_id": payload["firefighter_id"],
                        "status": payload["status"],
                        "alert_message": payload["alert_message"],
                        "timestamp": payload["timestamp"],
                    }
                    _safe_publish(client, Config.ALERT_TOPIC, json.dumps(alert))
            else:
                published += 1

            if count and published >= count:
                print(f"\n[SIM] Reached requested count of {count}. Stopping.")
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[SIM] Stopped by user (Ctrl+C).")
    finally:
        if client:
            client.loop_stop()
            client.disconnect()
        print(f"[SIM] Total readings published: {published}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Smart Firefighter Wearable Simulator\n"
            "Publishes synthetic sensor telemetry to MQTT (LoRa data-flow emulation)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scenario",
        choices=VALID_SCENARIOS,
        default="normal",
        metavar="SCENARIO",
        help=(
            "Simulation scenario. Choices: "
            + ", ".join(VALID_SCENARIOS)
            + "  (default: normal)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON payloads to terminal without publishing to MQTT.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=Config.PUBLISH_INTERVAL,
        help=f"Seconds between readings (default: {Config.PUBLISH_INTERVAL})",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Number of readings to publish then stop (0 = run indefinitely).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_simulation(
        scenario=args.scenario,
        dry_run=args.dry_run,
        interval=args.interval,
        count=args.count,
    )


if __name__ == "__main__":
    main()
