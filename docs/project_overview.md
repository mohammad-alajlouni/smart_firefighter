# Project Overview

## Background

Firefighting is one of the most hazardous professions in the world. Personnel
operating in active fire environments face simultaneous threats from extreme
heat, toxic gas accumulation, oxygen deprivation, physical exhaustion, and the
risk of sudden incapacitation through falls or cardiac events. Historically,
command teams have had limited real-time visibility into the physiological and
environmental status of individual firefighters once they enter a structure.

The emergence of the Internet of Things (IoT) and long-range radio
communication technologies such as LoRa (Long Range) presents an opportunity
to transform firefighter safety through continuous, wireless monitoring.

---

## Why Firefighter Monitoring Matters

1. **Delayed emergency response.** Without real-time health data, supervisors
   cannot distinguish between a firefighter who is proceeding normally and one
   who has collapsed or is experiencing a medical emergency.

2. **Cumulative exposure to hazards.** Carbon monoxide poisoning can develop
   gradually. A wearable sensor that tracks CO concentration over time allows
   early evacuation decisions before exposure reaches dangerous levels.

3. **Cardiac risk.** Intense physical exertion in high-temperature environments
   dramatically elevates the risk of cardiac events. Heart rate monitoring
   enables supervisors to identify firefighters approaching dangerous
   physiological limits.

4. **Accountability in dynamic situations.** During rapidly evolving incidents,
   knowing the real-time status of each team member improves command decisions
   and reduces the risk of personnel being left in dangerous areas.

---

## Why Wearable Technology is Valuable

Wearable devices offer a non-intrusive, continuous monitoring solution that:

- Operates independently of infrastructure (no cables or fixed sensors needed)
- Can be integrated into existing turnout gear (helmet, jacket, SCBA unit)
- Provides autonomous local alerts (LED, buzzer, OLED) so the firefighter
  themselves is aware of their status even without radio contact
- Transmits data wirelessly to a command dashboard, enabling remote supervision
- Records timestamped logs for post-incident analysis and training

---

## Why Simulation Was Used

This project is an **academic final-year engineering project**. A full hardware
deployment — including custom PCBs, certified wearable enclosures, environmental
testing, and real LoRa infrastructure — is beyond the scope of a single academic
project and requires significant budget and regulatory approval.

Simulation provides several key advantages in this context:

| Advantage | Explanation |
|---|---|
| **Accessibility** | Runs entirely on a laptop with free software tools |
| **Reproducibility** | Any scenario can be re-run identically without hardware variability |
| **Safety** | No risk of hardware damage or unsafe operation during testing |
| **Speed** | All scenarios (normal, hazard, fall) can be demonstrated in minutes |
| **Academic focus** | Allows the focus to remain on system design, logic, and data flow rather than hardware debugging |

The simulation accurately captures the **data model**, **classification logic**,
**communication protocol**, and **dashboard behaviour** of a real deployment.
Physical hardware characteristics (sensor calibration, battery life, enclosure
ruggedness, LoRa radio range) are explicitly acknowledged as outside scope in
the limitations document.
