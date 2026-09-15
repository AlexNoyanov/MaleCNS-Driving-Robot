# Hardware wiring — Fly Brain Robot (L293D + Arduino + Raspberry Pi 4)

This matches the clear **2WD acrylic chassis** (yellow TT motors at the **front**, small caster at the **back**, 4×AA tray in the middle).

**Nothing from the L293D or the HC-SR04 sensors plugs into the Raspberry Pi GPIO.**
The Pi only gets: USB-C power, USB to Arduino, CSI camera ribbon, Wi-Fi.

```
4×AA pack (on the deck)
        │
        │  red after the slide switch
        ▼
     L293D  VS / VCC2   (motor power ~6 V)
        │
        ├── OUT1/OUT2 → left yellow motor
        └── OUT3/OUT4 → right yellow motor

     L293D  IN1 IN2 EN1 IN3 IN4 EN2  ← Arduino D7–D13
     L293D  VCC1 / +5V               ← Arduino 5V
     L293D  GND                      ← Arduino GND  AND  battery black

Arduino USB  ←→  Raspberry Pi USB     (serial only)
Pi USB-C     ←→  5 V / 3 A supply     (never the 4×AA pack)
Pi CSI       ←→  camera
```

## Where each board sits on the chassis

Looking at the car the way it drives: **yellow wheels = front**, **small caster = rear**. The fly in the dashboard faces the yellow wheels.

| Part | Where to put it | Why |
|------|-----------------|-----|
| 4×AA holder | Keep it in the **center** of the acrylic (already there) | Motor power for L293D. Use the **slide switch** as the motor kill switch. |
| L293D module | **Front half** of the deck, between the yellow motors and the battery, on the hole grid | Short wires to the yellow TT motors. |
| Arduino Uno/Nano | Next to the L293D, still on the **front/mid deck** | Digital pins face the L293D. USB socket should point **rear or side** so the cable can reach the Pi. |
| Raspberry Pi 4 | **On top of the battery box** on standoffs, or a second acrylic floor | Too big to sit beside the pack. USB cable drops down to the Arduino. USB-C power cable leaves to a power bank. |
| Camera | **Front edge**, looking out over the yellow wheels | CSI ribbon to the Pi (not to Arduino). |
| HC-SR04 front | Nose, between / above the yellow wheels | Trig D2, Echo D3. |
| HC-SR04 left / right | Left and right wings of the acrylic | Left D4/D5, right D6/D11. |

Jack the driven wheels off the table the first time you test motors.

## Power rules

- **4×AA (~6 V)** → L293D motor supply only. Perfect for these yellow TT motors. L293D is rated ~600 mA/channel; do not swap in a 12 V pack.
- **Raspberry Pi 4** → official **5 V / 3 A USB-C** or a power bank. **Never** from the 4×AA tray or from L293D.
- Arduino is powered by the **Pi USB cable**. Do not also feed Arduino VIN from the battery.
- **Common GND is mandatory:** battery black, L293D GND, Arduino GND (the USB cable already shares GND with the Pi).
- If the L293D board has **ENA and ENB jumpers**, **pull them off** so Arduino PWM on D9/D10 can set speed.

## L293D module (screw-terminal board)

Most green/blue “L293D motor driver” boards are labelled like this:

| L293D board | Arduino | Notes |
|-------------|---------|--------|
| ENA / EN1 | **D9** | Left motor PWM. Jumper **removed**. |
| IN1 | **D8** | Left direction A |
| IN2 | **D7** | Left direction B |
| ENB / EN2 | **D10** | Right motor PWM. Jumper **removed**. |
| IN3 | **D12** | Right direction A |
| IN4 | **D13** | Right direction B |
| OUT1 / OUT2 | Left yellow motor (two wires) | If that wheel runs backward, swap these two wires only. |
| OUT3 / OUT4 | Right yellow motor | Same: swap the two motor wires if reversed. |
| VCC2 / VS / +12V | **Red** from the 4×AA pack **after the switch** | It is not really 12 V. 4×AA is correct. |
| VCC1 / +5V | Arduino **5V** | Logic power for the chip. |
| GND | Battery **black** **and** Arduino **GND** | Two GND wires on the same GND pin is fine. |

Leave Arduino **D0 and D1** empty (USB serial to the Pi).

## L293D 16-pin IC (if your board is just the chip)

```
     EN1  1 ●        16  VCC1  → Arduino 5V
     IN1  2          15  IN4   → D13
    OUT1  3          14  OUT4  → right motor −
     GND  4          13  GND
     GND  5          12  GND
    OUT2  6          11  OUT3  → right motor +
     IN2  7          10  IN3   → D12
     VS   8          9   EN2   → D10 PWM
      ↑
   4×AA red (switched)

EN1 (pin 1) → D9 PWM
IN1 (pin 2) → D8
IN2 (pin 7) → D7
OUT1/OUT2   → left motor
```

Tie **all four GND pins** together to Arduino GND + battery black.

## HC-SR04 (still on Arduino, 5 V)

Each sensor: `VCC` → Arduino **5V**, `GND` → Arduino **GND**.

| Sensor | Trig | Echo |
|--------|------|------|
| Front  | D2   | D3   |
| Left   | D4   | D5   |
| Right  | D6   | D11  |

Ping one at a time in firmware. Do **not** wire Echo to a Pi GPIO (5 V vs 3.3 V).

## Raspberry Pi 4 connections (only these)

1. **USB-C** — 5 V / 3 A power bank or wall supply.
2. **USB-A → Arduino** — this is the only Arduino↔Pi link (serial 115200).
3. **CSI camera ribbon** — brown/blue side oriented as marked on the Pi 4 CSI connector, facing the yellow wheels (forward).
4. **Wi-Fi** — same LAN as the Mac. The Pi opens `ws://<mac-ip>:8000/robot`.

No L293D pin, no motor wire, no ultrasonic pin goes to the Pi.

## USB serial (Pi ↔ Arduino)

115200 baud, one line per message.

- Arduino → Pi: `S,<front_cm>,<left_cm>,<right_cm>`
- Pi → Arduino: `M,<left>,<right>` each **−255..255**

If no `M,` for **200 ms**, Arduino **stops both motors**.

## First power-up order

1. Flash [`firmware/arduino_robot/arduino_robot.ino`](../firmware/arduino_robot/arduino_robot.ino).
2. USB Pi → Arduino (or laptop USB) with **wheels in the air**.
3. Serial Monitor 115200: you should see `S,…` lines. Sensors can be unplugged later; motors need L293D + battery.
4. Switch the 4×AA pack **on**.
5. Send `M,120,120` — both yellow wheels should spin **forward** (caster trails at the back).
6. Then plug the same USB into the Pi and run `pi/robot_agent.py`.
