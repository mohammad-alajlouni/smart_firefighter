"""
report_service.py — Summary statistics and report export.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))
from config import Config


class ReportService:
    def get_summary(self, records: list[dict]) -> dict:
        if not records:
            return {
                "total_readings": 0,
                "ok_count": 0,
                "warning_count": 0,
                "danger_count": 0,
                "fall_count": 0,
                "max_heart_rate": None,
                "max_body_temp": None,
                "max_co_level": None,
                "first_timestamp": None,
                "last_timestamp": None,
            }

        statuses = [r.get("status", "OK") for r in records]
        ok = statuses.count("OK")
        warn = statuses.count("WARNING")
        danger = statuses.count("DANGER")
        fall = statuses.count("FALL_DETECTED")

        def _safe_max(key: str):
            vals = []
            for r in records:
                try:
                    vals.append(float(r[key]))
                except (KeyError, ValueError, TypeError):
                    pass
            return round(max(vals), 1) if vals else None

        timestamps = sorted(
            r.get("timestamp", "") for r in records if r.get("timestamp")
        )

        return {
            "total_readings": len(records),
            "ok_count": ok,
            "warning_count": warn,
            "danger_count": danger,
            "fall_count": fall,
            "max_heart_rate": _safe_max("heart_rate"),
            "max_body_temp": _safe_max("body_temp"),
            "max_co_level": _safe_max("co_level"),
            "first_timestamp": timestamps[0] if timestamps else None,
            "last_timestamp": timestamps[-1] if timestamps else None,
        }

    def save_summary(self, records: list[dict]) -> Path:
        Config.ensure_dirs()
        summary = self.get_summary(records)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Config.REPORTS_DIR / f"web_report_{ts}.txt"

        lines = [
            "=" * 60,
            "  SMART FIREFIGHTER WEARABLE -- SESSION SUMMARY",
            f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            f"  Total readings      : {summary['total_readings']}",
            "",
            "  Status Breakdown:",
            f"    OK readings       : {summary['ok_count']}",
            f"    WARNING events    : {summary['warning_count']}",
            f"    DANGER events     : {summary['danger_count']}",
            f"    FALL events       : {summary['fall_count']}",
            "",
            "  Peak Values:",
            f"    Max heart rate    : {summary['max_heart_rate']} BPM",
            f"    Max body temp     : {summary['max_body_temp']} deg C",
            f"    Max CO level      : {summary['max_co_level']} ppm",
            "",
            "  Session Timeline:",
            f"    First reading     : {summary['first_timestamp']}",
            f"    Last reading      : {summary['last_timestamp']}",
            "=" * 60,
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
