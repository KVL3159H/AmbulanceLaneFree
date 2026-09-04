# LifeLane native UI redesign verification

This record covers the professional UI/UX redesign while retaining the existing GPS assessment, MQTT transport, medical-priority ordering, signal state machine, passage detection and safety invariant.

## Desktop verification commands

Run all Python, integration and Qt UI tests:

```powershell
python -m pytest -q
```

Run the Raspberry Pi application from a Raspberry Pi OS desktop session:

```bash
.venv/bin/python -m raspberry_pi_app.main
```

Capture the two supported verification sizes without a display server:

```powershell
$env:LIFELANE_MQTT_HOST='127.0.0.2'
python -m windows_app.main --headless-smoke-test --database ':memory:' --window-size 1440x900 --screenshot docs/lifelane-redesign-1440x900.png
python -m windows_app.main --headless-smoke-test --database ':memory:' --window-size 1100x700 --screenshot docs/lifelane-redesign-1100x700.png
python -m windows_app.main --headless-smoke-test --database ':memory:' --fullscreen-smoke
```

The smoke flow starts the normal signal animation, injects two explicitly simulated ambulances through the real GPS/coordinator path, exercises queue selection and preemption, and captures the resulting native window. GPS-loss and fail-safe presentation have direct Qt tests in `tests/test_ui.py`.

## Android verification commands

Configure the SDK and broker in `android_app/local.properties`, then build:

```powershell
cd android_app
.\gradlew.bat --no-daemon --console=plain :app:assembleDebug
```

On Linux or macOS use `./gradlew :app:assembleDebug`. The APK output is:

```text
android_app/app/build/outputs/apk/debug/app-debug.apk
```

Android Studio provides four native Compose previews in `LifeLanePreviews.kt`: dark portrait, light portrait, landscape, and 150% font scale. The preview data is visibly marked simulated. Runtime screens retain scrollability for larger system font sizes and all primary controls meet the 48 dp touch-target minimum.

## Recorded result — 4 September 2026

- Python, core integration and Qt UI: **41 passed**.
- Native desktop smoke captures: **1440×900 passed**, **1100×700 passed**.
- Full-screen transition: **passed** through the offscreen smoke entry point.
- Normal-cycle, two-ambulance selection and emergency-preemption path: **passed** through the real coordinator pipeline used by the captures.
- GPS-loss and fail-safe presentation: **passed** through dedicated Qt tests.
- Android `assembleDebug`: **BUILD SUCCESSFUL**.
- Android Lint: **0 errors, 6 warnings**. Five warnings only advertise newer dependency versions; one suggests moving an adaptive icon from its required `-v26` resource folder, which was tested and rejected because AAPT then failed to resolve the launcher resource.
- APK signature: **verified** with Android APK Signature Scheme v2, one debug signer.
- APK metadata: package `org.lifelane.mobile`, minimum SDK 26, target/compile SDK 36, launcher activity `org.lifelane.mobile.MainActivity`.
- Final APK size: **19,544,359 bytes**.
- APK SHA-256: `0E2EDA3103B44EDEB1E71E7AD74EACF3E986BC78F0D7590B11EDED681FA464BE`.

## Safety checks

- UI components display state but do not decide signal safety.
- Manual queue actions cannot select a conflicting green or bypass the controller.
- Timing changes require confirmation and retain the existing signal invariant.
- Android only displays priority granted after the junction reports that the detected approach is green.
- GPS or MQTT loss retains last-known values and removes any implication of a new confirmation.
- All generated desktop and preview data is labeled simulated.
