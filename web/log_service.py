"""
log_service.py — Reads and filters CSV telemetry logs from data/logs/.
"""

import csv
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))
from config import Config


class LogService:
    def get_logs(
        self,
        limit: int = 100,
        status_filter: Optional[str] = None,
        ff_filter: Optional[str] = None,
    ) -> list[dict]:
        """Return up to `limit` log records, newest first, with optional filters."""
        Config.ensure_dirs()
        all_rows: list[dict] = []

        for csv_path in sorted(Config.LOGS_DIR.glob("*.csv"), reverse=True):
            try:
                with open(csv_path, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        all_rows.append(dict(row))
            except Exception:
                continue

        # Apply filters
        if status_filter:
            status_filter = status_filter.upper()
            all_rows = [r for r in all_rows if r.get("status") == status_filter]
        if ff_filter:
            all_rows = [r for r in all_rows if r.get("firefighter_id") == ff_filter]

        # Sort newest first, apply limit
        all_rows.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        return all_rows[:limit]

    def get_latest_csv(self) -> Optional[Path]:
        """Return the path to the most recently modified CSV log file."""
        Config.ensure_dirs()
        files = sorted(Config.LOGS_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        return files[0] if files else None

    def get_available_statuses(self) -> list[str]:
        return ["OK", "WARNING", "DANGER", "FALL_DETECTED"]
