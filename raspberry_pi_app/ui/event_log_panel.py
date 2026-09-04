"""Searchable, filterable and exportable operational event console."""

from __future__ import annotations

import csv
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .components import SecondaryButton
from .theme import Color, Space, event_category, event_severity


class EventLogPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SectionCard")
        self.setMaximumHeight(220)
        self.events: list[dict[str, str]] = []
        # Keep the operational map prominent on startup. Operators can reveal
        # the full searchable console with one click and its state is retained.
        self._expanded = False
        root = QVBoxLayout(self)
        root.setContentsMargins(Space.LG, Space.MD, Space.LG, Space.MD)
        root.setSpacing(Space.SM)
        header = QHBoxLayout()
        self.toggle = QPushButton("Event log  —  Show")
        self.toggle.setObjectName("SectionTitle")
        self.toggle.setFlat(True)
        self.toggle.setToolTip("Collapse or expand the operational event log")
        self.toggle.clicked.connect(self.toggle_collapsed)
        header.addWidget(self.toggle)
        header.addStretch()
        root.addLayout(header)
        self.content = QWidget()
        content = QVBoxLayout(self.content)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(Space.SM)
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search events")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        self.category = QComboBox()
        self.category.addItems(["All categories", "GPS", "MQTT", "Signal", "Priority", "Safety", "System"])
        self.category.currentTextChanged.connect(self._apply_filter)
        self.severity = QComboBox()
        self.severity.addItems(["All severities", "Information", "Success", "Warning", "Critical"])
        self.severity.currentTextChanged.connect(self._apply_filter)
        self.auto_scroll = QCheckBox("Auto-scroll")
        self.auto_scroll.setChecked(True)
        clear = SecondaryButton("Clear visible")
        clear.clicked.connect(self.clear_visible)
        export = SecondaryButton("Export log")
        export.clicked.connect(self.export_log)
        for widget in (self.search, self.category, self.severity, self.auto_scroll, clear, export):
            tools.addWidget(widget)
        content.addLayout(tools)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Time", "Level", "Category", "Message"])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(96)
        content.addWidget(self.table)
        root.addWidget(self.content)
        self.content.setVisible(False)

    def append_event(self, event_type: str, message: str) -> None:
        self.events.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "severity": event_severity(event_type),
            "category": event_category(event_type),
            "type": event_type,
            "message": message,
        })
        if len(self.events) > 1000:
            self.events = self.events[-1000:]
        self._apply_filter()

    def _matching_events(self) -> list[dict[str, str]]:
        query = self.search.text().strip().lower()
        category = self.category.currentText()
        severity = self.severity.currentText().lower()
        result = []
        for event in self.events:
            haystack = f"{event['type']} {event['message']} {event['category']}".lower()
            if query and query not in haystack:
                continue
            if category != "All categories" and event["category"] != category:
                continue
            if severity != "all severities" and event["severity"] != severity:
                continue
            result.append(event)
        return result

    def _apply_filter(self) -> None:
        matching = self._matching_events()
        self.table.setRowCount(len(matching))
        colours = {"info": Color.INFO, "success": Color.GREEN, "warning": Color.AMBER, "critical": Color.RED}
        labels = {"info": "INFO", "success": "OK", "warning": "WARNING", "critical": "CRITICAL"}
        for row, event in enumerate(matching):
            values = [event["time"], labels[event["severity"]], event["category"], f"{event['type'].replace('_', ' ').title()} — {event['message']}"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 1:
                    item.setForeground(QColor(colours[event["severity"]]))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
        if self.auto_scroll.isChecked() and matching:
            self.table.scrollToBottom()

    def clear_visible(self) -> None:
        visible_ids = {id(event) for event in self._matching_events()}
        self.events = [event for event in self.events if id(event) not in visible_ids]
        self._apply_filter()

    def clear(self) -> None:
        self.events.clear()
        self._apply_filter()

    def export_log(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export LifeLane event log", "lifelane-events.csv", "CSV files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=["time", "severity", "category", "type", "message"])
            writer.writeheader()
            writer.writerows(self._matching_events())

    def toggle_collapsed(self) -> None:
        self._expanded = not self._expanded
        self.content.setVisible(self._expanded)
        self.toggle.setText(f"Event log  —  {'Hide' if self._expanded else 'Show'}")
