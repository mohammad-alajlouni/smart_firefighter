"""
utils.py — Shared helper functions for the Smart Firefighter Wearable System.

Covers:
  • Sensor reading generation per scenario
  • Status classification using configurable thresholds
  • Alert message generation
  • Terminal-based local alert output (simulates LED / buzzer / OLED)
"""

import random
from config import Config


# ─── Scenario Definitions ────────────────────────────────────────────────────

def _normal() -> dict:
    return {
        "heart_rate": round(random.uniform(72, 95), 1),
        "body_temp": round(random.uniform(36.5, 37.5), 1),
        "co_level": round(random.uniform(5, 30), 1),
        "fall_detected": False,
    }


def _high_temperature() -> dict:
    return {
        "heart_rate": round(random.uniform(100, 118), 1),
        "body_temp": round(random.uniform(39.0, 41.0), 1),
        "co_level": round(random.uniform(10, 40), 1),
        "fall_detected": False,
    }


def _high_co() -> dict:
    return {
        "heart_rate": round(random.uniform(85, 115), 1),
        "body_temp": round(random.uniform(37.0, 38.5), 1),
        "co_level": round(random.uniform(150, 400), 1),
        "fall_detected": False,
    }


def _high_heart_rate() -> dict:
    return {
        "heart_rate": round(random.uniform(135, 180), 1),
        "body_temp": round(random.uniform(37.5, 39.0), 1),
        "co_level": round(random.uniform(10, 45), 1),
        "fall_detected": False,
    }


def _fall_detection() -> dict:
    return {
        "heart_rate": round(random.uniform(60, 100), 1),
        "body_temp": round(random.uniform(36.0, 37.5), 1),
        "co_level": round(random.uniform(5, 25), 1),
        "fall_detected": True,
    }


def _multiple_hazards() -> dict:
    return {
        "heart_rate": round(random.uniform(140, 185), 1),
        "body_temp": round(random.uniform(39.8, 41.5), 1),
        "co_level": round(random.uniform(220, 450), 1),
        "fall_detected": random.choice([True, False]),
    }


def _random() -> dict:
    generators = [
        _normal, _high_temperature, _high_co,
        _high_heart_rate, _fall_detection, _multiple_hazards,
    ]
    return random.choice(generators)()


_SCENARIO_MAP = {
    "normal": _normal,
    "high_temperature": _high_temperature,
    "high_co": _high_co,
    "high_heart_rate": _high_heart_rate,
    "fall_detection": _fall_detection,
    "multiple_hazards": _multiple_hazards,
    "random": _random,
}


def generate_scenario_readings(scenario: str) -> dict:
    """Return a dict of raw sensor readings for the requested scenario."""
    generator = _SCENARIO_MAP.get(scenario)
    if generator is None:
        raise ValueError(
            f"Unknown scenario '{scenario}'. "
            f"Valid options: {list(_SCENARIO_MAP.keys())}"
        )
    return generator()


# ─── Status Classification ────────────────────────────────────────────────────

def classify_status(readings: dict) -> str:
    """
    Classify the overall status of the firefighter based on sensor readings.

    Priority order: FALL_DETECTED > DANGER > WARNING > OK
    """
    hr = readings["heart_rate"]
    temp = readings["body_temp"]
    co = readings["co_level"]
    fall = readings["fall_detected"]

    if fall:
        return "FALL_DETECTED"

    danger = (
        hr > Config.HR_WARNING_MAX
        or temp > Config.TEMP_WARNING_MAX
        or co > Config.CO_WARNING_MAX
    )
    if danger:
        return "DANGER"

    warning = (
        hr >= Config.HR_OK_MAX
        or temp >= Config.TEMP_OK_MAX
        or co >= Config.CO_OK_MAX
    )
    if warning:
        return "WARNING"

    return "OK"


# ─── Alert Message Generation ─────────────────────────────────────────────────

def generate_alert_message(readings: dict, status: str) -> str:
    """Compose a human-readable alert message based on readings and status."""
    if status == "OK":
        return "All parameters within normal range"

    if status == "FALL_DETECTED":
        return "Fall detected - immediate assistance required"

    issues = []
    hr = readings["heart_rate"]
    temp = readings["body_temp"]
    co = readings["co_level"]

    if hr > Config.HR_WARNING_MAX:
        issues.append(f"Critical heart rate ({hr} BPM)")
    elif hr >= Config.HR_OK_MAX:
        issues.append(f"Elevated heart rate ({hr} BPM)")

    if temp > Config.TEMP_WARNING_MAX:
        issues.append(f"Critical body temperature ({temp}°C)")
    elif temp >= Config.TEMP_OK_MAX:
        issues.append(f"High body temperature ({temp}°C)")

    if co > Config.CO_WARNING_MAX:
        issues.append(f"Dangerous CO level ({co} ppm)")
    elif co >= Config.CO_OK_MAX:
        issues.append(f"Elevated CO level ({co} ppm)")

    return "; ".join(issues) if issues else "Condition requires monitoring"


# ─── Local Alert Display (Terminal Simulation) ────────────────────────────────

_ALERT_PROFILES = {
    "OK": {
        "led": "GREEN",
        "buzzer": "OFF",
        "oled": "STATUS OK",
        "color_code": "\033[92m",   # bright green
    },
    "WARNING": {
        "led": "YELLOW",
        "buzzer": "SLOW BEEP",
        "oled": "WARNING",
        "color_code": "\033[93m",   # yellow
    },
    "DANGER": {
        "led": "RED",
        "buzzer": "FAST BEEP",
        "oled": "DANGER",
        "color_code": "\033[91m",   # bright red
    },
    "FALL_DETECTED": {
        "led": "RED",
        "buzzer": "FAST BEEP",
        "oled": "FALL DETECTED",
        "color_code": "\033[95m",   # magenta
    },
}

_RESET = "\033[0m"


def print_local_alert(status: str) -> None:
    """Print a terminal representation of the local LED/buzzer/OLED output."""
    profile = _ALERT_PROFILES.get(status, _ALERT_PROFILES["OK"])
    color = profile["color_code"]
    print(
        f"{color}"
        f"  [LOCAL ALERT]  LED: {profile['led']:<8}  "
        f"BUZZER: {profile['buzzer']:<12}  "
        f"OLED: {profile['oled']}"
        f"{_RESET}"
    )
