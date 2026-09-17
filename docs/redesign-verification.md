# LifeLane Android product redesign and verification

## Product and architecture audit

### Current problems found

The previous Android flow was a linear collection of large, independently styled screens. It duplicated medical priority and condition, had no post-login product shell, exposed broker configuration to drivers, used invented vehicle registrations, and repeated route status across headers, cards, and maps. The hospital experience was list-first, the sample fallback was presented like live data, and zero-distance values could reach the UI. GPS and MQTT status were also calculated from free-form strings in several screens.

Most importantly, the old UI inferred a green-light grant from a selected request, MQTT connectivity, and a green signal string. Those observations did not prove that the Raspberry Pi response belonged to the current request. The controller payload also lacked a request identifier needed for safe correlation.

### Improved screen hierarchy

`Driver sign-in → Select ambulance → Home → Patient information → Hospital map → Route review → Active emergency → Completion summary`

Home, Map, Trips, and Settings form the post-login bottom navigation. Navigation is hidden during authentication, trip setup, and the active emergency so the primary task stays clear.

### Visual direction

LifeLane uses a “Medical Emergency Command” system: calm neutral surfaces, navigation blue for ordinary actions, teal for safe operational progress, amber for degraded states, and red only for critical, failed, destructive, or medical-critical meaning. Cards use 16 dp corners, 16 dp internal spacing, 20 dp screen margins, and controls meet a 48 dp touch target. Roboto/system typography follows a compact 12–30 sp hierarchy.

Light tokens: background `#F8FAFC`, surface `#FFFFFF`, primary text `#0F172A`, secondary text `#64748B`, border `#E2E8F0`, navigation `#2563EB`, medical teal `#0F9D8A`, critical `#DC2626`, warning `#D97706`.

Dark tokens: background `#07111F`, surface `#111C2E`, raised surface `#172337`, primary text `#F8FAFC`, secondary text `#94A3B8`, border `#293548`, navigation `#60A5FA`, medical teal `#2DD4BF`, critical `#F87171`, warning `#FBBF24`.

### Reusable components

The implementation centralizes the top bar, primary and destructive actions, status pills, medical-priority cards, condition selectors, hospital and metric cards, GPS/MQTT indicators, junction progress, map surfaces, loading/empty/error states, and confirmation sheets. Material 3 supplies focus, disabled, pressed, and accessibility behavior.

### Screen-by-screen changes

- Sign-in is compact, includes PIN visibility and inline errors, and no longer exposes the broker or claims unsupported encryption.
- Ambulance selection uses configured prototype identity (`AMB-001`) and requires an explicit Continue action.
- Home summarizes the selected ambulance, real GPS state, real controller state, hospitals, and the primary trip action.
- Patient priority and reported condition are one step; neither is preselected and no patient name is collected.
- Hospital selection is map-first, keeps the list available, labels demo data explicitly, and renders unavailable distances honestly.
- Route review uses plain language and shows actual readiness states rather than promising a connection.
- Active navigation is map-dominant, formats ETA in minutes and distance in metres/kilometres, and uses one typed progress state.
- Trip history and completion summaries omit patient identity and report operational interruption counts.
- Settings separates appearance and status from PIN-protected prototype controls and explicit demo mode.

### Safety and state changes

The Android service now includes request, trip, ambulance, destination, route, GPS, approach, and junction identifiers in telemetry. “Priority granted” is possible only after a recent acknowledgement whose schema, request ID, trip ID, ambulance ID, junction ID, and approach all match; the controller must report an accepted ACTIVE request in `AMBULANCE_GREEN` or `PASSAGE_MONITORING`. A disconnect retains the last confirmed state and explicitly says priority is not confirmed.

GPS now has typed permission, locating, accurate, low-accuracy, last-known, unavailable, and stopped states. Impossible jumps are ignored, stale/last-known data is not labeled live, and the first valid fix updates hospital distances. MQTT uses one typed connection state. The existing controller continues to enforce medical priority, ETA, distance, waiting-time ordering, safe yellow/all-red transitions, passage detection, timeout recovery, and starvation protection.

The map reports resource failures visibly, provides Retry map, and leaves the hospital list usable. The existing map implementation uses OpenStreetMap/Leaflet; it does not require or silently pretend to use a Google Maps key.

## Configuration

Create `android_app/local.properties` (never commit secrets):

```properties
sdk.dir=C:\\Users\\you\\AppData\\Local\\Android\\Sdk
lifelane.mqtt.host=192.168.1.42
lifelane.mqtt.port=1883
lifelane.mqtt.username=
lifelane.mqtt.password=
```

The phone and Raspberry Pi must share a private network. Configure the Pi junction coordinates, authorized ambulance IDs, safe timing plan, detection radius, and MQTT topic prefix in `config/config.yaml`. Keep device clocks synchronized because acknowledgements older than ten seconds are rejected.

Android requests foreground precise location during setup and starts the location foreground service only for an active trip. On Android 13+, allow notifications so the required ongoing service notification is visible. If a device vendor throttles location, exclude LifeLane from battery optimization only for the controlled research test.

Demo hospitals are off by default. Unlock Developer Settings with the laboratory developer PIN and explicitly enable Demo hospital mode. The UI then labels every result as demo data and calculates geometric distance from the valid or configured simulated origin.

## Verification — 14 September 2026

- Android `assembleDebug`: **passed**.
- Android `testDebugUnitTest`: **passed** (`NO-SOURCE`; no Android unit-test sources currently exist).
- Android `lintDebug`: **passed** (no blocking lint findings).
- Raspberry Pi core/controller suite: **36 passed** (GPS, passage, priority, side detection, signal controller, integration, and database tests).
- Android APK output: `android_app/app/build/outputs/apk/debug/app-debug.apk`.

Qt UI tests were not run in this pass because the isolated verification runtime did not include PySide6/pytest-qt. Production road-signal integration remains explicitly outside this laboratory prototype.

## Responsive screen-layer revision — 15 September 2026

The Android `MainActivity` screen layer was replaced to remove the remaining chat/delivery-app visual language and fixed-height phone assumptions. Compact phones use 12–16 dp adaptive margins; larger phones and tablets use wider margins and a 1080 dp content ceiling. Hospital discovery becomes a vertically split map/list workspace on phones and a side-by-side map/list workspace from 760 dp. Home metrics become a two-column grid from 700 dp. Active navigation gives remaining height to the map and limits the status sheet to 58% of the screen with internal scrolling for landscape and large-font accessibility.

Map containers now honor parent constraints instead of forcing a 240 dp height. The route overlay receives an explicit validated-priority flag, so a green signal string alone can never produce the “Priority confirmed” presentation.

Revision verification: Android `assembleDebug`, `testDebugUnitTest`, and `lintDebug` all completed successfully.
