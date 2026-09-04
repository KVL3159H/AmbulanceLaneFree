# Testing and verification

## Automated Python suite

```bash
cd /path/to/lifelane
.venv/bin/python -m pytest -q
```

The suite covers cardinal side classification, 0° wrap-around, stale/poor/duplicate GPS, moving away, slow immediate-radius movement, medical/ETA/wait/ID priority ordering, starvation protection, normal timing, entry/recovery clearance, cancellation, GPS loss, maximum green, two conflicting requests, passage, restart all-red initialization, SQLite uniqueness, all four simulated paths, recovery, and the conflict invariant.

For a display-free Qt smoke test:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m raspberry_pi_app.main \
  --headless-smoke-test --database :memory: --screenshot docs/smoke.png
```

## Manual desktop scenario

1. Start the program and confirm all red during initial clearance, then NS green.
2. Press each cardinal simulation button. Confirm the detected side and moving icon.
3. Observe current green → yellow → all red → selected single-side green.
4. Let the icon pass. Confirm two outward samples, recovery yellow/all-red, then normal cycling.
5. Add a second ambulance and confirm the active request is not reversed.
6. Press **GPS loss** during ambulance green. Confirm warning, bounded maximum green, and safe recovery.
7. Cancel a selected emergency during preemption. Confirm yellow/all-red recovery.
8. Deliberately use a test-only conflict injection only in unit tests; confirm `FAIL_SAFE`, all red, and reset latch.

## Android build

```bash
cd android_app
./gradlew assembleDebug
```

The APK is `app/build/outputs/apk/debug/app-debug.apk`. Install on a device and verify permission prompts, the persistent emergency notification, one-to-two-second telemetry in `mosquitto_sub`, live junction status, delivery stop, and cancel stop. The command-line build proves compilation/packaging; real GNSS and handset background-policy behavior still require a physical-device test.
