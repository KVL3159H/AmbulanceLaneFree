"""Priority queue table."""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtWidgets import QGroupBox, QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout

from ..core.models import PriorityRequest


class PriorityQueuePanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Ambulance priority queue")
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["#", "Ambulance", "Side", "Priority", "Distance", "ETA", "Waiting", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

    def update_requests(self, requests: list[PriorityRequest]) -> None:
        now = datetime.now(timezone.utc)
        self.table.setRowCount(len(requests))
        for row, request in enumerate(requests):
            waiting = max(0.0, (now - request.first_requested_at).total_seconds())
            values = [
                str(row + 1), request.ambulance_id, request.approach.value,
                request.priority.value, f"{request.distance_metres:.0f} m",
                f"{request.eta_seconds:.1f} s" if request.eta_seconds is not None else "—",
                f"{waiting:.0f} s", request.status.value,
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def selected_trip_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        ambulance_item = self.table.item(row, 1)
        if not ambulance_item:
            return None
        # The trip is stored as item metadata by MainWindow when needed; row lookup is safer there.
        return ambulance_item.data(0x0100)
