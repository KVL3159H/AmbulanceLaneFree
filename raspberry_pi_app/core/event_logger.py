"""Structured laboratory events; patient names are never accepted fields."""
import csv
import json
import html
from datetime import datetime, timezone

FIELDS = "timestamp sourceComponent eventType tripId requestId ambulanceId junctionId approachSide gpsAccuracy distanceToStopLine controllerState signalState result failureReason".split()


class EventLogger:
    def __init__(self, path=None):
        self.events = []
        self.path = path

    def record(self, **event):
        row = {key: event.get(key) for key in FIELDS}
        row["timestamp"] = row["timestamp"] or datetime.now(timezone.utc).isoformat()
        self.events.append(row)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as stream:
                stream.write(json.dumps(row)+"\n")
        return row

    def export(self, path, search="", trip_id=None):
        rows = [r for r in self.events if (trip_id is None or r["tripId"] == trip_id)
                and search.lower() in json.dumps(r).lower()]
        with open(path, "w", encoding="utf-8", newline="") as stream:
            if str(path).lower().endswith(".csv"):
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader(); writer.writerows(rows)
            else:
                json.dump(rows, stream, indent=2)

    def trip_report(self, trip_id):
        rows = [row for row in self.events if row["tripId"] == trip_id]
        if not rows:
            raise ValueError("No recorded events for this trip")
        kinds = [row["eventType"] for row in rows]
        failures = [row for row in rows if row["failureReason"]]
        completed = "JUNCTION_CLEARED" in kinds and any(k in kinds for k in ("NORMAL_RESTORED", "NORMAL_OPERATION_RESTORED"))
        return {"tripId":trip_id,"scope":"Recorded laboratory events; not hardware certification",
                "firstEventTimestamp":rows[0]["timestamp"],"lastEventTimestamp":rows[-1]["timestamp"],
                "eventCount":len(rows),"failureCount":len(failures),
                "result":"FAIL" if failures else ("PASS" if completed else "INCOMPLETE"),
                "checks":{"junctionClearanceRecorded":"JUNCTION_CLEARED" in kinds,
                          "normalRestorationRecorded":any(k in kinds for k in ("NORMAL_RESTORED", "NORMAL_OPERATION_RESTORED"))},
                "events":rows}

    def metrics(self):
        trips={row["tripId"] for row in self.events if row["tripId"]}
        def first(rows,kind):
            return next((datetime.fromisoformat(r["timestamp"].replace("Z","+00:00")) for r in rows if r["eventType"]==kind),None)
        def elapsed(start,end):
            return max(0,(end-start).total_seconds()) if start and end else None
        measurements=[]
        for trip in sorted(trips):
            rows=[r for r in self.events if r["tripId"]==trip]
            requested=first(rows,"REQUEST_ACCEPTED")
            green=first(rows,"AMBULANCE_GREEN")
            entered=first(rows,"JUNCTION_ENTERED")
            cleared=first(rows,"JUNCTION_CLEARED")
            measurements.append({"tripId":trip,"delayBeforeGreenSeconds":elapsed(requested,green),
                "junctionOccupationSeconds":elapsed(entered,cleared),
                "monitoredTravelSeconds":elapsed(first(rows,"GPS_PACKET"),cleared)})
        return {"acceptedRequests":sum(r["eventType"]=="REQUEST_ACCEPTED" for r in self.events),
                "safeRestorations":len({r["tripId"] for r in self.events if r["eventType"]=="NORMAL_RESTORED" and r["tripId"]}),
                "rejectedGpsOrRequestEvents":sum(r["eventType"]=="REQUEST_REJECTED" for r in self.events),
                "ambulanceMeasurements":measurements}

    def trip_html(self,trip_id):
        report=self.trip_report(trip_id)
        escape=lambda value:html.escape(str(value if value is not None else "—"))
        columns=("timestamp","eventType","controllerState","result","failureReason")
        rows="".join("<tr>"+"".join("<td>"+escape(row[key])+"</td>" for key in columns)+"</tr>" for row in report["events"])
        return ('<!doctype html><html><meta charset="utf-8"><title>Emergency Way trip test</title>'
            '<style>body{font:14px system-ui;color:#172033;margin:40px;background:#F8FAFC}h1{color:#EA580C}'
            'table{border-collapse:collapse;width:100%;background:white}td,th{border:1px solid #E7EAF0;padding:8px;text-align:left}'
            'th{background:#FFF1E8}@media print{body{margin:12px;background:white}tr{break-inside:avoid}}</style>'
            '<h1>Emergency Way — trip test report</h1><p>Trip: '+escape(trip_id)+'</p><p>Result: <b>'+report['result']+'</b></p>'
            '<p>'+escape(report['scope'])+'</p><p>Events: '+str(report['eventCount'])+' · Failure events: '+str(report['failureCount'])+'</p>'
            '<table><thead><tr>'+''.join('<th>'+escape(column)+'</th>' for column in columns)+'</tr></thead><tbody>'+rows+'</tbody></table></html>')
