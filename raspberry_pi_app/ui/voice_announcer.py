"""Voice announcement service for emergency vehicle approaches and directions."""

from __future__ import annotations

import logging
import threading

LOGGER = logging.getLogger("lifelane.voice")


class VoiceAnnouncer:
    """Thread-safe, non-blocking text-to-speech announcer for traffic control alerts."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._spoken_trips: dict[str, str] = {}

    def reset_trip(self, trip_id: str) -> None:
        self._spoken_trips.pop(trip_id, None)

    def clear(self) -> None:
        self._spoken_trips.clear()

    def announce_approach(
        self, trip_id: str, approach_side: str, heading_direction: str = ""
    ) -> None:
        if not self.enabled:
            return

        normalized_side = approach_side.strip().upper()
        if not normalized_side or normalized_side in {"UNKNOWN", "CONFIRMING"}:
            return

        # Announce once per trip and approach
        if self._spoken_trips.get(trip_id) == normalized_side:
            return
        self._spoken_trips[trip_id] = normalized_side

        side_title = normalized_side.title()
        msg = f"Emergency vehicle approaching from {side_title}."
        if heading_direction:
            msg += f" Heading {heading_direction}."

        LOGGER.info("VOICE_ALERT: %s", msg)

        def _speak() -> None:
            try:
                import pythoncom
                import win32com.client

                pythoncom.CoInitialize()
                try:
                    speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    speaker.Speak(msg)
                finally:
                    pythoncom.CoUninitialize()
            except Exception as exc:
                LOGGER.debug("Voice announcement not available: %s", exc)

        thread = threading.Thread(target=_speak, daemon=True)
        thread.start()
