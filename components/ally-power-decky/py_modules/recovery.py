"""Opt-in, one-shot resume plan. Never persists or applies hardware profiles."""
import copy
import json
import math
import os
from pathlib import Path
import stat
import tempfile
import time
import uuid


class Recovery:
    def __init__(self, settings_dir=None, clock=time.monotonic):
        self.clock = clock
        self.path = Path(settings_dir) / 'resume.json' if settings_dir else None
        self.enabled = False
        self.pending = self.active = None
        self.phase, self.reason, self.seconds = 'idle', '', None
        if self.path:
            try:
                info = self.path.lstat()
                # Decky owns settings as its host user, including on reload.
                # This file contains ONLY a boolean, never a hardware profile,
                # executable/path or privileged operation supplied from disk.
                owners = (0, os.geteuid(), self.path.parent.stat().st_uid)
                if (stat.S_ISREG(info.st_mode) and info.st_uid in owners
                        and not info.st_mode & 0o022 and info.st_size < 1024):
                    self.enabled = json.loads(self.path.read_text()).get('enabled') is True
            except (OSError, ValueError, AttributeError):
                pass

    def set_enabled(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('Estado de recuperación no válido.')
        if self.path:
            if any(p.is_symlink() for p in self.path.parents) or self.path.is_symlink():
                raise RuntimeError('Ruta de ajustes de recuperación insegura.')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix='.resume-')
            try:
                with os.fdopen(fd, 'w') as stream:
                    json.dump({'enabled': enabled}, stream)
                    os.fchmod(stream.fileno(), 0o600)
                os.replace(temporary, self.path)
            finally:
                if os.path.exists(temporary): os.unlink(temporary)
        self.enabled = enabled
        self.cancel('Recuperación activada.' if enabled else 'Recuperación desactivada.')

    def cancel(self, reason=''):
        self.pending = self.active = None
        self.phase, self.reason, self.seconds = 'cancelled', reason, None

    def arm(self, cpu, tdp, context, epoch):
        self.cancel('')
        if not self.enabled or not context or not (cpu or tdp is not None):
            if self.enabled:
                self.reason = ('Sin pulso reciente de Steam; recuperación omitida.' if not context else
                               'Sin ajustes propios que recuperar.')
            return
        self.pending = dict(id=uuid.uuid4().hex, cpu=copy.deepcopy(cpu), tdp=tdp,
            context=copy.deepcopy(context), before=epoch, after=None, baseline=None,
            last=None, end=None, expires=None)
        self.phase = 'armed'

    def prepared(self, baseline):
        if self.pending:
            self.pending['baseline'] = copy.deepcopy(baseline)

    def resume(self, epoch):
        p = self.pending
        if not p: return
        if p['after'] is not None:
            if abs(epoch - p['after']) > .25: self.cancel('Nueva suspensión: recuperación anterior descartada.')
            return
        if abs(epoch - p['before']) <= .25:
            self.cancel('Suspensión cancelada; no se reaplica el perfil.')
            return
        if p['cpu'] and p['baseline'] is None:
            p['cpu'] = None  # Never reduce again after an unconfirmed preparation.
        if not p['cpu'] and p['tdp'] is None:
            self.cancel('CPU no preparada; recuperación omitida.')
            return
        p['after'], p['expires'] = epoch, self.clock() + 60
        self.phase, self.reason = 'waiting', ''

    def pulse(self, context, epoch, ready, gaming, busy, competitors):
        p = self.pending
        if not p or p['after'] is None: return
        now = self.clock()
        if abs(epoch-p['after']) > .25:
            self.cancel('Nueva suspensión.'); return
        if not gaming or busy or competitors:
            self.cancel('Control cedido: sesión o gestor diferente.'); return
        if now > p['expires']:
            self.cancel('Recuperación caducada; sin reintentos.'); return
        if context['game_id'] != p['context']['game_id']:
            if context['game_id'] == '0' and p['context']['game_id'] != '0':
                # Steam can briefly have no MainRunningApp during resume.
                # Wait for the original app (bounded by expires), never apply
                # its settings to the menu while it is still being identified.
                p['last'] = p['end'] = None
                self.phase, self.seconds = 'waiting', None
                return
            self.cancel('Cambió el juego activo.'); return
        if ready and context['awake'] and p['tdp'] is not None and (context['native_tdp'] is not False
                or context['tdp_key'] != p['context']['tdp_key']):
            p['tdp'] = None
            self.reason = 'Steam cambió su TDP; se conserva su control.'
        if not p['cpu'] and p['tdp'] is None:
            self.cancel(self.reason or 'No quedan ajustes propios que recuperar.'); return
        if not context['awake']:
            p['last'] = p['end'] = None
            self.phase, self.seconds = 'waiting', None
            return
        if p['last'] is None or now-p['last'] > 4:
            p['end'] = now + 10
        p['last'] = now
        self.seconds = max(0, math.ceil(p['end']-now))
        self.phase = 'ready' if self.seconds == 0 and ready else 'countdown'

    def claim(self, identity):
        if not self.enabled or not self.pending or self.pending['id'] != identity or self.phase != 'ready':
            raise RuntimeError('Recuperación caducada o ya consumida.')
        self.active, self.pending = self.pending, None  # Consume BEFORE any await.
        self.phase, self.seconds = 'applying', None
        return copy.deepcopy(self.active)

    def check(self, identity, epoch):
        if (not self.enabled or not self.active or self.active['id'] != identity
                or abs(epoch-self.active['after']) > .25 or self.clock() > self.active['expires']):
            raise RuntimeError('Recuperación cancelada durante la aplicación.')

    def await_cpu(self, identity):
        self.check(identity, self.active['after'] if self.active else -1)
        self.phase = 'cpu-check'

    def claim_cpu(self, identity, epoch):
        self.check(identity, epoch)
        if self.phase != 'cpu-check':
            raise RuntimeError('Etapa CPU ya consumida.')
        self.phase = 'applying-cpu'
        return copy.deepcopy(self.active)

    def finish(self, identity, error=''):
        if self.active and self.active['id'] == identity:
            self.active = None
            self.phase = 'skipped' if error else 'restored'
            if error: self.reason = error

    def state(self):
        if self.active and self.clock() > self.active['expires']:
            self.cancel('Recuperación caducada; no se reintenta.')
        visible = self.pending or (self.active if self.phase == 'cpu-check' else None)
        return dict(enabled=self.enabled, pending=self.pending is not None,
            id=visible['id'] if visible else None, phase=self.phase,
            seconds=self.seconds, reason=self.reason, delay=10,
            wants_tdp=bool(visible and visible['tdp'] is not None))
