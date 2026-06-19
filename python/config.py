"""
config.py — Centralised configuration for the Smart Firefighter Wearable System.

All settings are read from environment variables (or a .env file at project root).
Edit .env.example → copy to .env to override defaults without touching code.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve project root (two levels above this file: python/ → project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Config:
    # ── MQTT ─────────────────────────────────────────────────────────────────
    BROKER_HOST: str = os.getenv("MQTT_BROKER_HOST", "broker.emqx.io")
    BROKER_PORT: int = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    TELEMETRY_TOPIC: str = os.getenv(
        "MQTT_TELEMETRY_TOPIC", "smart_firefighter/ff01/telemetry"
    )
    ALERT_TOPIC: str = os.getenv(
        "MQTT_ALERT_TOPIC", "smart_firefighter/ff01/alerts"
    )

    # ── Identity ──────────────────────────────────────────────────────────────
    FIREFIGHTER_ID: str = os.getenv("FIREFIGHTER_ID", "FF-01")

    # ── Timing ───────────────────────────────────────────────────────────────
    PUBLISH_INTERVAL: float = float(os.getenv("PUBLISH_INTERVAL", "2.0"))

    # ── Heart Rate thresholds (BPM) ───────────────────────────────────────────
    HR_OK_MAX: float = float(os.getenv("HR_OK_MAX", "110"))
    HR_WARNING_MAX: float = float(os.getenv("HR_WARNING_MAX", "130"))

    # ── Body Temperature thresholds (°C) ─────────────────────────────────────
    TEMP_OK_MAX: float = float(os.getenv("TEMP_OK_MAX", "38.0"))
    TEMP_WARNING_MAX: float = float(os.getenv("TEMP_WARNING_MAX", "39.5"))

    # ── CO Level thresholds (ppm) ─────────────────────────────────────────────
    CO_OK_MAX: float = float(os.getenv("CO_OK_MAX", "50"))
    CO_WARNING_MAX: float = float(os.getenv("CO_WARNING_MAX", "200"))

    # ── File Paths ────────────────────────────────────────────────────────────
    BASE_DIR: Path = _PROJECT_ROOT
    DATA_DIR: Path = _PROJECT_ROOT / "data"
    LOGS_DIR: Path = _PROJECT_ROOT / "data" / "logs"
    REPORTS_DIR: Path = _PROJECT_ROOT / "data" / "reports"
    CHARTS_DIR: Path = _PROJECT_ROOT / "data" / "charts"

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create required output directories if they do not already exist."""
        for directory in (cls.LOGS_DIR, cls.REPORTS_DIR, cls.CHARTS_DIR):
            directory.mkdir(parents=True, exist_ok=True)
