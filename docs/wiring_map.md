# Wiring Map — Smart Firefighter Wearable System

## Component List

| ID | Component | Part Number | Interface | Simulated In |
|---|---|---|---|---|
| U1 | Microcontroller | ESP32-WROOM-32 (DevKit V1) | — | Wokwi (diagram.json) |
| U2 | Heart Rate Sensor | MAX30102 | I2C | Software only (sketch.ino simulates values) |
| U3 | Body Temperature | DS18B20 | 1-Wire | Software (4.7 kΩ pull-up in diagram.json) |
| U4 | CO Gas Sensor | MQ-7 | Analog (ADC) | Software only |
| U5 | IMU / Fall Detector | MPU6050 | I2C | Software only |
| U6 | OLED Display | SSD1306 128×64 | I2C | Wokwi (wokwi-ssd1306 part) |
| LED1 | Green LED | Generic 5mm | Digital out | Wokwi (wokwi-led, green) |
| LED2 | Yellow LED | Generic 5mm | Digital out | Wokwi (wokwi-led, yellow) |
| LED3 | Red LED | Generic 5mm | Digital out | Wokwi (wokwi-led, red) |
| BZ1 | Buzzer | Passive piezo | Digital PWM | Wokwi (wokwi-buzzer) |
| R1 | Pull-up Resistor | 4.7 kΩ | — | Wokwi (wokwi-resistor) |
| R2–R4 | LED Series Resistors | 220 Ω each | — | Wokwi (wokwi-resistor × 3) |

---

## Full Pin Assignment Table

| Signal | GPIO | Direction | Component | Wire Colour | Notes |
|---|---|---|---|---|---|
| I2C SDA | GPIO21 | Bidirectional | MAX30102, MPU6050, SSD1306 OLED | Blue | Shared I2C bus |
| I2C SCL | GPIO22 | Output | MAX30102, MPU6050, SSD1306 OLED | Cyan | Shared I2C clock |
| 1-Wire DATA | GPIO4 | Bidirectional | DS18B20 temperature sensor | Orange | Requires 4.7 kΩ pull-up to 3V3 |
| ADC Input | GPIO34 | Input only | MQ-7 analog output | Purple | GPIO34 is input-only on ESP32 |
| Buzzer PWM | GPIO18 | Output | Buzzer positive terminal | Orange | Active HIGH; GND to ESP32 GND |
| Green LED | GPIO27 | Output | LED1 anode (via 220 Ω) | Green | HIGH = LED ON (OK) |
| Yellow LED | GPIO26 | Output | LED2 anode (via 220 Ω) | Yellow | HIGH = LED ON (WARNING) |
| Red LED | GPIO25 | Output | LED3 anode (via 220 Ω) | Red | HIGH = LED ON (DANGER/FALL) |
| Power | 3V3 | Supply | All sensor VCC, LED pull-up | Red | 3.3 V supply rail |
| Ground | GND | Return | All component GND | Black | Common ground |

---

## I2C Bus Details

All I2C devices share GPIO21 (SDA) and GPIO22 (SCL):

| Device | I2C Address | Default Speed |
|---|---|---|
| MAX30102 (heart rate) | 0x57 | 100 kHz or 400 kHz |
| MPU6050 (IMU) | 0x68 | 400 kHz |
| SSD1306 (OLED) | 0x3C | 400 kHz |

**Pull-up resistors:** The I2C bus requires pull-up resistors (typically 4.7 kΩ to 3V3) on both SDA and SCL. On most breakout boards these are already included on the sensor board.

---

## DS18B20 1-Wire Wiring

```
3V3 ─────────────┐
                  │ 4.7 kΩ pull-up
                  ├──── DS18B20 VDD
GPIO4 ───────────┤──── DS18B20 DATA
                       DS18B20 GND → GND
```

The pull-up resistor is mandatory. Without it the 1-Wire protocol will not function.

---

## MQ-7 CO Sensor Wiring

```
5V (or 3V3) ──── MQ-7 VCC
GND ──────────── MQ-7 GND
GPIO34 ────────── MQ-7 AOUT (analog voltage output)
```

**Calibration note:** The MQ-7 requires a preheat cycle (5 V for 60 s, then 1.4 V for 90 s) for accurate CO measurement. The ADC reading must be converted to ppm using the sensor's RS/R0 characteristic curve. In this simulation, values are generated directly in software.

---

## LED Wiring (each LED identical pattern)

```
GPIO_N ──── 220 Ω ──── LED Anode
                        LED Cathode ──── GND
```

The 220 Ω series resistor limits current to approximately 12 mA at 3.3 V, which is within ESP32 GPIO current limits.

---

## Buzzer Wiring

```
GPIO18 ──── Buzzer (+)
GND ───────── Buzzer (−)
```

Use a transistor driver (e.g., 2N2222 or NPN MOSFET) for buzzers that require more than 12 mA. For a passive piezo buzzer driven at low current, a direct GPIO connection is acceptable.

---

## Wokwi Simulation Notes

The following components are **physically simulated** in Wokwi:
- SSD1306 OLED (displays text and status)
- Three LEDs (green / yellow / red)
- Buzzer
- 4.7 kΩ DS18B20 pull-up resistor
- 220 Ω LED series resistors

The following are **software-simulated only** (no Wokwi parts exist):
- MAX30102 (heart rate): random value generation in `readSensors()`
- MPU6050 (fall detection): random event generation
- MQ-7 (CO sensor): random ADC value
- DS18B20 actual temperature reading (1-Wire is present but reading is simulated)

---

## Consistency With Web Dashboard SVG Circuit

The wiring map above is the single source of truth for:
- `wokwi/diagram.json` — Wokwi simulation connections
- `wokwi/sketch.ino` — firmware `#define PIN_*` assignments
- `web/templates/simulation.html` — SVG circuit diagram pin labels and wire colours
- `docs/simulation_flow.md` — step-by-step process description

Any changes to GPIO assignments must be reflected in all four locations.
