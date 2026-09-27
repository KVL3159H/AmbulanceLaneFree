# Connected Windows and Android prototype

1. Run `run_connected_prototype.bat`, or open `dist/connected-prototype/LifeLane/LifeLane.exe`. Keep the entire LifeLane folder together; the executable needs `_internal`.
2. Install the updated root `LifeLane-debug.apk` on the phone.
3. Put the phone and PC on the same Wi-Fi. Open Windows LifeLane Settings to see the PC addresses. The Wi-Fi address on this build machine was `10.18.230.208` on 16 September 2026; it can change.
4. Open Android LifeLane Settings → Connect to Windows. Enter the PC address and port `1883`, then Save connection. You do not need to rebuild the APK when the address changes.
5. Keep the desktop in Live mobile GPS mode. Select AMB-001 through AMB-004 in Android, allow precise location, and start a trip. The desktop receives GPS and returns correlated request acknowledgements.

Windows automatically starts the bundled LAN broker for a localhost configuration without credentials/TLS. If a broker is already listening, it is reused. A remote/authenticated broker remains externally managed. The bundled broker is for an isolated prototype LAN.

If Windows asks about network access, allow the application on the private network used by your phone. The network must permit device-to-device connections and TCP port 1883; guest Wi-Fi may isolate clients. Desktop Settings lists candidate adapters, so choose the address of the adapter shared with the phone. Do not enter localhost on a physical phone.

A broker connection alone does not mean priority was granted. Accurate GPS, an authorized ambulance ID, the configured junction coordinates, approach direction, and activation distance determine eligibility. The demo junction defaults to 9.451500, 77.553500; configure it for your demonstration location. Built-in simulation disconnects mobile MQTT until Live mobile GPS is selected again.

Verification: Android `assembleDebug --offline`; Python unit/UI tests plus TCP integration tests covering telemetry, correlated acknowledgement, cancellation, existing-broker reuse, shutdown with a connected client, and restart; Windows offscreen launch and screenshot. No physical Android phone was connected during verification, so handset GPS, LAN firewall traversal, and on-device UI remain to be verified.

The verification suite passed 43 tests. Packaging excludes an incompatible Python-runtime ICU DLL so Qt uses the Windows system API; the standalone executable was smoke-tested separately from the source application.

This remains a software traffic-signal simulator; it does not control road hardware.
