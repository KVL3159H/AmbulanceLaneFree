"""LifeLane MQTT topic helpers."""


def ambulance_telemetry(prefix: str, ambulance_id: str = "+") -> str:
    return f"{prefix}/ambulance/{ambulance_id}/telemetry"


def ambulance_emergency(prefix: str, ambulance_id: str = "+") -> str:
    return f"{prefix}/ambulance/{ambulance_id}/emergency"


def ambulance_cancel(prefix: str, ambulance_id: str = "+") -> str:
    return f"{prefix}/ambulance/{ambulance_id}/cancel"


def ambulance_status(prefix: str, ambulance_id: str) -> str:
    return f"{prefix}/ambulance/{ambulance_id}/status"


def junction_request(prefix: str, junction_id: str) -> str:
    return f"{prefix}/junction/{junction_id}/request"


def junction_status(prefix: str, junction_id: str) -> str:
    return f"{prefix}/junction/{junction_id}/status"


def junction_events(prefix: str, junction_id: str) -> str:
    return f"{prefix}/junction/{junction_id}/events"
