/*
  Fly Brain Robot — Arduino Uno / Nano firmware

  Sequential HC-SR04 (front/left/right) + L293D differential drive.
  USB serial 115200 to Raspberry Pi.

  Protocol:
    Arduino -> Pi:  S,<front_cm>,<left_cm>,<right_cm>
    Pi -> Arduino:  M,<left>,<right>     // each -255..255

  If no M command for WATCHDOG_MS, motors stop.

  Pinout: see docs/WIRING.md
*/

const int TRIG_FRONT = 2;
const int ECHO_FRONT = 3;
const int TRIG_LEFT = 4;
const int ECHO_LEFT = 5;
const int TRIG_RIGHT = 6;
const int ECHO_RIGHT = 11;

const int ENA = 9;   // L293D EN1, left PWM
const int IN1 = 8;   // L293D IN1
const int IN2 = 7;   // L293D IN2
const int ENB = 10;  // L293D EN2, right PWM
const int IN3 = 12;  // L293D IN3
const int IN4 = 13;  // L293D IN4

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

  pinMode(ENA, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(ENB, OUTPUT);
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

void setOneMotor(int pwm, int inA, int inB, int en) {
  int mag = pwm < 0 ? -pwm : pwm;
  if (mag > 255) mag = 255;
  if (pwm > 0) {
    digitalWrite(inA, HIGH);
    digitalWrite(inB, LOW);
  } else if (pwm < 0) {
    digitalWrite(inA, LOW);
    digitalWrite(inB, HIGH);
  } else {
    digitalWrite(inA, LOW);
    digitalWrite(inB, LOW);
  }
  analogWrite(en, mag);
}

void applyMotors() {
  setOneMotor(leftPwm, IN1, IN2, ENA);
  setOneMotor(rightPwm, IN3, IN4, ENB);
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
