"""Compact, accessible ambulance priority queue table."""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QHeaderView, QStackedLayout, QTableWidget, QTableWidgetItem

from ..core.models import PriorityRequest
from .components import EmptyState
from .theme import Color


class PriorityQueuePanel(QFrame):
    HEADERS = ["Position", "Ambulance", "Side", "Priority", "Distance", "ETA", "Waiting"]

    def __init__(self, detailed: bool = False) -> None:
        super().__init__()
        self.setObjectName("SectionCard")
        self.detailed = detailed
        self.stack = QStackedLayout(self)
        self.empty = EmptyState("No emergency requests", "Validated requests will appear here automatically.")
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.stack.addWidget(self.empty); self.stack.addWidget(self.table)

    def update_requests(self, requests: list[PriorityRequest], selected_trip: str | None = None) -> None:
        self.stack.setCurrentWidget(self.table if requests else self.empty)
        now = datetime.now(timezone.utc)
        self.table.setRowCount(len(requests))
        tones = {"RED": Color.RED, "YELLOW": Color.AMBER, "GREEN": Color.GREEN}
        names = {"RED": "Critical", "YELLOW": "Serious", "GREEN": "Stable"}
        for row, request in enumerate(requests):
            waiting = max(0.0, (now - request.first_requested_at).total_seconds())
            values = [str(row + 1), request.ambulance_id, request.approach.value.title(), names[request.priority.value],
                      f"{request.distance_metres:.0f} m", f"{request.eta_seconds:.1f} s" if request.eta_seconds is not None else "—", f"{waiting:.0f} s"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, request.trip_id)
                if column == 3: item.setForeground(QColor(tones[request.priority.value]))
                if request.trip_id == selected_trip: item.setBackground(QColor("#DBEAFE"))
                if column in {0, 4, 5, 6}: item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, item)

    def selected_trip_id(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else None
