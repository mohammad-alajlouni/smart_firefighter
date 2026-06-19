"""
mqtt_service.py — MQTT subscriber for the web dashboard.

Subscribes to the telemetry topic so that readings published by the
CLI simulator (simulated_wearable.py) also appear in the web dashboard,
not just readings from the web's own SimulationManager.

Duplicate suppression: if the same timestamp was already broadcast by
SimulationManager, the message is skipped.
"""

import json
import sys
import uuid
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))
from config import Config


class MQTTService:
    def __init__(self) -> None:
        self._client = None
        self._broadcast: Optional[Callable] = None
        self._loop = None
        self._last_ts: Optional[str] = None   # de-dup against SimManager

    def set_context(self, loop, broadcast: Callable) -> None:
        self._loop = loop
        self._broadcast = broadcast

    def notify_sent(self, timestamp: str) -> None:
        """SimulationManager calls this so MQTTService can skip the echo."""
        self._last_ts = timestamp

    def start(self) -> None:
        try:
            import asyncio
            import paho.mqtt.client as mqtt
            from paho.mqtt.enums import CallbackAPIVersion

            client_id = f"web_sub_{uuid.uuid4().hex[:6]}"
            client = mqtt.Client(
                callback_api_version=CallbackAPIVersion.VERSION2,
                client_id=client_id,
                clean_session=True,
            )
            client.on_connect = self._on_connect
            client.on_message = self._on_message
            client.connect(Config.BROKER_HOST, Config.BROKER_PORT, keepalive=60)
            client.loop_start()
            self._client = client
            print(f"[MQTT-SUB] Subscribing to {Config.TELEMETRY_TOPIC}")
        except Exception as exc:
            print(f"[MQTT-SUB] Could not start subscriber: {exc}")
            self._client = None

    def stop(self) -> None:
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None

    def _on_connect(self, client, userdata, flags, rc, props) -> None:
        if rc == 0:
            client.subscribe(Config.TELEMETRY_TOPIC, qos=1)

    def _on_message(self, client, userdata, msg) -> None:
        if not self._broadcast or not self._loop:
            return
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return

        # Skip if SimulationManager already broadcast this exact reading
        if payload.get("timestamp") == self._last_ts:
            return

        import asyncio
        asyncio.run_coroutine_threadsafe(
            self._broadcast(payload), self._loop
        )
