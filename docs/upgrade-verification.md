# Software verification — 2026-09-17

This record does not sign off the complete requested acceptance criteria.

| Check | Result |
|---|---|
| Baseline Python suite | 43 passed before modifications |
| Updated Python/Qt suite | 106 passed; automated-test-results.xml |
| Android JVM suite | 7 passed; app/build/reports/tests/testDebugUnitTest/index.html |
| Android assembleDebug, JDK 17, offline Gradle cache | BUILD SUCCESSFUL |
| Python controller compile/run, memory GPIO, 20 ticks | Exit 0 |
| Windows source smoke, 1440×900 and 1100×700 | Exit 0; screenshots in docs |
| Final Windows PyInstaller bundle and packaged 1440×900 smoke | Build succeeded; packaged executable exit 0 |
| Twenty deterministic component scenarios | Covered by passing automated suite |
| Continuous desktop ambulance and ordinary traffic | Clearance, removal, restoration and measured occupation passed |
| Signed HIL adapter/controller integration | Passed with memory GPIO; fresh-ID reconfirmation after cancellation covered |
| Hardware monitor isolation and heartbeat loss | Passed; local FSM cannot overwrite hardware state |
| Delayed GPS delivery | Eight-second-old samples rejected; no priority request created |
| Registered turning ambulance | Configured North-to-East GPS path, confirmed entry and correct exit passed |
| Ordinary turning paths | All twelve entry/exit combinations continuous; shared-exit spacing passed |
| Android catalog | Two-junction route ordering, cleared-junction exclusion and configured turn passed |
| Android USB device discovery | No connected devices reported by adb |
| Physical GPIO, actual LED readback, phone road GPS, three-device run | Not verified |

Outputs:

- Android: `android_app/app/build/outputs/apk/debug/app-debug.apk`
- Windows: `dist/upgrade/LifeLane/LifeLane.exe` plus its `_internal` directory
- Tests: `docs/automated-test-results.xml`
- Setup, provisioning, demonstration and remaining gaps: `docs/emergency-way-upgrade.md`
- Changed working-tree inventory, including pre-existing edits: `docs/upgrade-changed-files.md`

Simulation results are not measurements of physical GPIO or public traffic signals.
