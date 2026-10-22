"""Separate CPU and TDP transactions: CPU-only operation never touches RyzenAdj."""
from . import power_backend as hw
from .manager import competitors, in_gaming


class LiveController:
    def __init__(self):
        self.groups = hw.topology()
        self.cpu_original = hw.cpu_state(self.groups)
        self.cpu_target = None
        self.cpu_changed = False
        self.tdp_enabled = False
        self.tdp_original = None
        self.tdp_target = None
        self.tdp_changed = False
        self.last_limits = hw.remembered_limits() or hw.asus_limits()
        self.warning = ''

    def allowed(self):
        others = competitors()
        if others:
            raise RuntimeError('Otro gestor activo: ' + ', '.join(others))
        if not in_gaming():
            raise RuntimeError('Se ha salido del modo Gaming; control cedido.')

    def set_tdp_mode(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('Estado de control TDP no válido.')
        if enabled:
            self.allowed()
            if not self.tdp_enabled:
                # Capture only when explicitly acquiring TDP; CPU-only never probes the SMU.
                self.tdp_original = hw.limits()
                self.last_limits = dict(self.tdp_original)
                self.tdp_target = self.last_limits['stapm']
            self.tdp_enabled = True
        else:
            # Handoff to Steam: no restore, no last battery clamp, no TDP write.
            self.tdp_enabled = False
            self.tdp_original = None
            self.tdp_target = None
            self.tdp_changed = False
            hw.FALLBACK_LIMITS = None
        self.warning = ''

    def apply_cpu(self, config):
        self.allowed()
        if not isinstance(config, dict) or set(config) != {'smt', 'cores', 'threads'}:
            raise ValueError('Configuración de CPU no válida.')
        wanted = hw.target_cpus(self.groups, config['cores'], config['threads'], config['smt'])
        before = hw.cpu_state(self.groups)
        self.cpu_changed = True  # Include partial transactions in crash recovery.
        try:
            hw.write_cpus(config['smt'], wanted)
        except Exception as exc:
            try:
                hw.write_cpus(before['smt'], set(before['online']))
            except Exception as rollback:
                raise RuntimeError(f'{exc}; restauración de CPU incompleta: {rollback}') from exc
            raise
        self.cpu_target = dict(config)
        self.cpu_changed = True
        self.warning = ''

    def apply_tdp(self, watts):
        self.allowed()
        if not self.tdp_enabled:
            raise RuntimeError('El TDP está a cargo de Steam. Activa «TDP de Steam desactivado» para usar el deslizador.')
        maximum = hw.power_source()['max_watts']
        if type(watts) is not int or not 3 <= watts <= maximum:
            raise ValueError(f'El TDP debe estar entre 3 y {maximum} W.')
        before = hw.limits()
        # Recheck AC at the point of writing, but never touch the CPU here.
        watts = min(watts, hw.power_source()['max_watts'])
        self.tdp_changed = True
        try:
            self.last_limits = hw.write_limits(dict.fromkeys(('stapm', 'fast', 'slow'), watts))
        except Exception as exc:
            try:
                maximum = hw.power_source()['max_watts']
                self.last_limits = hw.write_limits({key: min(value, maximum) for key, value in before.items()})
            except Exception as rollback:
                raise RuntimeError(f'{exc}; restauración TDP incompleta: {rollback}') from exc
            raise
        self.tdp_target = watts
        self.tdp_changed = True
        self.warning = ''

    def apply(self, _config):
        raise ValueError('Utiliza las operaciones independientes de CPU y TDP.')

    def restore(self):
        # Crash safety, not a user-visible action. Never restore a domain not owned.
        if competitors() or not in_gaming():
            return
        errors = []
        if self.cpu_changed:
            try:
                hw.write_cpus(self.cpu_original['smt'], set(self.cpu_original['online']))
                self.cpu_changed = False
                self.cpu_target = None
            except Exception as exc:
                errors.append(str(exc))
        if self.tdp_enabled and self.tdp_changed and self.tdp_original:
            try:
                maximum = hw.power_source()['max_watts']
                self.last_limits = hw.write_limits({key: min(value, maximum) for key, value in self.tdp_original.items()})
                self.tdp_changed = False
                self.tdp_target = None
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError('Restauración incompleta: ' + '; '.join(errors))

    def tick(self):
        if competitors() or not in_gaming():
            return self.status()
        source = hw.power_source()
        if self.tdp_enabled and self.tdp_target is not None and self.tdp_target > source['max_watts']:
            self.apply_tdp(source['max_watts'])
        if self.cpu_target:
            actual = hw.cpu_state(self.groups)
            if any(actual[key] != self.cpu_target[key] for key in ('smt', 'cores', 'threads')):
                self.warning = 'Otro controlador ha cambiado la CPU. No se fuerza una reaplicación.'
        return self.status(source)

    def status(self, source=None):
        if not self.tdp_enabled:
            self.last_limits = hw.remembered_limits() or hw.asus_limits()
        return {'power': source or hw.power_source(), 'cpu': hw.cpu_state(self.groups),
                'limits': self.last_limits, 'target': None, 'cpu_target': self.cpu_target,
                'tdp_enabled': self.tdp_enabled, 'tdp_target': self.tdp_target,
                'tdp_verified': self.tdp_enabled and hw.FALLBACK_LIMITS is None,
                'tdp_note': 'Límite configurado/recordado; no es el consumo real medido de la APU.',
                'temperature': hw.temperature(), 'warning': self.warning}
