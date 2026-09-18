/*
 * =====================================================================================
 * LifeLane ESP32 Hardware Traffic Signal Controller
 * Dual Control: USB Data Cable (PC / Raspberry Pi) + LoRa Wireless Receiver
 * =====================================================================================
 * Pin Configuration & Hardware Assignment:
 *   LoRa Module (433 MHz SX1278):
 *     - SCK:  18
 *     - MISO: 19
 *     - MOSI: 23
 *     - SS:   27
 *     - RST:  25
 *     - DIO0: 26
 *
 *   Signal LED Pins (Active HIGH: RED = HIGH/GRN = LOW for STOP):
 *     - North: Red = 2,  Green = 5
 *     - South: Red = 12, Green = 14
 *     - East:  Red = 15, Green = 22
 *     - West:  Red = 32, Green = 13
 *
 * Workflow Modes:
 *   1. USB APPLICATION MODE (Connected to LifeLane GUI via USB Data Cable):
 *      - Full real-time synchronization with LifeLane simulator.
 *      - Instant corridor clearing when an ambulance approaches.
 *   2. LORA WIRELESS PRIORITY MODE:
 *      - Receives wireless priority triggers from ambulance transmitter.
 *   3. AUTONOMOUS FAIL-SAFE / STANDALONE MODE:
 *      - Cycles 4-way traffic if USB is unplugged and no LoRa packet.
 * =====================================================================================
 */

#include <SPI.h>
#include <LoRa.h>

// -------- LoRa Pins & Configuration --------
#define LORA_SCK  18
#define LORA_MISO 19
#define LORA_MOSI 23
#define LORA_SS   27
#define LORA_RST  25
#define LORA_DIO0 26

String unitID = "N02";   // Change to unit ID (e.g. N01, N02)
const long LORA_FREQUENCY = 433E6;

// -------- Signal Pins --------
// North (Approach 1 / S1)
#define N_RED 2
#define N_GRN 5

// South (Approach 2 / S2)
#define S_RED 12
#define S_GRN 14

// East (Approach 3 / S3)
#define E_RED 15
#define E_GRN 22

// West (Approach 4 / S4)
#define W_RED 32
#define W_GRN 13

// Onboard Status LED (Blinks on packet activity)
#define STATUS_LED 2

// -------- Timing Configuration --------
const unsigned long STANDALONE_GREEN_TIME = 6000;   // 6 seconds per approach in standalone
const unsigned long STANDALONE_CLEAR_TIME = 1500;   // 1.5 seconds all-red clearance
const unsigned long LORA_OVERRIDE_TIMEOUT = 5000;   // LoRa priority hold time
const unsigned long USB_WATCHDOG_TIMEOUT  = 3500;   // Timeout before falling back to standalone

// -------- Operating Modes --------
enum SystemMode {
  MODE_USB_APP,      // Actively controlled by LifeLane software over USB Serial
  MODE_LORA_PRIORITY,// Overridden by wireless LoRa ambulance beacon
  MODE_STANDALONE    // Autonomous 4-way rotation when disconnected
};

SystemMode currentMode = MODE_STANDALONE;

int standaloneSignal = 0; // 0=North, 1=South, 2=East, 3=West
unsigned long lastStandaloneCycle = 0;
bool standaloneInClearance = false;

unsigned long lastUsbPacketTime = 0;
unsigned long lastLoraReceiveTime = 0;
String loraCommand = "";
String serialBuffer = "";

bool loraAvailable = false;

// =====================================================================================
// Hardware Actuation Helper Functions
// =====================================================================================

void allRed() {
  digitalWrite(N_RED, HIGH); digitalWrite(N_GRN, LOW);
  digitalWrite(S_RED, HIGH); digitalWrite(S_GRN, LOW);
  digitalWrite(E_RED, HIGH); digitalWrite(E_GRN, LOW);
  digitalWrite(W_RED, HIGH); digitalWrite(W_GRN, LOW);
}

void setApproachGreen(int dir) {
  allRed();
  switch (dir) {
    case 0: // North
      digitalWrite(N_RED, LOW);
      digitalWrite(N_GRN, HIGH);
      break;
    case 1: // South
      digitalWrite(S_RED, LOW);
      digitalWrite(S_GRN, HIGH);
      break;
    case 2: // East
      digitalWrite(E_RED, LOW);
      digitalWrite(E_GRN, HIGH);
      break;
    case 3: // West
      digitalWrite(W_RED, LOW);
      digitalWrite(W_GRN, HIGH);
      break;
  }
}

void setApproachState(int dir, bool isGreen, bool isYellow) {
  // Handles individual approach signals from LifeLane
  int pinRed = (dir == 0) ? N_RED : (dir == 1) ? S_RED : (dir == 2) ? E_RED : W_RED;
  int pinGrn = (dir == 0) ? N_GRN : (dir == 1) ? S_GRN : (dir == 2) ? E_GRN : W_GRN;

  if (isGreen) {
    digitalWrite(pinRed, LOW);
    digitalWrite(pinGrn, HIGH);
  } else if (isYellow) {
    // For 2-pin LEDs (Red+Green), Amber is indicated by both or quick pulse
    digitalWrite(pinRed, HIGH);
    digitalWrite(pinGrn, HIGH);
  } else {
    // Red
    digitalWrite(pinRed, HIGH);
    digitalWrite(pinGrn, LOW);
  }
}

// Power-on self test to verify all 8 LED channels
void runSelfTest() {
  Serial.println(F("[LIFELANE] Running LED Self-Test..."));
  allRed();
  delay(600);

  // Cycle each approach to Green
  for (int i = 0; i < 4; i++) {
    setApproachGreen(i);
    delay(400);
  }
  allRed();
  delay(400);
  Serial.println(F("[LIFELANE] Self-Test complete. Ready."));
}

// =====================================================================================
// USB Serial Parser (LifeLane Application Workflow)
// =====================================================================================

void processSerialLine(String line) {
  line.trim();
  if (line.length() == 0) return;

  // Check if it's a LifeLane JSON packet
  if (line.indexOf("{") >= 0 && line.indexOf("}") >= 0) {
    lastUsbPacketTime = millis();
    currentMode = MODE_USB_APP;

    bool n_grn = (line.indexOf("\"NORTH\":\"GREEN\"") >= 0);
    bool n_yel = (line.indexOf("\"NORTH\":\"YELLOW\"") >= 0);

    bool s_grn = (line.indexOf("\"SOUTH\":\"GREEN\"") >= 0);
    bool s_yel = (line.indexOf("\"SOUTH\":\"YELLOW\"") >= 0);

    bool e_grn = (line.indexOf("\"EAST\":\"GREEN\"") >= 0);
    bool e_yel = (line.indexOf("\"EAST\":\"YELLOW\"") >= 0);

    bool w_grn = (line.indexOf("\"WEST\":\"GREEN\"") >= 0);
    bool w_yel = (line.indexOf("\"WEST\":\"YELLOW\"") >= 0);

    // Apply exact states sent by LifeLane coordinator
    setApproachState(0, n_grn, n_yel);
    setApproachState(1, s_grn, s_yel);
    setApproachState(2, e_grn, e_yel);
    setApproachState(3, w_grn, w_yel);

    // ACK back to application
    Serial.println(F("ACK:OK"));
    return;
  }

  // Also support compact commands: SIG:S1, SIG:S2, SIG:S3, SIG:S4, or SIG:ALLRED
  if (line.startsWith("SIG:")) {
    lastUsbPacketTime = millis();
    currentMode = MODE_USB_APP;

    if (line.indexOf("S1") >= 0 || line.indexOf("NORTH") >= 0) {
      setApproachGreen(0);
    } else if (line.indexOf("S2") >= 0 || line.indexOf("SOUTH") >= 0) {
      setApproachGreen(1);
    } else if (line.indexOf("S3") >= 0 || line.indexOf("EAST") >= 0) {
      setApproachGreen(2);
    } else if (line.indexOf("S4") >= 0 || line.indexOf("WEST") >= 0) {
      setApproachGreen(3);
    } else if (line.indexOf("ALLRED") >= 0) {
      allRed();
    }
    Serial.println(F("ACK:SIG"));
  }
}

// =====================================================================================
// LoRa RF Receiver Handler
// =====================================================================================

void checkLoRaPacket() {
  if (!loraAvailable) return;

  int packetSize = LoRa.parsePacket();
  if (!packetSize) return;

  String rx = "";
  while (LoRa.available()) {
    rx += (char)LoRa.read();
  }
  rx.trim();
  rx.replace("\n", "");
  rx.replace("\r", "");

  Serial.print(F("[LORA-RX] Raw: "));
  Serial.println(rx);

  int sep = rx.indexOf('-');
  if (sep != -1) {
    String target = rx.substring(0, sep);
    String cmd = rx.substring(sep + 1);
    target.trim();
    cmd.trim();

    if (target == unitID || target == "ALL") {
      loraCommand = cmd;
      currentMode = MODE_LORA_PRIORITY;
      lastLoraReceiveTime = millis();

      Serial.print(F("[LORA-PRIORITY] Target: "));
      Serial.print(target);
      Serial.print(F(" -> Action: "));
      Serial.println(cmd);

      // Notify connected LifeLane application about wireless trigger
      Serial.print(F("LORA_TRIGGER:"));
      Serial.println(cmd);
    } else {
      Serial.println(F("[LORA] Ignored (ID mismatch)"));
    }
  }
}

// =====================================================================================
// Setup & Main Loop
// =====================================================================================

void setup() {
  Serial.begin(115200);
  delay(100);

  // Configure output pins for all 4 approaches
  pinMode(N_RED, OUTPUT); pinMode(N_GRN, OUTPUT);
  pinMode(S_RED, OUTPUT); pinMode(S_GRN, OUTPUT);
  pinMode(E_RED, OUTPUT); pinMode(E_GRN, OUTPUT);
  pinMode(W_RED, OUTPUT); pinMode(W_GRN, OUTPUT);

  runSelfTest();

  // Initialize LoRa SPI
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  if (LoRa.begin(LORA_FREQUENCY)) {
    loraAvailable = true;
    Serial.println(F("[LORA] Receiver Ready at 433 MHz"));
  } else {
    loraAvailable = false;
    Serial.println(F("[LORA] Warning: LoRa init failed. USB Serial active."));
  }

  serialBuffer.reserve(128);
  lastStandaloneCycle = millis();
}

void loop() {
  // 1. Process USB Serial commands from LifeLane Application
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialBuffer.length() > 0) {
        processSerialLine(serialBuffer);
        serialBuffer = "";
      }
    } else {
      serialBuffer += c;
      if (serialBuffer.length() > 200) serialBuffer = "";
    }
  }

  // 2. Check for wireless LoRa packets
  checkLoRaPacket();

  unsigned long now = millis();

  // 3. Mode Evaluation & Execution
  if (currentMode == MODE_LORA_PRIORITY) {
    // Wireless priority active
    if (now - lastLoraReceiveTime <= LORA_OVERRIDE_TIMEOUT) {
      if (loraCommand.indexOf("SIG:S1") >= 0) setApproachGreen(0);      // North
      else if (loraCommand.indexOf("SIG:S2") >= 0) setApproachGreen(1); // South
      else if (loraCommand.indexOf("SIG:S3") >= 0) setApproachGreen(2); // East
      else if (loraCommand.indexOf("SIG:S4") >= 0) setApproachGreen(3); // West
      return;
    } else {
      // LoRa timeout elapsed
      Serial.println(F("[LORA] Priority timeout elapsed. Returning to application/normal cycle."));
      currentMode = (now - lastUsbPacketTime < USB_WATCHDOG_TIMEOUT) ? MODE_USB_APP : MODE_STANDALONE;
      allRed();
    }
  }

  if (currentMode == MODE_USB_APP) {
    // Active USB connection from LifeLane
    if (now - lastUsbPacketTime > USB_WATCHDOG_TIMEOUT) {
      // USB cable unplugged or LifeLane stopped
      Serial.println(F("[WATCHDOG] USB disconnected. Switching to autonomous cycle."));
      currentMode = MODE_STANDALONE;
      lastStandaloneCycle = now;
      standaloneInClearance = false;
      allRed();
    }
    // In USB mode, states are driven directly by processSerialLine()
    return;
  }

  // 4. Autonomous Standalone Cycle (when USB is not connected)
  if (currentMode == MODE_STANDALONE) {
    if (standaloneInClearance) {
      if (now - lastStandaloneCycle >= STANDALONE_CLEAR_TIME) {
        standaloneInClearance = false;
        lastStandaloneCycle = now;
        standaloneSignal = (standaloneSignal + 1) % 4;
        setApproachGreen(standaloneSignal);
      }
    } else {
      if (now - lastStandaloneCycle >= STANDALONE_GREEN_TIME) {
        standaloneInClearance = true;
        lastStandaloneCycle = now;
        allRed();
      }
    }
  }
}
