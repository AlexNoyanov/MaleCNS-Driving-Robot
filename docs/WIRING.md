# Hardware wiring — Fly Brain Robot (L298N/L298D + Arduino + Raspberry Pi 4)

This matches the clear **2WD acrylic chassis** (yellow TT motors at the **front**, small caster at the **back**, 4×AA tray in the middle).

**Nothing from the motor driver or the HC-SR05 sensors plugs into the Raspberry Pi GPIO.**
The Pi only gets: USB-C power, USB to Arduino, camera, Wi-Fi.

```
4×AA pack (on the deck)
        │
        │  red after the slide switch
        ▼
     L298N  VS / VCC     (motor power ~6 V)
        │
        ├── OUT1/OUT2 → left yellow motor
        └── OUT3/OUT4 → right yellow motor

     L298N  IN1 IN2 IN3 IN4   ← Arduino D4–D7
     L298N  ENA ENB jumpers    ON (5 V, always enabled)
     L298N  +5V                ← Arduino 5V (if the module needs it)
     L298N  GND                ← Arduino GND  AND  battery black

Arduino USB  ←→  Raspberry Pi USB     (serial only)
Pi USB-C     ←→  5 V / 3 A supply     (never the 4×AA pack)
```

## Where each board sits on the chassis

Looking at the car the way it drives: **yellow wheels = front**, **small caster = rear**. The fly in the dashboard faces the yellow wheels.

| Part | Where to put it | Why |
|------|-----------------|-----|
| 4×AA holder | Keep it in the **center** of the acrylic (already there) | Motor power for L293D. Use the **slide switch** as the motor kill switch. |
| L298N / L298D module | **Front half** of the deck, between the yellow motors and the battery, on the hole grid | Short wires to the yellow TT motors. |
| Arduino Uno/Nano | Next to the driver, still on the **front/mid deck** | Digital pins face the driver. USB socket should point **rear or side** so the cable can reach the Pi. |
| Raspberry Pi 4 | **On top of the battery box** on standoffs, or a second acrylic floor | Too big to sit beside the pack. USB cable drops down to the Arduino. USB-C power cable leaves to a power bank. |
| Camera | **Front edge**, looking out over the yellow wheels | USB or CSI to the Pi (not to Arduino). |
| HC-SR05 center | Nose, between / above the yellow wheels | Trig D11, Echo D10. |
| HC-SR05 left / right | Left and right wings of the acrylic | Left D13/D12, right D9/D8. |

Jack the driven wheels off the table the first time you test motors.

## Power rules

- **4×AA (~6 V)** → L298N motor supply only. Do not swap in a 12 V pack for these yellow TT motors.
- **Raspberry Pi 4** → official **5 V / 3 A USB-C** or a power bank. **Never** from the 4×AA tray or from the driver.
- Arduino is powered by the **Pi USB cable**. Do not also feed Arduino VIN from the battery.
- **Common GND is mandatory:** battery black, L298N GND, Arduino GND (the USB cable already shares GND with the Pi).
- Keep **ENA and ENB jumpers ON** (tied to 5 V). This sketch does not use Arduino PWM on the enable pins.

## L298N / L298D module (current robot)

| Driver pin | Arduino | Notes |
|------------|---------|--------|
| IN1 | **D4** | Left direction A |
| IN2 | **D5** | Left direction B (PWM) |
| IN3 | **D6** | Right direction A (PWM) |
| IN4 | **D7** | Right direction B |
| ENA | jumper **ON** | Always enabled |
| ENB | jumper **ON** | Always enabled |
| OUT1 / OUT2 | Left yellow motor | If that wheel runs backward, swap these two wires only. |
| OUT3 / OUT4 | Right yellow motor | Same: swap the two motor wires if reversed. |
| VS / VCC / +12V | **Red** from the 4×AA pack **after the switch** | 4×AA is correct even if the board says 12 V. |
| +5V | Arduino **5V** if the module has a 5 V logic pin | |
| GND | Battery **black** **and** Arduino **GND** | |

Leave Arduino **D0 and D1** empty (USB serial to the Pi).

## HC-SR05 (still on Arduino, 5 V)

Each sensor: `VCC` → Arduino **5V**, `GND` → Arduino **GND**. Same ping protocol as HC-SR04.

| Sensor | Trig | Echo |
|--------|------|------|
| Left   | D13  | D12  |
| Center | D11  | D10  |
| Right  | D9   | D8   |

Ping one at a time in firmware. Do **not** wire Echo to a Pi GPIO (5 V vs 3.3 V).

## Raspberry Pi 4 connections (only these)

1. **USB-C** — 5 V / 3 A power bank or wall supply.
2. **USB-A → Arduino** — this is the only Arduino↔Pi link (serial 115200).
3. **CSI camera ribbon** — brown/blue side oriented as marked on the Pi 4 CSI connector, facing the yellow wheels (forward).
4. **Wi-Fi** — same LAN as the Mac. The Pi opens `ws://<mac-ip>:8000/robot`.

No L298N pin, no motor wire, no ultrasonic pin goes to the Pi.

## USB serial (Pi ↔ Arduino)

115200 baud, one line per message.

- Arduino → Pi: `S,<front_cm>,<left_cm>,<right_cm>`
- Pi → Arduino: `M,<left>,<right>` each **−255..255**

If no `M,` for **200 ms**, Arduino **stops both motors**.

## First power-up order

1. Flash [`firmware/arduino_robot/arduino_robot.ino`](../firmware/arduino_robot/arduino_robot.ino).
2. USB Pi → Arduino (or laptop USB) with **wheels in the air**.
3. Serial Monitor 115200: you should see `S,…` lines. Sensors can be unplugged later; motors need the L298N + battery.
4. Switch the 4×AA pack **on**.
5. Send `M,120,120` — both yellow wheels should spin **forward** (caster trails at the back).
6. Then plug the same USB into the Pi and run `pi/robot_agent.py`.
