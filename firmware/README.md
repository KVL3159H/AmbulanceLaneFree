# LifeLane ESP32 Hardware Traffic Signal Integration

This directory contains the firmware and wiring specifications to connect physical 3D-printed traffic light posts (such as your yellow junction prototype) to LifeLane via a standard USB data cable.

---

## 1. Prototype Overview & Features

- **Direct Plug-and-Play USB Integration**: LifeLane automatically probes and connects to your ESP32 on **`COM5`** (Windows) or **`/dev/ttyUSB0`** (Raspberry Pi / Linux) at **115200 baud**.
- **Synchronized Signal Control**: Physical LEDs update in real-time with the software cycle:
  - **Normal Cycle**: Alternate North/South and East/West phases with standard Green → Yellow → All-Red clearance.
  - **Ambulance Preemption**: When an ambulance approaches, the corresponding approach immediately switches to physical GREEN, conflicting faces turn RED, and the optional siren sounds!
- **Power-On Self-Test**: Cycles through RED → YELLOW → GREEN for 1.5s on boot so you can instantly verify all wiring.
- **Fail-Safe Watchdog**: If the USB cable is unplugged or the software stops, the ESP32 safely switches to blinking amber after 8 seconds.

---

## 2. Pin Mapping (ESP32 Dev Board)

The pins are configured at the top of [`esp32_traffic_light.ino`](esp32_traffic_light/esp32_traffic_light.ino) and can be adjusted if your prototype is wired differently:

| Signal Function | ESP32 GPIO Pin | Description |
| :--- | :---: | :--- |
| **Approach 1 - Red LED** (North/South) | **GPIO 23** | Top Red LED on front face |
| **Approach 1 - Yellow LED** (North/South) | **GPIO 22** | Middle Yellow LED on front face |
| **Approach 1 - Green LED** (North/South) | **GPIO 21** | Bottom Green LED on front face |
| **Approach 2 - Red LED** (East/West) | **GPIO 19** | Top Red LED on side face |
| **Approach 2 - Yellow LED** (East/West) | **GPIO 18** | Middle Yellow LED on side face |
| **Approach 2 - Green LED** (East/West) | **GPIO 5** | Bottom Green LED on side face |
| **Optional Siren / Buzzer** | **GPIO 4** | Active buzzer for ambulance preemption sound |
| **Status / Heartbeat LED** | **GPIO 2** | Built-in blue LED on ESP32 DevKit |
| **Ground (GND)** | **GND** | Connect to cathode (-) of all LEDs via 220Ω-330Ω resistors |

> [!TIP]
> If your LEDs share a positive VCC line instead of GND (Common Anode), simply change `#define LED_ACTIVE_HIGH true` to `false` in line 28 of the sketch.

---

## 3. How to Flash the ESP32

1. Open **Arduino IDE** (or VS Code with PlatformIO).
2. Install the ESP32 board definitions if you haven't already:
   - In Arduino IDE: `Tools` → `Board` → `Boards Manager...` → Search for `esp32` by Espressif Systems and click **Install**.
3. Open [`firmware/esp32_traffic_light/esp32_traffic_light.ino`](esp32_traffic_light/esp32_traffic_light.ino).
4. Connect your prototype via the USB data cable.
5. In Arduino IDE:
   - Select Board: **ESP32 Dev Module** (or **DOIT ESP32 DEVKIT V1**).
   - Select Port: **COM5** (or the port assigned to the Silicon Labs CP210x / CH340 chip).
   - Upload Speed: **115200** or **921600**.
6. Click **Upload**.
7. Once uploaded, the prototype will run its startup self-test (cycling Red → Yellow → Green).

---

## 4. Running the Complete System

Simply run LifeLane normally:

### On Windows:
```powershell
.venv\Scripts\python.exe -m raspberry_pi_app.main
```
or
```cmd
run_windows.bat
```

### On Raspberry Pi:
```bash
.venv/bin/python -m raspberry_pi_app.main
```

### What You Will See:
1. LifeLane's top header bar will display the new badge: **`ESP32  COM5`** in **Green**.
2. As the simulated junction cycles, the LEDs on your yellow 3D-printed post will physically change in exact real-time synchronization with the on-screen graphics.
3. When you trigger an ambulance (or simulated emergency trip), the post will immediately grant physical green to that corridor!
