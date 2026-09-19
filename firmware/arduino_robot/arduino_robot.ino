/*
  Fly Brain Robot — Arduino Uno / Nano firmware

  Sequential HC-SR05 (left / center / right) + L298N/L298D differential drive.
  USB serial 115200 to Raspberry Pi.

  Protocol:
    Arduino -> Pi:  S,<front_cm>,<left_cm>,<right_cm>
    Pi -> Arduino:  M,<left>,<right>     // each -255..255

  If no M command for WATCHDOG_MS, motors stop.

  Pinout: see docs/WIRING.md
  ENA/ENB on the driver must be jumpered to 5 V (always enabled).
  Speed is PWM on IN2 (D5) and IN3 (D6).
*/

// HC-SR05
const int TRIG_LEFT = 13;
const int ECHO_LEFT = 12;
const int TRIG_FRONT = 11;  // center
const int ECHO_FRONT = 10;
const int TRIG_RIGHT = 9;
const int ECHO_RIGHT = 8;

// L298N / L298D — IN pins only (ENA/ENB jumpered HIGH on the module)
const int IN1 = 4;  // left
const int IN2 = 5;  // left (PWM)
const int IN3 = 6;  // right (PWM)
const int IN4 = 7;  // right

const unsigned long PING_TIMEOUT_US = 20000UL;  // ~340 cm max; miss -> -1
const unsigned long WATCHDOG_MS = 200;
const unsigned long BAUD = 115200;

float distFront = -1.0f;
float distLeft = -1.0f;
float distRight = -1.0f;

int leftPwm = 0;
int rightPwm = 0;
unsigned long lastCmdMs = 0;
int pingPhase = 0;

String serialBuf;

void setup() {
  Serial.begin(BAUD);

  pinMode(TRIG_FRONT, OUTPUT);
  pinMode(ECHO_FRONT, INPUT);
  pinMode(TRIG_LEFT, OUTPUT);
  pinMode(ECHO_LEFT, INPUT);
  pinMode(TRIG_RIGHT, OUTPUT);
  pinMode(ECHO_RIGHT, INPUT);
  digitalWrite(TRIG_FRONT, LOW);
  digitalWrite(TRIG_LEFT, LOW);
  digitalWrite(TRIG_RIGHT, LOW);

  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  stopMotors();
  lastCmdMs = millis();  // start stopped; watchdog keeps them stopped until M,
}

float ping(int trig, int echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  unsigned long us = pulseIn(echo, HIGH, PING_TIMEOUT_US);
  if (us == 0) {
    return -1.0f;
  }
  return us / 58.0f;
}

int clampPwm(long v) {
  if (v > 255) return 255;
  if (v < -255) return -255;
  return (int)v;
}

void writeIn(int pin, int mag, bool pwmCapable) {
  if (pwmCapable) {
    analogWrite(pin, mag);
  } else {
    digitalWrite(pin, mag > 0 ? HIGH : LOW);
  }
}

void setOneMotor(int pwm, int inA, int inB, bool aPwm, bool bPwm) {
  int mag = pwm < 0 ? -pwm : pwm;
  if (mag > 255) mag = 255;
  if (pwm > 0) {
    writeIn(inA, mag, aPwm);
    writeIn(inB, 0, bPwm);
  } else if (pwm < 0) {
    writeIn(inA, 0, aPwm);
    writeIn(inB, mag, bPwm);
  } else {
    writeIn(inA, 0, aPwm);
    writeIn(inB, 0, bPwm);
  }
}

void applyMotors() {
  setOneMotor(leftPwm, IN1, IN2, false, true);
  setOneMotor(rightPwm, IN3, IN4, true, false);
}

void stopMotors() {
  leftPwm = 0;
  rightPwm = 0;
  applyMotors();
}

void handleLine(String line) {
  line.trim();
  if (line.length() < 3) return;
  if (line.charAt(0) != 'M' || line.charAt(1) != ',') return;

  int comma = line.indexOf(',', 2);
  if (comma < 0) return;

  long l = line.substring(2, comma).toInt();
  long r = line.substring(comma + 1).toInt();
  leftPwm = clampPwm(l);
  rightPwm = clampPwm(r);
  lastCmdMs = millis();
  applyMotors();
}

void pollSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      handleLine(serialBuf);
      serialBuf = "";
    } else {
      if (serialBuf.length() < 64) serialBuf += c;
      else serialBuf = "";
    }
  }
}

void loop() {
  pollSerial();

  if (millis() - lastCmdMs >= WATCHDOG_MS) {
    stopMotors();
  }

  // One sensor per loop so pulseIn cannot starve the watchdog / serial.
  if (pingPhase == 0) {
    distFront = ping(TRIG_FRONT, ECHO_FRONT);
  } else if (pingPhase == 1) {
    distLeft = ping(TRIG_LEFT, ECHO_LEFT);
  } else {
    distRight = ping(TRIG_RIGHT, ECHO_RIGHT);
    Serial.print("S,");
    Serial.print(distFront, 1);
    Serial.print(",");
    Serial.print(distLeft, 1);
    Serial.print(",");
    Serial.println(distRight, 1);
  }
  pingPhase = (pingPhase + 1) % 3;
}
