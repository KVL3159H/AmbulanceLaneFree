"""Timestamped UI event feed."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QGroupBox, QPlainTextEdit, QVBoxLayout


class EventLogPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Event log")
        layout = QVBoxLayout(self)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        layout.addWidget(self.log)

    def append_event(self, event_type: str, message: str) -> None:
        self.log.appendPlainText(f"{datetime.now().strftime('%H:%M:%S')}  {event_type:<24} {message}")

    def clear(self) -> None:
        self.log.clear()
