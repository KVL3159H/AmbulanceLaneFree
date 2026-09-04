# Architecture

LifeLane deliberately separates UI, telemetry transport, safety logic, and storage. Both simulated and mobile packets become the same immutable `TelemetryPacket` and enter `LifeLaneCoordinator.process_packet`; there is no simulator-only priority shortcut.

```text
Android fused GPS ─ MQTT QoS 1 ─┐
                               ├─ validation/GPS history ─ queue ─ signal FSM ─ Qt scene
Built-in cardinal simulator ────┘                │             │
                                                └─ SQLite      └─ MQTT status/events
```

## Safety state model

The explicit preemption sequence is:

```text
NORMAL → REQUEST_VALIDATION → PREEMPTION_PENDING
       → CLEAR_CURRENT_GREEN → ALL_RED_CLEARANCE
       → AMBULANCE_GREEN → PASSAGE_MONITORING
       → RECOVERY_YELLOW → RECOVERY_ALL_RED
       → RETURN_TO_NORMAL → NORMAL
```

A request waits out the configurable minimum current green. Existing green lamps become yellow; all directions then become red for clearance; only the selected approach becomes green. Passage completion or maximum-green timeout starts a yellow recovery and all-red clearance. `assert_safe` runs after every transition and forbids simultaneous NS-group and EW-group green. Any violation latches `FAIL_SAFE`, forces all red, pauses timing, logs a critical event, and requires controlled reset.

Normal operation is the independent sequence NS green, NS yellow, all red, EW green, EW yellow, all red. North/South may be green together because they are the same non-conflicting demonstration phase; emergency green is limited to one approach.

## GPS eligibility

The engine validates schema, allow-listed ID, coordinates, finite fields, accuracy, packet age, trip status, and monotonically increasing sequence numbers. It calculates Haversine distance and both initial bearings. Outside the immediate radius it requires a heading inside tolerance plus a decreasing multi-sample distance trend. Inside the immediate radius, a slow/stopped unit remains eligible unless the trend clearly moves away. Speed is a rolling median; stopped ETA is unavailable outside the immediate area and uses the configured assumed minimum only inside it.

Passage needs prior entry inside the exit radius followed by two increasing distance samples and a heading away from the centre. A single noisy point cannot restore normal operation.

## Priority and persistence

Active passage wins, followed by RED, YELLOW, GREEN, ETA, longest wait, and ambulance ID. Every configured waiting-protection interval improves the effective queue rank by one level. Once a request owns clearance/passage, a newly arrived request cannot reverse it.

SQLite writes use placeholders. The desktop owns its connection on the UI thread; MQTT callbacks cross a Qt signal bridge before touching coordinator state. Rotating log files retain five 1 MB files.
