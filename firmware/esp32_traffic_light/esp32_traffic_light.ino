/*
 * =====================================================================================
 * LifeLane ESP32 Hardware Traffic Signal Controller (Dual USB + LoRa)
 * =====================================================================================
 * Pin Assignment (User Prototype):
 *   North (Approach 1): Red = 2,  Green = 5
 *   South (Approach 2): Red = 12, Green = 14
 *   East  (Approach 3): Red = 15, Green = 22
 *   West  (Approach 4): Red = 32, Green = 13
 *
 *   LoRa 433MHz (SX1278):
 *     SCK = 18, MISO = 19, MOSI = 23, SS = 27, RST = 25, DIO0 = 26
 *
 * Serial Protocol (115200 baud over USB Data Cable):
 *   Accepts:
 *     SIG:N=GREEN,S=GREEN,E=RED,W=RED,PRE=0
 *     {"N":"GREEN","S":"GREEN","E":"RED","W":"RED"}
 *     {"NORTH":"GREEN","SOUTH":"GREEN","EAST":"RED","WEST":"RED"}
 *     SIG:S1 (North Green), SIG:S2 (South Green), SIG:S3 (East Green), SIG:S4 (West Green)
 * =====================================================================================
 */

#include <SPI.h>
#include <LoRa.h>

// -------- LoRa Pins --------
#define LORA_SCK  18
#define LORA_MISO 19
#define LORA_MOSI 23
#define LORA_SS   27
#define LORA_RST  25
#define LORA_DIO0 26

String unitID = "N02";
const long LORA_FREQUENCY = 433E6;

// -------- Signal Pins --------
#define N_RED 2
#define N_GRN 5

#define S_RED 12
#define S_GRN 14

#define E_RED 15
#define E_GRN 22

#define W_RED 32
#define W_GRN 13

// -------- State Tracking --------
bool n_is_green = false;
bool s_is_green = false;
bool e_is_green = false;
bool w_is_green = false;

// Standalone autonomous rotation (fallback if USB is not streaming)
unsigned long lastUsbTime = 0;
const unsigned long USB_TIMEOUT_MS = 3000;

int standalonePhase = 0; // 0=NS Green, 1=All Red, 2=EW Green, 3=All Red
unsigned long lastStandaloneTime = 0;
const unsigned long STANDALONE_GREEN_MS = 5000;
const unsigned long STANDALONE_CLEAR_MS = 1500;

// LoRa
bool loraReady = false;
unsigned long lastLoraTime = 0;
const unsigned long LORA_TIMEOUT_MS = 4000;
bool loraPriorityActive = false;
int loraPriorityDir = 0;

String rxBuffer = "";

// =====================================================================================
// Output Functions
// =====================================================================================

void applyOutputs() {
  // North
  digitalWrite(N_RED, n_is_green ? LOW : HIGH);
  digitalWrite(N_GRN, n_is_green ? HIGH : LOW);

  // South
  digitalWrite(S_RED, s_is_green ? LOW : HIGH);
  digitalWrite(S_GRN, s_is_green ? HIGH : LOW);

  // East
  digitalWrite(E_RED, e_is_green ? LOW : HIGH);
  digitalWrite(E_GRN, e_is_green ? HIGH : LOW);

  // West
  digitalWrite(W_RED, w_is_green ? LOW : HIGH);
  digitalWrite(W_GRN, w_is_green ? HIGH : LOW);
}

void setAllRed() {
  n_is_green = false;
  s_is_green = false;
  e_is_green = false;
  w_is_green = false;
  applyOutputs();
}

void setSingleGreen(int dir) {
  n_is_green = (dir == 0);
  s_is_green = (dir == 1);
  e_is_green = (dir == 2);
  w_is_green = (dir == 3);
  applyOutputs();
}

void setPhaseNSGreen() {
  n_is_green = true;
  s_is_green = true;
  e_is_green = false;
  w_is_green = false;
  applyOutputs();
}

void setPhaseEWGreen() {
  n_is_green = false;
  s_is_green = false;
  e_is_green = true;
  w_is_green = true;
  applyOutputs();
}

// Power-on self-test to verify each LED circuit
void startupTest() {
  Serial.println(F("[LIFELANE-HW] Startup LED Self-Test starting..."));
  setAllRed();
  delay(500);

  // North Green
  setSingleGreen(0);
  delay(400);

  // South Green
  setSingleGreen(1);
  delay(400);

  // East Green
  setSingleGreen(2);
  delay(400);

  // West Green
  setSingleGreen(3);
  delay(400);

  setAllRed();
  delay(300);
  Serial.println(F("[LIFELANE-HW] Self-Test complete. Listening on USB Serial (115200)..."));
}

// =====================================================================================
// Command Parser (Robust case/space-insensitive parser)
// =====================================================================================

void parseCommand(String cmd) {
  cmd.toUpperCase();
  cmd.trim();
  if (cmd.length() == 0) return;

  lastUsbTime = millis();

  // 1. Direct phase commands
  if (cmd.indexOf("SIG:S1") >= 0 || cmd.indexOf("TARGET=NORTH") >= 0) {
    setSingleGreen(0);
    Serial.println(F("ACK:NORTH_GREEN"));
    return;
  }
  if (cmd.indexOf("SIG:S2") >= 0 || cmd.indexOf("TARGET=SOUTH") >= 0) {
    setSingleGreen(1);
    Serial.println(F("ACK:SOUTH_GREEN"));
    return;
  }
  if (cmd.indexOf("SIG:S3") >= 0 || cmd.indexOf("TARGET=EAST") >= 0) {
    setSingleGreen(2);
    Serial.println(F("ACK:EAST_GREEN"));
    return;
  }
  if (cmd.indexOf("SIG:S4") >= 0 || cmd.indexOf("TARGET=WEST") >= 0) {
    setSingleGreen(3);
    Serial.println(F("ACK:WEST_GREEN"));
    return;
  }
  if (cmd.indexOf("ALL_RED") >= 0 || cmd.indexOf("ALLRED") >= 0) {
    setAllRed();
    Serial.println(F("ACK:ALL_RED"));
    return;
  }

  // 2. Multi-approach states (works for JSON and SIG:... format)
  // Check North
  if (cmd.indexOf("\"N\":\"GREEN\"") >= 0 || cmd.indexOf("\"N\": \"GREEN\"") >= 0 ||
      cmd.indexOf("N=GREEN") >= 0 || cmd.indexOf("NORTH=GREEN") >= 0 ||
      cmd.indexOf("\"NORTH\":\"GREEN\"") >= 0 || cmd.indexOf("\"NORTH\": \"GREEN\"") >= 0) {
    n_is_green = true;
  } else {
    n_is_green = false;
  }

  // Check South
  if (cmd.indexOf("\"S\":\"GREEN\"") >= 0 || cmd.indexOf("\"S\": \"GREEN\"") >= 0 ||
      cmd.indexOf("S=GREEN") >= 0 || cmd.indexOf("SOUTH=GREEN") >= 0 ||
      cmd.indexOf("\"SOUTH\":\"GREEN\"") >= 0 || cmd.indexOf("\"SOUTH\": \"GREEN\"") >= 0) {
    s_is_green = true;
  } else {
    s_is_green = false;
  }

  // Check East
  if (cmd.indexOf("\"E\":\"GREEN\"") >= 0 || cmd.indexOf("\"E\": \"GREEN\"") >= 0 ||
      cmd.indexOf("E=GREEN") >= 0 || cmd.indexOf("EAST=GREEN") >= 0 ||
      cmd.indexOf("\"EAST\":\"GREEN\"") >= 0 || cmd.indexOf("\"EAST\": \"GREEN\"") >= 0) {
    e_is_green = true;
  } else {
    e_is_green = false;
  }

  // Check West
  if (cmd.indexOf("\"W\":\"GREEN\"") >= 0 || cmd.indexOf("\"W\": \"GREEN\"") >= 0 ||
      cmd.indexOf("W=GREEN") >= 0 || cmd.indexOf("WEST=GREEN") >= 0 ||
      cmd.indexOf("\"WEST\":\"GREEN\"") >= 0 || cmd.indexOf("\"WEST\": \"GREEN\"") >= 0) {
    w_is_green = true;
  } else {
    w_is_green = false;
  }

  applyOutputs();
  Serial.print(F("ACK:STATE [N="));
  Serial.print(n_is_green ? "G" : "R");
  Serial.print(F(" S="));
  Serial.print(s_is_green ? "G" : "R");
  Serial.print(F(" E="));
  Serial.print(e_is_green ? "G" : "R");
  Serial.print(F(" W="));
  Serial.print(w_is_green ? "G" : "R");
  Serial.println(F("]"));
}

// =====================================================================================
// LoRa Handler
// =====================================================================================

void checkLoRa() {
  if (!loraReady) return;

  int packetSize = LoRa.parsePacket();
  if (!packetSize) return;

  String rx = "";
  while (LoRa.available()) {
    rx += (char)LoRa.read();
  }
  rx.trim();
  rx.replace("\n", "");
  rx.replace("\r", "");

  Serial.print(F("[LORA-RX] "));
  Serial.println(rx);

  int sep = rx.indexOf('-');
  if (sep != -1) {
    String target = rx.substring(0, sep);
    String cmd = rx.substring(sep + 1);
    target.trim();
    cmd.trim();

    if (target == unitID || target == "ALL") {
      loraPriorityActive = true;
      lastLoraTime = millis();

      if (cmd.indexOf("SIG:S1") >= 0) loraPriorityDir = 0;
      else if (cmd.indexOf("SIG:S2") >= 0) loraPriorityDir = 1;
      else if (cmd.indexOf("SIG:S3") >= 0) loraPriorityDir = 2;
      else if (cmd.indexOf("SIG:S4") >= 0) loraPriorityDir = 3;

      setSingleGreen(loraPriorityDir);
      Serial.print(F("LORA_TRIGGER:DIR="));
      Serial.println(loraPriorityDir);
    }
  }
}

// =====================================================================================
// Arduino Setup & Main Loop
// =====================================================================================

void setup() {
  Serial.begin(115200);
  delay(100);

  // Configure output pins
  pinMode(N_RED, OUTPUT); pinMode(N_GRN, OUTPUT);
  pinMode(S_RED, OUTPUT); pinMode(S_GRN, OUTPUT);
  pinMode(E_RED, OUTPUT); pinMode(E_GRN, OUTPUT);
  pinMode(W_RED, OUTPUT); pinMode(W_GRN, OUTPUT);

  startupTest();

  // Setup LoRa
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (LoRa.begin(LORA_FREQUENCY)) {
    loraReady = true;
    Serial.println(F("[LORA] Ready (433MHz)"));
  } else {
    loraReady = false;
    Serial.println(F("[LORA] LoRa not detected. Running USB Serial mode."));
  }

  rxBuffer.reserve(256);
  lastStandaloneTime = millis();
}

void loop() {
  // 1. Read Serial input non-blocking
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (rxBuffer.length() > 0) {
        parseCommand(rxBuffer);
        rxBuffer = "";
      }
    } else {
      rxBuffer += c;
      if (rxBuffer.length() > 240) rxBuffer = "";
    }
  }

  // 2. Check LoRa
  checkLoRa();

  unsigned long now = millis();

  // 3. Priority from LoRa takes temporary precedence
  if (loraPriorityActive) {
    if (now - lastLoraTime <= LORA_TIMEOUT_MS) {
      setSingleGreen(loraPriorityDir);
      return;
    } else {
      loraPriorityActive = false;
      Serial.println(F("[LORA] Priority timed out."));
    }
  }

  // 4. If USB data is active from LifeLane application, it controls the lights
  if (now - lastUsbTime <= USB_TIMEOUT_MS) {
    return; // Driven by Serial parseCommand()
  }

  // 5. Fallback: Standalone Autonomous Cycle when USB is disconnected
  if (standalonePhase == 0) {
    // NS Green
    setPhaseNSGreen();
    if (now - lastStandaloneTime >= STANDALONE_GREEN_MS) {
      standalonePhase = 1;
      lastStandaloneTime = now;
    }
  } else if (standalonePhase == 1) {
    // All Red clearance
    setAllRed();
    if (now - lastStandaloneTime >= STANDALONE_CLEAR_MS) {
      standalonePhase = 2;
      lastStandaloneTime = now;
    }
  } else if (standalonePhase == 2) {
    // EW Green
    setPhaseEWGreen();
    if (now - lastStandaloneTime >= STANDALONE_GREEN_MS) {
      standalonePhase = 3;
      lastStandaloneTime = now;
    }
  } else if (standalonePhase == 3) {
    // All Red clearance
    setAllRed();
    if (now - lastStandaloneTime >= STANDALONE_CLEAR_MS) {
      standalonePhase = 0;
      lastStandaloneTime = now;
    }
  }
}
