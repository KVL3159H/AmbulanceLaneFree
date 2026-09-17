# Emergency Way upgrade baseline — 2026-09-16

Inspected existing Android Kotlin/Compose foreground fused-location service, HiveMQ
gateway, StateFlow trip models/viewmodel, hospital repository and map components;
Python/PySide6 Windows/Pi entry points, coordinator, GPS, passage, queue, signal FSM,
Paho adapter, SQLite persistence, simulator, UI, configuration and tests.
Existing uncommitted changes are preserved. No existing GPIO implementation exists.

## Before-modification verification

- Python: bundled Python 3.12 with `.runtime-packages`; `pytest -q`: **43 passed**.
- Windows: PyInstaller spec built successfully into `dist/baseline/LifeLane`.
- Pi: `compileall -q raspberry_pi_app` passed on Windows; not a Pi hardware test.
- Android: `assembleDebug --offline` passed with JDK 17 and existing Gradle cache.
  Initial attempts failed because Gradle defaulted to `C:/.gradle`, then the sandbox
  denied cache lock writes. Approved cache access resolved this environment issue.

## Existing defects recorded before corrections

1. Android invents an unregistered midpoint junction for distant GPS locations.
2. Approach classification uses one radial bearing; stationary/immediate-radius
   exceptions allow unconfirmed priority. Histories mix trips of one ambulance.
3. GPS permits arbitrary AMB/SIM/DRV/EMG prefixes, unrealistic speed, and timestamp
   reversal with a new sequence. Invalid packets refresh the controller GPS clock.
4. Distance means centre radius, not route progress to a configured stop line.
5. Passage can finish inside the exit radius; entry requires only one point.
6. Completed/expired trips can requeue; waiting requests do not expire at selection.
7. ACK lacks controller identity/applied lamps/mode; Android accepts any junction
   and can overwrite confirmed progress on the next GPS update.
8. Ordinary traffic engine, physical GPIO interlock/watchdog and scenario runner absent.
9. Blue desktop/Android themes and Android dark mode differ from requested design.
10. Existing tests encode one/two-sample grants and centre-radius passage.
11. Anonymous local broker and prototype login are not authenticated device identity.
12. No shared route registry, protocol schema or all-three-application state contract.

This is an isolated laboratory LED prototype, not public traffic-signal control.
