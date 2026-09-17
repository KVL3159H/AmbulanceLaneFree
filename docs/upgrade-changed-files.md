# Working-tree changed-file inventory

Recorded 2026-09-17. This workspace already contained edits when the upgrade began.
This inventory includes those pre-existing changes; it is not a claim that every diff was authored by this upgrade.
See upgrade-baseline.md for starting findings and emergency-way-upgrade.md for delivered scope.

Git status (M modified, A added, D deleted, ?? untracked):

```text
MM .gitignore
D  LifeLane-debug.apk
 M README.md
 M android_app/app/build.gradle.kts
 M android_app/app/src/main/java/org/lifelane/mobile/EmergencyLocationService.kt
 M android_app/app/src/main/java/org/lifelane/mobile/MainActivity.kt
 M android_app/app/src/main/java/org/lifelane/mobile/MqttGateway.kt
 M android_app/app/src/main/java/org/lifelane/mobile/TripModels.kt
 M android_app/app/src/main/java/org/lifelane/mobile/TripStatusRepository.kt
 M android_app/app/src/main/java/org/lifelane/mobile/TripViewModel.kt
 M android_app/app/src/main/java/org/lifelane/mobile/ui/components/LifeLaneComponents.kt
 M android_app/app/src/main/java/org/lifelane/mobile/ui/components/LiveRouteMapView.kt
 M android_app/app/src/main/java/org/lifelane/mobile/ui/components/RealTimeMapView.kt
 M android_app/app/src/main/java/org/lifelane/mobile/ui/previews/LifeLanePreviews.kt
 M android_app/app/src/main/java/org/lifelane/mobile/ui/theme/Color.kt
 M android_app/app/src/main/java/org/lifelane/mobile/ui/theme/Dimens.kt
 M android_app/app/src/main/java/org/lifelane/mobile/ui/theme/Shape.kt
 M android_app/app/src/main/java/org/lifelane/mobile/ui/theme/Theme.kt
 M android_app/app/src/main/java/org/lifelane/mobile/ui/theme/Type.kt
 M android_app/app/src/main/res/values/colors.xml
 M android_app/app/src/main/res/values/themes.xml
 M config/junction.yaml
 M docs/redesign-verification.md
 M lifelane_windows.spec
 M raspberry_pi_app/communication/mqtt_client.py
 M raspberry_pi_app/core/config.py
 M raspberry_pi_app/core/coordinator.py
 M raspberry_pi_app/core/gps_engine.py
 M raspberry_pi_app/core/models.py
 M raspberry_pi_app/core/passage_detector.py
 M raspberry_pi_app/core/priority_manager.py
 M raspberry_pi_app/core/safety_validator.py
 M raspberry_pi_app/core/signal_controller.py
 M raspberry_pi_app/core/signal_states.py
 M raspberry_pi_app/simulator/gps_simulator.py
 M raspberry_pi_app/ui/information_panel.py
 M raspberry_pi_app/ui/junction_scene.py
 M raspberry_pi_app/ui/main_window.py
 M raspberry_pi_app/ui/pages.py
 M raspberry_pi_app/ui/styles.qss
 M raspberry_pi_app/ui/theme.py
 M scripts/run_broker.py
 M tests/test_gps_engine.py
 M tests/test_integration.py
 M tests/test_passage_detector.py
 M tests/test_priority_manager.py
 M tests/test_signal_controller.py
 M tests/test_ui.py
 M web_app/static/index.html
 M windows_app/main.py
?? android_app/app/src/main/java/org/lifelane/mobile/ApproachTracker.kt
?? android_app/app/src/main/java/org/lifelane/mobile/Protocol.kt
?? android_app/app/src/main/java/org/lifelane/mobile/RoutePlan.kt
?? docs/automated-test-results.xml
?? docs/connected-prototype.md
?? docs/connection-prototype.png
?? docs/emergency-way-upgrade.md
?? docs/packaged-prototype.png
?? docs/scenario-results.json
?? docs/upgrade-baseline.md
?? docs/upgrade-changed-files.md
?? docs/upgrade-state-machines.md
?? docs/upgrade-verification.md
?? docs/upgrade-windows-1100.png
?? docs/upgrade-windows.png
?? raspberry_pi_app/communication/hardware_monitor.py
?? raspberry_pi_app/communication/local_broker.py
?? raspberry_pi_app/communication/request_validator.py
?? raspberry_pi_app/controller_runtime.py
?? raspberry_pi_app/core/event_logger.py
?? raspberry_pi_app/core/gpio_driver.py
?? raspberry_pi_app/core/protocol.py
?? raspberry_pi_app/core/route_geometry.py
?? raspberry_pi_app/core/watchdog.py
?? raspberry_pi_app/requirements-hardware.txt
?? raspberry_pi_app/simulator/scenarios.py
?? raspberry_pi_app/simulator/simulation_adapter.py
?? raspberry_pi_app/simulator/traffic_engine.py
?? raspberry_pi_app/ui/upgrade_pages.py
?? run_connected_prototype.bat
?? scripts/generate_shared_contract.py
?? shared/
?? tests/test_mqtt_connection.py
?? tests/test_upgrade_safety.py
```
