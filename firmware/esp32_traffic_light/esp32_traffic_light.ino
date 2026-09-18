/*
 * =====================================================================================
 * LifeLane ESP32 Hardware Traffic Signal Controller
 * =====================================================================================
 * This firmware runs on an ESP32 Dev Module connected via USB data cable to the 
 * LifeLane Raspberry Pi / Windows Desktop Application.
 *
 * Real-time signal states (RED, YELLOW, GREEN) for North/South and East/West approaches
 * are received over USB Serial (115200 baud) and physically actuated on the LEDs.
 *
 * Features:
 *  - 2-Face (NS & EW) and 4-Face (North, South, East, West) LED control
 *  - Built-in Power-On Self-Test (cycles all LEDs on startup)
 *  - Emergency Preemption Siren/Buzzer alert
 *  - Communication Watchdog (safe blinking amber if USB cable is disconnected)
 *  - Supports both JSON (`{"NORTH":"GREEN",...}`) and Compact commands (`SIG:NS=RED,EW=GREEN`)
 * =====================================================================================
 */

#include <Arduino.h>

// =====================================================================================
// GPIO PIN CONFIGURATION (Change these to match your prototype wiring if needed)
// =====================================================================================

// Set to true if LEDs share GND (Common Cathode - standard).
// Set to false if LEDs share 3.3V/5V (Common Anode).
#define LED_ACTIVE_HIGH true

// Approach 1 (North / South Face - Facing User)
#define PIN_NS_RED     23
#define PIN_NS_YELLOW  22
#define PIN_NS_GREEN   21

// Approach 2 (East / West Face - Side Face)
#define PIN_EW_RED     19
#define PIN_EW_YELLOW  18
#define PIN_EW_GREEN   5

// Optional: Emergency Siren / Active Buzzer for Ambulance Priority Alert
#define PIN_BUZZER     4
#define ENABLE_BUZZER  true

// On-board LED for USB Heartbeat activity
#define PIN_STATUS_LED 2

// Watchdog timeout in milliseconds (Enter failsafe if no USB data for 8 seconds)
#define WATCHDOG_TIMEOUT_MS 8000

// =====================================================================================
// Signal States & Variables
// =====================================================================================
enum SignalColor {
  COLOR_RED,
  COLOR_YELLOW,
  COLOR_GREEN,
  COLOR_OFF
};

SignalColor state_ns = COLOR_RED;
SignalColor state_ew = COLOR_RED;
bool preemption_active = false;
unsigned long last_packet_time = 0;
bool failsafe_mode = false;
unsigned long last_blink_time = 0;
bool blink_toggle = false;

// Serial buffer
String inputBuffer = "";

// =====================================================================================
// Helper Functions
// =====================================================================================

void writeLed(uint8_t pin, bool state) {
  if (!LED_ACTIVE_HIGH) {
    state = !state;
  }
  digitalWrite(pin, state ? HIGH : LOW);
}

void setApproachLights(SignalColor ns_color, SignalColor ew_color) {
  // NS Face
  writeLed(PIN_NS_RED,    ns_color == COLOR_RED);
  writeLed(PIN_NS_YELLOW, ns_color == COLOR_YELLOW);
  writeLed(PIN_NS_GREEN,  ns_color == COLOR_GREEN);

  // EW Face
  writeLed(PIN_EW_RED,    ew_color == COLOR_RED);
  writeLed(PIN_EW_YELLOW, ew_color == COLOR_YELLOW);
  writeLed(PIN_EW_GREEN,  ew_color == COLOR_GREEN);
}

void soundBuzzer(bool enable) {
  #if ENABLE_BUZZER
    digitalWrite(PIN_BUZZER, enable ? HIGH : LOW);
  #endif
}

SignalColor parseColor(const String &str) {
  String s = str;
  s.toUpperCase();
  s.trim();
  if (s.indexOf("GREEN") >= 0 || s == "G") return COLOR_GREEN;
  if (s.indexOf("YELLOW") >= 0 || s.indexOf("AMBER") >= 0 || s == "Y") return COLOR_YELLOW;
  if (s.indexOf("RED") >= 0 || s == "R") return COLOR_RED;
  return COLOR_OFF;
}

// Power-on self test to verify all LED wiring
void runStartupSelfTest() {
  Serial.println(F("[LIFELANE-ESP32] Running Startup Self-Test..."));
  
  // 1. All RED
  setApproachLights(COLOR_RED, COLOR_RED);
  soundBuzzer(true); delay(150); soundBuzzer(false);
  delay(600);

  // 2. All YELLOW
  setApproachLights(COLOR_YELLOW, COLOR_YELLOW);
  delay(600);

  // 3. All GREEN
  setApproachLights(COLOR_GREEN, COLOR_GREEN);
  delay(600);

  // 4. Initial Safe Default: NS Green / EW Red
  setApproachLights(COLOR_RED, COLOR_RED);
  delay(400);

  Serial.println(F("[LIFELANE-ESP32] Self-Test complete. Ready for serial commands."));
}

// =====================================================================================
// Command Parsers
// =====================================================================================

// Parses JSON packet e.g.:
// {"type":"signals","NORTH":"RED","SOUTH":"RED","EAST":"GREEN","WEST":"GREEN","preemption":"NORMAL"}
// or {"ns":"RED","ew":"GREEN","preempt":true}
bool parseJsonCommand(const String &line) {
  if (line.indexOf("{") < 0 || line.indexOf("}") < 0) return false;

  // Check Preemption flag
  if (line.indexOf("\"preemption\":\"AMBULANCE_GREEN\"") >= 0 ||
      line.indexOf("\"preempt\":true") >= 0 ||
      line.indexOf("\"preempt\":1") >= 0 ||
      line.indexOf("AMBULANCE_GREEN") >= 0) {
    preemption_active = true;
  } else if (line.indexOf("NORMAL") >= 0 || line.indexOf("\"preempt\":false") >= 0) {
    preemption_active = false;
  }

  // Extract NORTH / NS color
  int ns_idx = line.indexOf("\"NORTH\":");
  if (ns_idx < 0) ns_idx = line.indexOf("\"ns\":");
  if (ns_idx >= 0) {
    int start_q = line.indexOf("\"", ns_idx + 6);
    int end_q = line.indexOf("\"", start_q + 1);
    if (start_q > 0 && end_q > start_q) {
      state_ns = parseColor(line.substring(start_q + 1, end_q));
    }
  }

  // Extract EAST / EW color
  int ew_idx = line.indexOf("\"EAST\":");
  if (ew_idx < 0) ew_idx = line.indexOf("\"ew\":");
  if (ew_idx >= 0) {
    int start_q = line.indexOf("\"", ew_idx + 6);
    int end_q = line.indexOf("\"", start_q + 1);
    if (start_q > 0 && end_q > start_q) {
      state_ew = parseColor(line.substring(start_q + 1, end_q));
    }
  }

  return true;
}

// Parses compact key-value e.g.:
// SIG:NS=RED,EW=GREEN,PREEMPT=1
// or SIG:NORTH=RED,SOUTH=RED,EAST=GREEN,WEST=GREEN
bool parseCompactCommand(const String &line) {
  if (!line.startsWith("SIG:") && !line.startsWith("STATUS:")) return false;

  String body = line.substring(line.indexOf(":") + 1);
  int start = 0;
  while (start < body.length()) {
    int comma = body.indexOf(',', start);
    if (comma < 0) comma = body.length();
    String token = body.substring(start, comma);
    token.trim();

    int eq = token.indexOf('=');
    if (eq > 0) {
      String key = token.substring(0, eq);
      String val = token.substring(eq + 1);
      key.toUpperCase();
      val.toUpperCase();

      if (key == "NS" || key == "NORTH") {
        state_ns = parseColor(val);
      } else if (key == "EW" || key == "EAST") {
        state_ew = parseColor(val);
      } else if (key == "PREEMPT" || key == "PREEMPTION") {
        preemption_active = (val == "1" || val == "TRUE" || val.indexOf("AMBULANCE") >= 0);
      }
    }
    start = comma + 1;
  }
  return true;
}

void processIncomingLine(String line) {
  line.trim();
  if (line.length() == 0) return;

  bool ok = false;
  if (line.startsWith("{")) {
    ok = parseJsonCommand(line);
  } else {
    ok = parseCompactCommand(line);
  }

  if (ok) {
    last_packet_time = millis();
    failsafe_mode = false;
    setApproachLights(state_ns, state_ew);

    // If preemption is active, sound brief buzzer chirps
    if (preemption_active) {
      soundBuzzer(true);
    } else {
      soundBuzzer(false);
    }

    // Echo confirmation back to LifeLane
    Serial.print(F("ACK:NS="));
    Serial.print(state_ns == COLOR_GREEN ? "G" : (state_ns == COLOR_YELLOW ? "Y" : "R"));
    Serial.print(F(",EW="));
    Serial.print(state_ew == COLOR_GREEN ? "G" : (state_ew == COLOR_YELLOW ? "Y" : "R"));
    Serial.print(F(",PRE="));
    Serial.println(preemption_active ? "1" : "0");

    // Toggle status LED
    digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED));
  }
}

// =====================================================================================
// Arduino Setup & Loop
// =====================================================================================

void setup() {
  Serial.begin(115200);
  delay(100);

  // Configure output pins
  pinMode(PIN_NS_RED, OUTPUT);
  pinMode(PIN_NS_YELLOW, OUTPUT);
  pinMode(PIN_NS_GREEN, OUTPUT);

  pinMode(PIN_EW_RED, OUTPUT);
  pinMode(PIN_EW_YELLOW, OUTPUT);
  pinMode(PIN_EW_GREEN, OUTPUT);

  pinMode(PIN_STATUS_LED, OUTPUT);

  #if ENABLE_BUZZER
    pinMode(PIN_BUZZER, OUTPUT);
    digitalWrite(PIN_BUZZER, LOW);
  #endif

  // Execute Power-on Self Test
  runStartupSelfTest();

  last_packet_time = millis();
  inputBuffer.reserve(256);
}

void loop() {
  // 1. Read Serial input non-blocking
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 0) {
        processIncomingLine(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
      if (inputBuffer.length() > 250) {
        inputBuffer = ""; // buffer overflow protection
      }
    }
  }

  // 2. Watchdog: If LifeLane app is not sending packets, flash amber / all-red for safety
  unsigned long now = millis();
  if (now - last_packet_time > WATCHDOG_TIMEOUT_MS) {
    failsafe_mode = true;
    soundBuzzer(false);

    // Blink amber every 500ms in failsafe mode
    if (now - last_blink_time > 500) {
      last_blink_time = now;
      blink_toggle = !blink_toggle;
      if (blink_toggle) {
        setApproachLights(COLOR_YELLOW, COLOR_YELLOW);
        digitalWrite(PIN_STATUS_LED, HIGH);
      } else {
        setApproachLights(COLOR_OFF, COLOR_OFF);
        digitalWrite(PIN_STATUS_LED, LOW);
      }
    }
  }
}
