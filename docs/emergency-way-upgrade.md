# Emergency Way laboratory upgrade

This work extends the existing Kotlin/Compose Android app and shared Python/PySide6
Windows/Pi implementation. Existing hospital lookup, trip storage, local sign-in,
MQTT gateway and SQLite modules remain. The original project had no GPIO driver.
This is a laboratory LED model, not control of unregistered public traffic signals.

## Verification and deliverables

- Before-change findings and build record: `upgrade-baseline.md`.
- Automated test details: `automated-test-results.xml`.
- Final software verification summary: `upgrade-verification.md`.
- Twenty deterministic **component** scenarios: `scenario-results.json` and the
  Windows Scenario Testing page. These are not twenty physical end-to-end trials.
- Protocol source: `shared/protocol.json`; generated Python/Kotlin enums.
- Request/ACK schemas: `shared/priority-request.schema.json`, `priority-ack.schema.json`.
- Junction source: `config/junction.yaml`; generated Android asset `shared/junction.json`;
  format description in `shared/junction.schema.json`.
- Controller, vehicle and approach explanations: `upgrade-state-machines.md`.
- Code changes: `upgrade-changed-files.md`.

## Build and run

Use Python 3.12, the existing requirements, JDK 17 and Android SDK 36.

```powershell
python -m pip install -r requirements.txt
python -m scripts.generate_shared_contract
python -m pytest -q --junitxml=docs/automated-test-results.xml
python -m windows_app.main
python -m PyInstaller --noconfirm --distpath dist/upgrade --workpath build/upgrade lifelane_windows.spec
cd android_app
.\gradlew.bat assembleDebug
```

The Android APK is `android_app/app/build/outputs/apk/debug/app-debug.apk`.
The Windows bundle is `dist/upgrade/LifeLane/LifeLane.exe`; distribute its entire
directory, including `_internal`. The existing root APK is not a reliable marker
of the latest build: use the Gradle output above.

On this workstation Python is supplied by the bundled runtime and dependencies in
`.runtime-packages`; the verification scripts used `PYTHONPATH` to include that
directory. Gradle requires access to `C:/Users/dell8/.gradle`. Initial sandbox cache
lock failures were environmental and were resolved with approved cache access.

After editing the YAML registry or wire enums, run `scripts.generate_shared_contract`
before rebuilding Android. Deploy the same YAML to the Pi. Coordinates in `geometry`
are **local metres, east/north**, relative to `junction.latitude/longitude`. Path
progress increases inbound, through the junction, and outbound. Stop/exit progress
values locate the corresponding cross-sections of each configured path.

Additional registered junctions belong in `config/junctions/*.yaml`, each with a unique
junction ID and controller ID. Generation produces `shared/junctions.json`; Android
orders its supported stop lines along the active route and excludes cleared junctions.
Each Pi runs with its own file using `--config <junction.yaml>`. No additional physical
junction coordinates are fabricated by the generator. The bundled catalog contains
the existing laboratory junction only. Android JVM tests cover a two-junction route.

Ambulances follow the registry's selected path for each inbound approach. To register
a turning movement, supply its continuous path and matching stop/exit progress and
supported-movement entry. The simulator exposes the registered destination exit;
it does not grant an arbitrary unregistered exit. Ordinary vehicles independently
support all three distinct exits with continuous curves and conflict-zone/merge spacing.

## MQTT and device provisioning

The bundled anonymous broker remains useful for local software demonstrations.
Physical mode requires broker credentials and a provisioned device HMAC secret.
Use an isolated laboratory broker with per-device topic ACLs. Enable TLS when using
a shared network; never commit passwords or device secrets.

Controller environment:

```text
LIFELANE_MQTT_HOST=<laboratory broker>
LIFELANE_MQTT_USERNAME=<controller account>
LIFELANE_MQTT_PASSWORD=<controller password>
LIFELANE_MQTT_TLS=true
EMERGENCY_WAY_DEVICE_SECRETS={"AMB-001":"<unique random device secret>"}
```

Set the broker port in `config/junction.yaml` (normally 8883 for TLS). Android's
git-ignored `android_app/local.properties` supports:

```properties
lifelane.mqtt.host=<laboratory broker>
lifelane.mqtt.port=8883
lifelane.mqtt.username=<ambulance account>
lifelane.mqtt.password=<ambulance password>
lifelane.mqtt.tls=true
lifelane.device.secret=<same device secret provisioned for this ambulance>
```

The current APK provisions secrets at build time. This is a lab provisioning
mechanism, not a secure production credential store or replacement for driver
identity verification. A build without a secret sends legacy diagnostic telemetry
but cannot request physical priority. Existing local sign-in remains a prototype.

V2 topics under `lifelane`:

| Topic | Producer | Content |
|---|---|---|
| `ambulance/<id>/telemetry2` | Android | Authenticated GPS telemetry |
| `junction/<id>/priority` | Android | Authenticated priority request |
| `junction/<id>/control` | Android | Authenticated correlated cancellation |
| `junction/<id>/ack` | Pi runtime | Authenticated applied-state acknowledgement |
| `junction/<id>/status` | Pi runtime | Broker-protected heartbeat and lamp snapshot |

Signed messages have `payload` (the exact JSON string) and `signature` (lowercase
hex HMAC-SHA256 over the payload's UTF-8 bytes). Do not reserialize before verifying.
The ACK additionally contains `mode` and canonical `junctionState`. Priority requests
use the GPS acquisition timestamp. Physical control does not consume legacy unsigned
telemetry. Request IDs are persisted for replay protection in physical mode.

An ACK confirms green only after identity, freshness, requested approach, controller
state and all four applied lamp colours match. Android also checks the HMAC and
`mode=HARDWARE`. An ordinary MQTT connection or a sent request never confirms green.

## Raspberry Pi 5

Install on Raspberry Pi OS with the existing project requirements plus:

```bash
python3 -m pip install -r raspberry_pi_app/requirements-hardware.txt
python3 -m raspberry_pi_app.controller_runtime --mode simulation --ticks 100
python3 -m raspberry_pi_app.controller_runtime --mode gpio-test --ticks 1200
python3 -m raspberry_pi_app.controller_runtime --mode physical
```

`simulation` uses memory-backed pins. `gpio-test` uses actual GPIO and the same
normal-cycle FSM for a bounded lamp test; it does not label ACKs as live hardware
priority. `physical` uses actual GPIO plus authenticated requests. The legacy
`raspberry_pi_app.main` entry point still launches the Qt simulator.

The driver explicitly uses GPIO Zero's lgpio backend, rather than silently accepting
a mock pin factory. If the OS requires an explicit gpiochip selection, set
`EMERGENCY_WAY_GPIO_CHIP` to the verified chip number. Pi kernel versions can differ;
do not assume a chip number from an old wiring tutorial. See
[GPIO Zero pin documentation](https://gpiozero.readthedocs.io/en/stable/api_pins.html).

BCM pin assignment (editable in YAML):

| Approach | Red | Yellow | Green |
|---|---:|---:|---:|
| North | 17 | 27 | 22 |
| East | 5 | 6 | 13 |
| South | 19 | 26 | 21 |
| West | 16 | 20 | 12 |

Use individual current-limiting resistors and suitable driver circuitry. Keep the
GPIO model electrically isolated from any mains-powered equipment. Pin readback
checks logic state, not LED current, a broken wire, or a stuck external transistor.
The software watchdog cannot protect against power loss, SIGKILL, kernel hangs or
hardware output failure. An independent hardware watchdog/output-enable interlock
is required to guarantee electrical fail-safe behavior under those faults.

Startup initializes and verifies all-red. Physical normal cycling waits for broker
initialization. Faults latch; restart through all-red only after correcting the
cause. The default is single-approach N → E → S → W. Paired operation requires both
`normal_cycle_mode: PAIRED` and `paired_movements: true` for a verified compatible model.

## Demonstration

1. Start Windows and choose Simulation. Confirm the visible simulation label.
2. Observe ordinary vehicles braking before red, moving on green and leaving only
   after their rear bumper passes the exit boundary. Compare the queue and wait metrics.
3. Add a North ambulance. Watch approach confirmation, yellow, all-red, North green,
   repeated entry/exit confirmation, recovery yellow/all-red, and normal restoration.
4. Add a conflicting ambulance and repeat with different medical priorities.
5. Pause, step one tick, resume, and change simulation speed. GPS-loss testing and
   the twenty component scenarios are available from the UI.
6. Export filtered CSV/JSON from Event Logs. Scenario reports explicitly identify
   their component-simulation scope.
7. For a physical trial, configure the actual laboratory geometry, broker ACLs,
   device secrets, pin wiring and GPS time synchronization. Run the Pi GPIO test
   before physical mode. Install the newly built APK and grant precise location.
8. Start an emergency trip whose measured route crosses the registered supported
   straight movement. Android fetches OSRM route geometry; unavailable or unsupported
   routes cannot trigger hardware priority. OSRM's
   [route API](https://project-osrm.org/docs/v5.22.0/api/) supplies the measured polyline.
9. In Windows choose Monitor Raspberry Pi. Only actual controller snapshots drive
   the monitor; heartbeat loss freezes ordinary-vehicle simulation and labels the
   lamps as last known. Verified hardware grants require the matching request to
   have been observed and its secret provisioned in the monitor environment.
10. For HIL, provision unique SIM-NORTH / SIM-EAST / SIM-SOUTH / SIM-WEST secrets
    in both Windows and Pi environments and retain these IDs in the allowlist.
    Choose Hardware-in-the-loop, wait for a real Pi heartbeat, then add an ambulance.
    GPS and requests are signed; actual Pi outputs determine vehicle movement. HIL
    runs at real time and never uses a local controller grant.
11. The ambulance dialog offers GPS noise and network delivery delay. Fault controls
    support stopping, a pre-stop-line U-turn, GPS loss, MQTT loss/restore and software
    controller faults. Recover the fail-safe latch using Controlled reset.
12. Event Logs exports a JSON test report for an exact trip ID. Missing clearance or
    restoration produces INCOMPLETE, not PASS. Metrics show measured travel, green
    delay and junction occupation when the events exist; absent values remain null.
    Printable HTML reports are also available. Open the exported file in a browser to
    print. Stop safely completes clearance before holding all-red; Pause freezes only
    software simulation time. Hardware monitoring never pauses the actual Pi controller.

## Remaining acceptance gaps — not a complete acceptance sign-off

- Physical Pi 5 GPIO, phone GPS on a real route, electrical fault recovery, TLS broker
  provisioning and a three-device end-to-end run have not been verified on hardware.
- The shipped registry contains **one laboratory junction with straight ambulance paths**.
  Multi-junction route ordering and configured ambulance turns are implemented and
  component-tested, but additional physical routes require actual registered geometry.
  There is one selected ambulance path per inbound approach in each configuration.
  Unsupported movements cannot receive priority. Android cancels after three departing-route samples before
  the stop line, waits out the configured recovery bound, then obtains a new route and
  request ID. This conservative reroute path needs a physical GPS trial. The U-turn
  scenario reverses along its approach path; it is not a lateral dynamics model.
- HIL request generation and authenticated controller acceptance/cancellation are
  component-tested. Actual Pi/broker HIL testing remains required. The twenty predefined
  scenarios are component tests, not full network/hardware trials.
- The desktop shows observed request-to-ACK delay, not an invented network RTT. These
  observer measurements include controller processing and cannot isolate network transit
  time. Ordinary turning paths, JSON/printable trip reports and measured core ambulance
  metrics are implemented. The canvas is a stylized four-way laboratory model, not a
  lane-level road survey or a high-fidelity lateral-dynamics simulator.
- Shared enums and configuration generation are present. Some legacy view models and
  internal controller phase names remain as adapters; not every enum state is a separately
  persisted transition. The request replay store is local to one controller deployment.
- Android OSRM routing needs network access and uses a public demonstration endpoint;
  select a provisioned routing service before any sustained deployment.
- Software and logic-state verification do not certify an electrical fail-safe system.

These gaps are explicit so a successful build or passing component suite is not
mistaken for fulfillment of the complete requested acceptance criteria.
