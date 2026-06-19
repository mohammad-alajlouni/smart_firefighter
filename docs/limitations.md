# System Limitations

This document explicitly acknowledges the boundaries of the current simulation-
based implementation. These limitations are inherent to an academic project
conducted without physical hardware or live fire-ground access, and are not
defects in the simulation design.

---

## 1. No Real Hardware

The wearable unit is entirely software-simulated using a Python script
(`simulated_wearable.py`). No physical ESP32 microcontroller, no real sensors,
and no custom PCB are used in this project.

**Implications:**
- Sensor values are mathematically random within scenario ranges; they do not
  exhibit the analogue characteristics of real sensors (non-linearity,
  temperature drift, warm-up time, cross-sensitivity).
- Physical integration concerns (enclosure size, connector waterproofing,
  wearability, weight) are not addressed.
- The Wokwi simulation is optional and does not support WiFi or MQTT
  communication in the free-tier environment.

---

## 2. No Real LoRa Physical Testing

MQTT over TCP/IP is used as a software-level communication layer to emulate
the **logical data flow** of a LoRa link between the wearable unit and the
command-side dashboard.

> MQTT is used in this project as a software-level communication mechanism
> to emulate the logical data flow of LoRa communication between the wearable
> unit and the command-side dashboard. It does not simulate LoRa physical-layer
> characteristics such as range, interference, antenna gain, penetration through
> walls, or path loss.

**Specifically NOT tested or validated:**
- LoRa radio range (typical 1–15 km outdoors, 100–500 m through buildings)
- Signal strength and RSSI values
- Antenna design and gain
- Penetration through concrete walls, steel structures, or firefighting gear
- Multi-path interference and signal fading
- LoRaWAN network server, gateway, and application server integration
- LoRa spreading factors, bandwidth, and coding rate selection
- Packet delivery rate under real fire-ground RF conditions
- Co-channel interference from other LoRa devices

---

## 3. No Real Sensor Noise or Drift

Simulated sensor values are drawn from uniform random distributions within
scenario-specific ranges. Real sensors exhibit:

- **Gaussian noise** superimposed on the true value
- **Baseline drift** over time due to temperature changes and ageing
- **Warm-up periods** (especially gas sensors such as MQ-7 for CO)
- **Cross-sensitivity** (e.g., CO sensors responding to hydrogen or alcohol)
- **Saturation** at extreme values
- **Response time delays** (a gas sensor may take 10–60 seconds to stabilise)

The simulation does not model any of these effects.

---

## 4. No Battery Life Validation

A real firefighter wearable must operate on battery power, typically for an
entire operational shift (4–8 hours). This project does not address:

- Battery capacity selection
- Power consumption of ESP32 in active transmit mode
- Deep sleep / duty-cycling strategies
- Impact of LoRa transmission power settings on battery life
- Battery management IC selection
- Charging circuitry and connector standards (IP67/IP68 waterproofing)

---

## 5. No Ruggedness or Environmental Testing

Firefighting environments subject equipment to:

- Temperatures up to 250–500 °C (near approach limits)
- Physical impact from falling debris
- Water and chemical foam exposure
- Vibration from tools and structural movement
- EMI from radio equipment and power lines

The simulation does not model or validate behaviour under any of these
conditions. Real deployment would require:

- IP67 or IP68 enclosure rating
- Flame-retardant materials
- MIL-STD-810 or equivalent shock/vibration testing
- EMC compliance testing

---

## 6. No Real Fire-Ground Testing

The system has not been tested in any real fire or emergency response
environment. All scenario inputs are synthetic. Validation by experienced
firefighters, safety officers, and occupational health professionals would be
required before any real-world use.

---

## 7. No Multi-Firefighter Support (Current Implementation)

The current simulation supports a single firefighter (`FF-01`) on a single
MQTT topic. A production system would require:

- Unique device IDs and MQTT topics per firefighter
- A command dashboard that aggregates readings from all active units
- Alarm prioritisation when multiple firefighters are simultaneously in distress

---

## 8. No Authentication or Security

The public MQTT broker (`broker.emqx.io`) is used without TLS, username/password
authentication, or topic-level access control. In a real deployment:

- TLS 1.2+ encryption would be mandatory for all MQTT connections
- Username/password or certificate-based authentication would be required
- Topic ACLs would restrict which devices can publish to which topics
- A private MQTT broker would replace the public broker
