# LifeLane ESP32 Hardware Traffic Signal Integration (LoRa + USB Sync)

This directory contains the firmware and pinout specification for your 3D-printed traffic light post prototype.

---

## 1. Pin Configuration (Configured to Your Hardware)

The firmware in [`esp32_traffic_light.ino`](esp32_traffic_light/esp32_traffic_light.ino) is configured with your exact hardware connections:

### 4-Way Traffic Signal LEDs:
| Approach | Direction | Red LED Pin | Green LED Pin | Logic |
| :--- | :--- | :---: | :---: | :--- |
| **Approach 1** | **North** | **GPIO 2** | **GPIO 5** | Active HIGH (`RED=HIGH, GRN=LOW` = Stop; `RED=LOW, GRN=HIGH` = Go) |
| **Approach 2** | **South** | **GPIO 12** | **GPIO 14** | Active HIGH |
| **Approach 3** | **East** | **GPIO 15** | **GPIO 22** | Active HIGH |
| **Approach 4** | **West** | **GPIO 32** | **GPIO 13** | Active HIGH |

### LoRa Module (SX1278 - 433 MHz):
| LoRa Pin | ESP32 Pin | Description |
| :--- | :---: | :--- |
| **SCK** | **GPIO 18** | SPI Clock |
| **MISO** | **GPIO 19** | SPI Master In / Slave Out |
| **MOSI** | **GPIO 23** | SPI Master Out / Slave In |
| **NSS / CS** | **GPIO 27** | Chip Select |
| **RST** | **GPIO 25** | Reset |
| **DIO0** | **GPIO 26** | Interrupt Request |

---

## 2. Integrated Workflow (LifeLane Application + LoRa)

The ESP32 firmware dynamically handles three modes:

1. **USB Application Mode (LifeLane Desktop / Raspberry Pi)**:
   - When the USB cable is plugged in and LifeLane is running, the app automatically connects on **`COM5`** at **115200 baud**.
   - LifeLane sends real-time signal states (North, South, East, West) and emergency preemption status.
   - The physical LEDs on your prototype switch in lockstep with the software GUI.
   - When an ambulance approaches an approach (e.g. North), LifeLane triggers preemption and the ESP32 locks that direction to **GREEN** while keeping all conflicting approaches at **RED**.

2. **LoRa Wireless Priority Mode**:
   - The SX1278 radio constantly listens at **433 MHz**.
   - When a priority packet matching your unit ID (`N02-SIG:S1`, `N02-SIG:S2`, `N02-SIG:S3`, or `N02-SIG:S4`) is received, the ESP32 grants immediate physical Green priority to that direction for 5 seconds and notifies LifeLane over Serial (`LORA_TRIGGER:...`).

3. **Autonomous Standalone Mode (Fail-Safe)**:
   - If the USB data cable is disconnected and no wireless LoRa signal is active, the ESP32 autonomously operates a safe 4-way traffic rotation (6s Green, 1.5s All-Red clearance per approach).

---

## 3. How to Flash the ESP32

1. Open **Arduino IDE**.
2. Make sure you have installed the required libraries:
   - **LoRa** library by Sandeep Mistry (`Sketch` → `Include Library` → `Manage Libraries...` → search `LoRa`).
3. Open [`firmware/esp32_traffic_light/esp32_traffic_light.ino`](esp32_traffic_light/esp32_traffic_light.ino).
4. Connect your prototype via the USB data cable.
5. In Arduino IDE:
   - Select Board: **ESP32 Dev Module** (or **DOIT ESP32 DEVKIT V1**).
   - Select Port: **COM5** (or detected port).
   - Upload Speed: **115200** or **921600**.
6. Click **Upload** (➡️).
7. On boot, the post will run a quick self-test cycling each direction to Green.

---

## 4. Running the Full System

Run the LifeLane desktop application:

```powershell
.venv\Scripts\python.exe -m raspberry_pi_app.main
```
or via the batch file:
```cmd
run_windows.bat
```

The top bar will show **`ESP32  COM5`** in **Green**, and all physical LEDs will actuate in real-time according to the application state!
