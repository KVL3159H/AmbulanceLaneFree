"""SQLite schema for the software prototype."""

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS ambulances (
    ambulance_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    authorized INTEGER NOT NULL DEFAULT 1 CHECK (authorized IN (0, 1)),
    last_connection TEXT,
    last_latitude REAL,
    last_longitude REAL
);
CREATE TABLE IF NOT EXISTS trips (
    trip_id TEXT PRIMARY KEY,
    ambulance_id TEXT NOT NULL,
    priority TEXT NOT NULL,
    condition TEXT NOT NULL,
    destination TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    status TEXT NOT NULL,
    FOREIGN KEY (ambulance_id) REFERENCES ambulances(ambulance_id)
);
CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    accuracy REAL NOT NULL,
    speed REAL NOT NULL,
    heading REAL NOT NULL,
    timestamp TEXT NOT NULL,
    UNIQUE (trip_id, sequence_number),
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
);
CREATE TABLE IF NOT EXISTS signal_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    junction_id TEXT NOT NULL,
    trip_id TEXT,
    event_type TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT,
    reason TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_telemetry_trip_time ON telemetry(trip_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_time ON signal_events(timestamp);
"""
