import json
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QPlainTextEdit, QLineEdit, QFileDialog
from ..simulator.scenarios import SCENARIOS, run_scenario


class MetricsPage(QWidget):
    def __init__(self):
        super().__init__(); layout=QVBoxLayout(self)
        layout.addWidget(QLabel("Traffic Metrics · Simulation measurements"))
        self.text=QPlainTextEdit(); self.text.setReadOnly(True); layout.addWidget(self.text)

    def refresh(self, engine, logger=None, hardware_acks=None):
        values=engine.metrics()
        if logger: values.update(logger.metrics())
        if hardware_acks is not None:
            values["observedHardwareRequests"]=len(hardware_acks)
            values["hardwareAccepted"]=sum(ack.get("accepted") is True for ack in hardware_acks)
            values["hardwareRejected"]=sum(ack.get("accepted") is False for ack in hardware_acks)
            values["hardwareAcknowledgements"]=[{key:ack.get(key) for key in
                ("requestId","controllerState","queuePosition","acknowledgementTimestamp","observedResponseSeconds")} for ack in hardware_acks]
        self.text.setPlainText(json.dumps(values,indent=2))


class ScenarioPage(QWidget):
    def __init__(self,config):
        super().__init__(); layout=QVBoxLayout(self)
        layout.addWidget(QLabel("Scenario Testing · Deterministic component simulations"))
        button=QPushButton("Run all 20 scenarios"); layout.addWidget(button)
        self.text=QPlainTextEdit(); self.text.setReadOnly(True); layout.addWidget(self.text)
        self.text.setPlainText("\n".join(f"{i+1}. {n}\nExpected: {e}" for i,(n,e) in enumerate(SCENARIOS)))
        button.clicked.connect(lambda:self.text.setPlainText(json.dumps([run_scenario(i,config) for i in range(len(SCENARIOS))],indent=2)))


class LogsPage(QWidget):
    def __init__(self,logger):
        super().__init__(); self.logger=logger; layout=QVBoxLayout(self)
        layout.addWidget(QLabel("Event Logs · Search, filter and export"))
        self.search=QLineEdit(); self.search.setPlaceholderText("Search event, trip, request or result"); layout.addWidget(self.search)
        self.text=QPlainTextEdit(); self.text.setReadOnly(True); layout.addWidget(self.text)
        for extension in ("csv","json"):
            button=QPushButton("Export "+extension.upper()); layout.addWidget(button)
            button.clicked.connect(lambda _=False,ext=extension:self.export(ext))
        self.search.textChanged.connect(self.refresh)
        self.trip=QLineEdit(); self.trip.setPlaceholderText("Exact trip ID for test report"); layout.addWidget(self.trip)
        report=QPushButton("Export trip test report (JSON)"); layout.addWidget(report)
        report.clicked.connect(self.export_trip_report)
        printable=QPushButton("Export printable trip report (HTML)"); layout.addWidget(printable)
        printable.clicked.connect(self.export_printable_report)

    def refresh(self,*_):
        query=self.search.text().lower()
        self.text.setPlainText("\n".join(json.dumps(row) for row in self.logger.events if query in json.dumps(row).lower()))

    def export(self,extension):
        path,_=QFileDialog.getSaveFileName(self,"Export events","emergency-way-events."+extension,"*."+extension)
        if path:self.logger.export(path,self.search.text())

    def export_trip_report(self):
        try: report=self.logger.trip_report(self.trip.text().strip())
        except ValueError as exc:
            self.text.setPlainText(str(exc)); return
        path,_=QFileDialog.getSaveFileName(self,"Trip test report","trip-test-report.json","*.json")
        if path:
            with open(path,"w",encoding="utf-8") as stream: json.dump(report,stream,indent=2)

    def export_printable_report(self):
        try: report=self.logger.trip_html(self.trip.text().strip())
        except ValueError as exc:
            self.text.setPlainText(str(exc)); return
        path,_=QFileDialog.getSaveFileName(self,"Printable trip report","trip-test-report.html","*.html")
        if path:
            with open(path,"w",encoding="utf-8") as stream: stream.write(report)
