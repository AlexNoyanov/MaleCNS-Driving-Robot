# Hardware wiring — Fly Brain Robot

Arduino **Uno or Nano** (same pin numbers). Leave **D0 / D1** free for USB serial to the Raspberry Pi.

## Power rules (read this first)

- Power the Raspberry Pi 4 from its own **5V / 3A USB-C** supply (or a 5V 5A UBEC from the traction battery). **Never** power the Pi from the L298N 5V regulator.
- Remove **both** ENA and ENB jumpers on the L298N so Arduino PWM can set speed.
- Remove the L298N **5V jumper**. Feed L298N logic `+5V` from Arduino 5V. Arduino is powered by the Pi USB cable.
- **Do not** also use the L298N 5V-out jumper while Arduino is on USB — that backfeeds 5V.
- Battery GND, L298N GND, and Arduino GND **must** be tied together.
- Do **not** wire HC-SR04 Echo to Pi GPIO. Echo is 5V; Pi pins are 3.3V.

## HC-SR04 ultrasonic sensors

Each sensor: `VCC` → Arduino **5V**, `GND` → Arduino **GND**.

| Sensor | Trig | Echo |
|--------|------|------|
| Front  | D2   | D3   |
| Left   | D4   | D5   |
| Right  | D6   | D11  |

Firmware pings **one sensor at a time** (they interfere if fired together). Distance is `duration_us / 58.0` cm. Timeout (~20 ms) is reported as `-1`.

Mount them facing **left / forward / right** on the chassis so the dashboard labels match the world.

## L298N motor driver

| L298N pin | Arduino | Notes |
|-----------|---------|--------|
| ENA       | D9      | Left motor PWM. Jumper **removed**. |
| IN1       | D8      | Left direction A |
| IN2       | D7      | Left direction B |
| ENB       | D10     | Right motor PWM. Jumper **removed**. |
| IN3       | D12     | Right direction A |
| IN4       | D13     | Right direction B |
| OUT1/OUT2 | Left motor  | Swap these two wires if left wheel runs backward. |
| OUT3/OUT4 | Right motor | Swap these two wires if right wheel runs backward. |
| +12V      | Motor battery + | 7.4V 2S LiPo or 6×AA is fine; the label is just motor voltage. |
| GND       | Battery − **and** Arduino GND | Common ground. |
| +5V       | Arduino 5V | Logic power. 5V jumper **off**. |

## Raspberry Pi 4

- **Camera:** CSI ribbon (Camera Module 2 or 3). USB webcam is a software fallback.
- **Arduino:** USB A-to-B (Uno) or USB-C/Micro (Nano) into a Pi USB port.
- **Network:** same Wi-Fi LAN as the Mac. The Pi **initiates** the WebSocket to the Mac.

## USB serial protocol (Pi ↔ Arduino)

115200 baud, one line per message, `\n` terminated (`\r` ignored).

- Arduino → Pi (~12–20 Hz after a full sensor trio): `S,<front_cm>,<left_cm>,<right_cm>`
- Pi → Arduino: `M,<left>,<right>` with each value **−255..255** (sign = direction, magnitude = PWM)

If no `M,` command arrives for **200 ms**, Arduino **stops both motors**.
