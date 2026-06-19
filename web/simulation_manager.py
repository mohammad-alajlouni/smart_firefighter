"""
simulation_manager.py — Background simulation thread for the web dashboard.

Generates sensor readings, writes CSV, publishes to MQTT, and broadcasts
payloads to connected WebSocket clients via an asyncio callback.
"""

import asyncio
import csv
import json
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from config import Config
from utils import classify_status, generate_alert_message, generate_scenario_readings

VALID_SCENARIOS = [
    "normal", "high_temperature", "high_co",
    "high_heart_rate", "fall_detection", "multiple_hazards", "random",
]


class SimulationManager:
    def __init__(self) -> None:
        self.running: bool = False
        self.scenario: str = "normal"
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._broadcast: Optional[Callable] = None
        self._mqtt_client = None

        self.last_payload: Optional[dict] = None
        self.records: list[dict] = []
        self.mqtt_connected: bool = False

        # Session statistics
        self.total_readings: int = 0
        self.warning_count: int = 0
        self.danger_count: int = 0
        self.fall_count: int = 0

        # CSV handles
        self._csv_file = None
        self._csv_writer = None

    # ── Setup ─────────────────────────────────────────────────────────────────

    def set_loop_and_callback(
        self, loop: asyncio.AbstractEventLoop, broadcast: Callable
    ) -> None:
        self._loop = loop
        self._broadcast = broadcast

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self, scenario: str = "normal") -> None:
        if self.running:
            self.stop()
        self.scenario = scenario
        self._stop_event.clear()
        self.running = True
        Config.ensure_dirs()
        self._open_csv()
        self._start_mqtt()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=6)
        self._close_csv()
        self._stop_mqtt()

    # ── Simulation loop ───────────────────────────────────────────────────────

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                readings = generate_scenario_readings(self.scenario)
                payload = self._build_payload(readings)
                self._handle_payload(payload)
            except Exception as exc:
                print(f"[SIM] Error in simulation loop: {exc}")
            self._stop_event.wait(timeout=Config.PUBLISH_INTERVAL)

    def _build_payload(self, readings: dict) -> dict:
        status = classify_status(readings)
        return {
            "firefighter_id": Config.FIREFIGHTER_ID,
            "heart_rate": readings["heart_rate"],
            "body_temp": readings["body_temp"],
            "co_level": readings["co_level"],
            "fall_detected": readings["fall_detected"],
            "status": status,
            "alert_message": generate_alert_message(readings, status),
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def _handle_payload(self, payload: dict) -> None:
        self.last_payload = payload
        self.records.append(payload)
        self.total_readings += 1
        s = payload["status"]
        if s == "WARNING":
            self.warning_count += 1
        elif s == "DANGER":
            self.danger_count += 1
        elif s == "FALL_DETECTED":
            self.fall_count += 1

        self._write_csv(payload)
        self._mqtt_publish(payload)

        if self._loop and self._broadcast:
            asyncio.run_coroutine_threadsafe(
                self._broadcast(payload), self._loop
            )

    # ── One-shot publish ──────────────────────────────────────────────────────

    def publish_once(self, scenario: str) -> dict:
        Config.ensure_dirs()
        if not self._csv_writer:
            self._open_csv()
        readings = generate_scenario_readings(scenario)
        payload = self._build_payload(readings)
        self._handle_payload(payload)
        return payload

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        ok_count = max(
            0,
            self.total_readings - self.warning_count - self.danger_count - self.fall_count,
        )
        return {
            "simulation_running": self.running,
            "active_scenario": self.scenario,
            "mqtt_connected": self.mqtt_connected,
            "last_payload": self.last_payload,
            "total_readings": self.total_readings,
            "ok_count": ok_count,
            "warning_count": self.warning_count,
            "danger_count": self.danger_count,
            "fall_count": self.fall_count,
        }

    # ── CSV ───────────────────────────────────────────────────────────────────

    _CSV_COLUMNS = [
        "timestamp", "firefighter_id", "heart_rate", "body_temp",
        "co_level", "fall_detected", "status", "alert_message",
    ]

    def _open_csv(self) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Config.LOGS_DIR / f"web_telemetry_{ts}.csv"
        self._csv_file = open(path, "w", newline="", encoding="utf-8")
        self._csv_writer = csv.DictWriter(
            self._csv_file, fieldnames=self._CSV_COLUMNS
        )
        self._csv_writer.writeheader()

    def _write_csv(self, payload: dict) -> None:
        if not self._csv_writer:
            return
        try:
            self._csv_writer.writerow(
                {col: payload.get(col, "") for col in self._CSV_COLUMNS}
            )
            self._csv_file.flush()
        except Exception:
            pass

    def _close_csv(self) -> None:
        if self._csv_file:
            try:
                self._csv_file.close()
            except Exception:
                pass
            self._csv_file = None
            self._csv_writer = None

    # ── MQTT ──────────────────────────────────────────────────────────────────

    def _start_mqtt(self) -> None:
        try:
            import paho.mqtt.client as mqtt
            from paho.mqtt.enums import CallbackAPIVersion

            client_id = f"web_{Config.FIREFIGHTER_ID}_{uuid.uuid4().hex[:6]}"
            client = mqtt.Client(
                callback_api_version=CallbackAPIVersion.VERSION2,
                client_id=client_id,
                clean_session=True,
            )

            def _on_connect(c, ud, flags, rc, props):
                self.mqtt_connected = rc == 0

            def _on_disconnect(c, ud, flags, rc, props):
                self.mqtt_connected = False

            client.on_connect = _on_connect
            client.on_disconnect = _on_disconnect
            client.connect(Config.BROKER_HOST, Config.BROKER_PORT, keepalive=60)
            client.loop_start()
            self._mqtt_client = client
        except Exception as exc:
            print(f"[MQTT] Could not connect: {exc}")
            self._mqtt_client = None

    def _stop_mqtt(self) -> None:
        if self._mqtt_client:
            try:
                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()
            except Exception:
                pass
            self._mqtt_client = None
        self.mqtt_connected = False

    def _mqtt_publish(self, payload: dict) -> None:
        if not self._mqtt_client or not self.mqtt_connected:
            return
        try:
            body = json.dumps(payload, ensure_ascii=False)
            self._mqtt_client.publish(Config.TELEMETRY_TOPIC, body, qos=1)
            if payload["status"] != "OK":
                alert = {
                    k: payload[k]
                    for k in ("firefighter_id", "status", "alert_message", "timestamp")
                }
                self._mqtt_client.publish(
                    Config.ALERT_TOPIC, json.dumps(alert), qos=1
                )
        except Exception as exc:
            print(f"[MQTT] Publish error: {exc}")
