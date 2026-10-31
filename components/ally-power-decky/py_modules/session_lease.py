"""Read-only session lease. No system-sleep hooks, inhibitors or automatic writes."""
import time
import uuid
from .session_io import suspend_offset, session_frozen, SessionBoundary


class SessionLease:
    def __init__(self, clock=time.monotonic, offset=suspend_offset, frozen=session_frozen):
        self.clock, self.offset, self.frozen = clock, offset, frozen
        self.epoch = offset()
        self.token = uuid.uuid4().hex
        self.last = None
        self.since = None
        self.ready = False
        self.changed = False
        self.preparing = False

    def set_preparing(self, value):
        self.preparing = value
        self.token = uuid.uuid4().hex
        self.ready = False
        self.last = self.since = None

    def observe(self, pulse=False):
        now, epoch = self.clock(), self.offset()
        boundary = self.preparing or self.frozen() or abs(epoch - self.epoch) > .25
        gap = self.last is not None and now - self.last > 4
        self.changed = boundary or gap
        if self.changed:
            self.token = uuid.uuid4().hex
            self.epoch = epoch
            self.since = None
            self.last = None
            self.ready = False
        if pulse and not self.preparing and not self.frozen():
            if self.since is None:
                self.since = now
            self.last = now
            self.ready = now - self.since >= 10
        return self.ready

    def check(self, token):
        self.observe()
        if not self.ready or token != self.token:
            raise SessionBoundary('Sesión en transición: espera 10 s y vuelve a mover el control. No se reaplican órdenes antiguas.')
