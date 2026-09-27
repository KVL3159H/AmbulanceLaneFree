"""Independent monotonic watchdog; expiry latches until controlled restart."""
import time
from threading import Event, Thread


class Watchdog:
    def __init__(self, timeout, on_fault, clock=time.monotonic):
        self.timeout, self.on_fault, self.clock = timeout, on_fault, clock
        self.last = clock()
        self.failed = False
        self.stopped = Event()

    def feed(self):
        if not self.failed:
            self.last = self.clock()

    def check(self):
        if not self.failed and self.clock() - self.last > self.timeout:
            self.failed = True
            self.on_fault()
        return not self.failed

    def start(self):
        def run():
            while not self.stopped.wait(min(0.1, self.timeout/4)):
                self.check()
        Thread(target=run, daemon=True).start()

    def close(self):
        self.stopped.set()
