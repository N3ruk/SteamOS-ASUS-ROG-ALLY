#!/usr/bin/python3
import json
from pathlib import Path
import subprocess
import threading
import sys

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Gio
from power_backend import cpu_state, power_source, read, remembered_limits
from tray import Tray

BASE = Path(__file__).resolve().parent
HELPER = '/usr/local/libexec/desktop-power-helper'
DESKTOP = Path.home() / '.local/share/applications/local.AllyPower.desktop'
TRAY_ICON = BASE / 'icon.svg'


def launcher_icon():
    entry = Gio.DesktopAppInfo.new_from_filename(str(DESKTOP))
    return entry.get_string('Icon') if entry else str(BASE / 'icon-gaming.png')


def recorded_state():
    value = read('/sys/class/firmware-attributes/asus-armoury/attributes/ppt_pl1_spl/current_value')
    watts = float(value) if value.isdigit() and 0 < int(value) < 200 else None
    remembered = remembered_limits()
    if remembered:
        watts = remembered['stapm']
    return {'cpu': cpu_state(), 'limits': {'stapm': watts}, 'target': None,
            'tdp_verified': False, 'temperature': None,
            'tdp_note': ('Último TDP aceptado por Ally Power; no es telemetría. Otros gestores pueden cambiarlo.'
                         if remembered else 'Configuración registrada por ASUS. Lectura real de la APU no disponible.')}
CSS = b'''
window { background: #10161d; color: #edf2f7; }
.page { padding: 22px; }
.footer { padding: 0 26px 22px; }
.title { font-size: 27px; font-weight: 800; letter-spacing: -1px; }
.subtitle { color: #92a1b2; font-size: 12px; }
.badge { background: #16332f; color: #75e4c4; border-radius: 18px;
         padding: 8px 12px; font-size: 11px; font-weight: 700; }
.card { background: #19222d; border: 1px solid #293442; border-radius: 18px; padding: 18px; }
.state-card { background: #152c2b; border-color: #2b514b; }
.metric { font-size: 29px; font-weight: 800; color: #8cebcf; }
.section { color: #b3c0ce; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; }
.watts { font-size: 42px; font-weight: 800; color: #75e4c4; }
.muted { color: #93a3b5; font-size: 12px; }
.small { color: #93a3b5; font-size: 11px; }
.field { font-size: 14px; font-weight: 600; }
.live { color: #c4d2df; font-size: 12px; }
scale { padding: 12px 0; }
scale trough { background: #32404e; min-height: 6px; border-radius: 8px; }
scale highlight { background: #68dbba; border-radius: 8px; }
scale slider { background: #b6ffe9; border: 3px solid #68dbba; min-width: 15px;
               min-height: 15px; border-radius: 20px; box-shadow: none; }
button { background: #263341; color: #e2eaf2; border: 1px solid #354454;
         border-radius: 10px; padding: 9px 14px; box-shadow: none; font-weight: 600; }
button:hover { background: #344657; }
button:disabled { opacity: 0.45; }
button.apply { background: #75e4c4; color: #102720; border: none; padding: 12px 30px; }
button.apply:hover { background: #a1f3db; }
button.quiet { background: transparent; border-color: #34414f; }
switch { background: #344354; border-radius: 18px; }
switch:checked { background: #75e4c4; }
switch slider { background: #e9f4f0; border-radius: 18px; min-width: 22px; min-height: 22px; }
spinbutton { background: #101820; color: #eff8f5; border: 1px solid #384758; border-radius: 10px; }
spinbutton text { padding: 8px; min-width: 35px; font-weight: 700; }
spinbutton button { padding: 7px 10px; border: none; background: transparent; }
separator { background: #2c3947; min-height: 1px; }
.status { font-size: 12px; color: #b6c5d3; }
.error { color: #ffb5a7; }
'''


def label(text, style=None, xalign=0):
    widget = Gtk.Label(label=text, xalign=xalign)
    if style:
        widget.add_css_class(style)
    return widget


def row(*widgets, spacing=12):
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
    for widget in widgets:
        box.append(widget)
    return box


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Ally Power')
        self.set_default_size(620, 960)
        self.set_resizable(True)
        self.proc = None
        self.ready = False
        self.can_keep = False
        self.backend_error = ''
        self.busy = False
        self.closing = False
        self.pending = None
        self.dirty = False
        self.close_dialog = None
        self.cancel_auth_on_close = False
        self.initializing = True
        self.current_state = None
        self.applied_config = None
        self.last_ac = None
        self.initial_cpu = cpu_state()
        self.initial_state = recorded_state()
        self.initial_tdp = self.initial_state['limits']['stapm']
        self.max_cores = self.initial_cpu['max_cores']
        self.connect('close-request', self.on_close)
        icon = launcher_icon()
        if Path(icon).is_file():
            Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).add_search_path(str(Path(icon).parent))
            self.set_icon_name(Path(icon).stem)
        else:
            self.set_icon_name(icon)

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(root)
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        root.append(scroll)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page.add_css_class('page')
        scroll.set_child(page)

        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, hexpand=True)
        heading.append(label('Ally Power', 'title'))
        heading.append(label('Control de energía · Modo escritorio', 'subtitle'))
        self.badge = label('DETECTANDO', 'badge')
        self.badge.set_valign(Gtk.Align.CENTER)
        page.append(row(heading, self.badge))

        state_card = self.card()
        state_card.add_css_class('state-card')
        state_card.append(label('ESTADO ACTUAL', 'section'))
        metrics = row(spacing=22)
        self.active_tdp = label('—', 'metric')
        self.active_cores = label('—', 'metric')
        self.active_threads = label('—', 'metric')
        for text, value in [('TDP configurado', self.active_tdp),
                            ('Núcleos activos', self.active_cores), ('Hilos activos', self.active_threads)]:
            column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
            column.append(value)
            column.append(label(text, 'small'))
            metrics.append(column)
        state_card.append(metrics)
        self.live = label('', 'live')
        state_card.append(self.live)
        self.tdp_note = label('', 'small')
        self.tdp_note.set_wrap(True)
        self.tdp_note.set_max_width_chars(65)
        state_card.append(self.tdp_note)
        page.append(state_card)

        tdp_card = self.card()
        title = label('AJUSTAR TDP', 'section')
        title.set_hexpand(True)
        self.watts_label = label('', 'watts')
        tdp_card.append(row(title, self.watts_label))
        self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 3, 30, 1)
        self.slider.set_draw_value(False)
        self.slider.set_value(self.initial_tdp or 3)
        self.slider.set_round_digits(0)
        self.slider.set_hexpand(True)
        self.slider.connect('value-changed', self.on_change)
        tdp_card.append(self.slider)
        minimum = label('3 W', 'muted')
        minimum.set_hexpand(True)
        self.maximum = label('30 W · corriente', 'muted', 1)
        tdp_card.append(row(minimum, self.maximum))
        self.slider_hint = label('Sin cambios pendientes', 'small')
        tdp_card.append(self.slider_hint)
        presets = row()
        for title, value in [('Ahorro · 8 W', 8), ('Equilibrio · 15 W', 15), ('Potencia · 25 W', 25)]:
            button = Gtk.Button(label=title, hexpand=True)
            button.connect('clicked', lambda _, watts=value: self.slider.set_value(watts))
            presets.append(button)
        tdp_card.append(presets)
        tdp_card.append(label('Límite de CPU + GPU, no consumo total del equipo.', 'small'))
        page.append(tdp_card)

        cpu_card = self.card()
        cpu_card.append(label('NÚCLEOS E HILOS', 'section'))
        smt_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        smt_text.append(label('SMT', 'field'))
        smt_text.append(label('Permite hasta dos hilos por núcleo físico', 'muted'))
        self.smt = Gtk.Switch(active=self.initial_cpu['smt'], valign=Gtk.Align.CENTER)
        self.smt.connect('notify::active', self.on_smt)
        cpu_card.append(row(smt_text, self.smt))
        cpu_card.append(Gtk.Separator())
        self.cores = Gtk.SpinButton.new_with_range(1, self.max_cores, 1)
        self.cores.set_value(self.initial_cpu['cores'])
        self.threads = Gtk.SpinButton.new_with_range(1, self.initial_cpu['max_threads'], 1)
        self.threads.set_value(self.initial_cpu['threads'])
        self.cores.connect('value-changed', self.on_cores)
        self.threads.connect('value-changed', self.on_change)
        for title, control in [('Núcleos activos', self.cores), ('Hilos activos', self.threads)]:
            text = label(title, 'field')
            text.set_hexpand(True)
            cpu_card.append(row(text, control))
        self.cpu_hint = label('', 'muted')
        cpu_card.append(self.cpu_hint)
        page.append(cpu_card)

        footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        footer.add_css_class('footer')
        root.append(footer)
        self.status = label('Ajusta los controles y pulsa Aplicar.', 'status')
        self.status.set_wrap(True)
        self.status.set_max_width_chars(60)
        footer.append(self.status)
        self.restore_button = Gtk.Button(label='Restaurar inicial')
        self.restore_button.add_css_class('quiet')
        self.restore_button.connect('clicked', self.on_restore)
        spacer = Gtk.Box(hexpand=True)
        self.apply_button = Gtk.Button(label='Aplicar')
        self.apply_button.add_css_class('apply')
        self.apply_button.connect('clicked', self.on_apply)
        footer.append(row(self.restore_button, spacer, self.apply_button))
        footnote = label('Al salir conserva lo aplicado. En la bandeja sigue vigilando la batería.\n'
                         'Restaurar inicial solo se hace si lo solicitas.', 'small')
        footnote.set_wrap(True)
        footer.append(footnote)
        self.initializing = False
        self.update_threads()
        self.poll()
        self.poll_id = GLib.timeout_add_seconds(2, self.poll)

    def card(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.add_css_class('card')
        return box

    def config(self):
        return {'watts': round(self.slider.get_value()), 'smt': self.smt.get_active(),
                'cores': self.cores.get_value_as_int(), 'threads': self.threads.get_value_as_int()}

    def set_config(self, config):
        self.initializing = True
        self.slider.set_value(config['watts'])
        self.smt.set_active(config['smt'])
        self.cores.set_value(config['cores'])
        self.update_threads()
        self.threads.set_value(config['threads'])
        self.initializing = False
        self.dirty = False
        self.watts_label.set_text(f"{round(self.slider.get_value())} W")
        self.slider_hint.set_text('Sincronizado con la configuración actual')

    def update_threads(self, full=False):
        cores = self.cores.get_value_as_int()
        maximum = cores * (2 if self.smt.get_active() else 1)
        self.threads.set_range(cores, maximum)
        if full:
            self.threads.set_value(maximum)
        self.threads.set_sensitive(self.smt.get_active() and not self.busy)
        self.cpu_hint.set_text(f'{cores} núcleos físicos · de {cores} a {maximum} hilos disponibles')

    def on_smt(self, *_):
        self.update_threads(full=True)
        self.on_change()

    def on_cores(self, *_):
        self.update_threads(full=True)
        self.on_change()

    def on_change(self, *_):
        if self.initializing:
            return
        self.dirty = True
        self.watts_label.set_text(f'{round(self.slider.get_value())} W')
        self.slider_hint.set_text('Vista previa · pendiente de aplicar')
        if not self.busy:
            self.message('Cambios pendientes · pulsa Aplicar.')

    def message(self, text, error=False):
        self.status.set_text(text)
        self.status.remove_css_class('error')
        if error:
            self.status.add_css_class('error')

    def set_busy(self, value):
        self.busy = value
        for widget in (self.apply_button, self.restore_button, self.slider, self.smt, self.cores):
            widget.set_sensitive(not value)
        self.update_threads()
        self.apply_button.set_label('Aplicando…' if value else 'Aplicar')

    def send(self, request):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write(json.dumps(request) + '\n')
                self.proc.stdin.flush()
                return True
            except (OSError, BrokenPipeError):
                pass
        return False

    def start_backend(self):
        self.ready = False
        self.backend_error = ''
        self.message('Autoriza el control de energía en la ventana del sistema.')
        self.proc = subprocess.Popen(['pkexec', HELPER], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, bufsize=1)
        process = self.proc

        def consume():
            for line in process.stdout:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                GLib.idle_add(self.on_event, event)
            code = process.wait()
            detail = process.stderr.read()[-400:]
            GLib.idle_add(self.on_exit, process, code, detail)

        threading.Thread(target=consume, daemon=True).start()

    def on_apply(self, *_):
        if not Path(HELPER).is_file():
            self.message('Falta completar la instalación: acepta la autorización del sistema.', True)
            return
        self.pending = self.config()
        self.set_busy(True)
        if self.ready:
            self.message('Aplicando y comprobando los ajustes…')
            self.send({'action': 'apply', 'config': self.pending})
        else:
            try:
                self.start_backend()
            except OSError as exc:
                self.set_busy(False)
                self.message(str(exc), True)

    def on_restore(self, *_):
        if self.ready:
            self.set_busy(True)
            self.message('Restaurando el estado inicial…')
            self.send({'action': 'restore'})
        else:
            self.set_config({'watts': self.initial_tdp or 3, **{key: self.initial_cpu[key]
                                           for key in ('smt', 'cores', 'threads')}})
            self.message('No se ha aplicado ningún cambio al equipo.')

    def on_event(self, event):
        kind = event.get('event')
        state = event.get('state')
        if state:
            self.current_state = state
        if kind == 'ready':
            self.ready = True
            self.can_keep = 'quit_keep' in event.get('capabilities', [])
            if self.closing:
                self.closing = False
                self.begin_shutdown()
            elif self.pending:
                self.send({'action': 'apply', 'config': self.pending})
        elif kind in ('applied', 'restored'):
            self.pending = None
            self.applied_config = state['target']
            self.set_busy(False)
            if kind == 'applied':
                self.set_config(state['target'])
                self.message('Aplicado · TDP y procesadores verificados.' if state.get('tdp_verified', True)
                             else 'Aplicado · potencia aceptada por la SMU; núcleos e hilos verificados.')
            else:
                self.set_config({'watts': round(state['limits']['stapm']),
                                 **{key: state['cpu'][key] for key in ('smt', 'cores', 'threads')}})
                self.message('Estado inicial restaurado.')
        elif kind == 'error':
            self.backend_error = event['message']
            self.pending = None
            self.set_busy(False)
            if self.closing:
                self.closing = False
                self.present()
            self.message(event['message'], True)
        elif kind == 'closed':
            if self.closing:
                self.get_application().finish()
        if state:
            self.show_state(state)
        return False

    def show_state(self, state):
        cpu = state['cpu']
        actual = state['limits']['stapm']
        temp = state.get('temperature')
        suffix = f'  ·  {temp} °C' if temp is not None else ''
        self.active_tdp.set_text(f'{actual:g} W' if actual is not None else '—')
        self.active_cores.set_text(str(cpu['cores']))
        self.active_threads.set_text(str(cpu['threads']))
        self.live.set_text(f"SMT {'activado' if cpu['smt'] else 'desactivado'}{suffix}")
        self.tdp_note.set_text(state.get('tdp_note', ''))
        if actual is not None and not self.dirty and not self.busy:
            self.set_config({'watts': round(actual), **{key: cpu[key] for key in ('smt', 'cores', 'threads')}})
        tray = getattr(self.get_application(), 'tray', None)
        if tray:
            watts = f'{actual:g} W configurados' if actual is not None else 'TDP no disponible'
            tray.update(f"{watts} · {cpu['cores']} núcleos / {cpu['threads']} hilos")
        if state.get('warning') and not self.busy:
            self.message(state['warning'], True)

    def on_exit(self, process, code, detail):
        if self.proc is not process:
            return False
        self.ready = False
        self.proc = None
        self.current_state = None
        if self.closing and (code == 0 or self.cancel_auth_on_close):
            self.get_application().finish()
        elif self.closing:
            self.closing = False
            self.set_busy(False)
            self.message('No se ha podido confirmar el cierre conservando los ajustes. ' + detail, True)
        elif code:
            self.set_busy(False)
            if self.backend_error:
                self.message(self.backend_error, True)
            elif code == 126:
                self.message('Se canceló la autorización del sistema.', True)
            elif code == 127:
                self.message('El sistema no autorizó el ayudante. ' + detail, True)
            else:
                self.message(f'El ayudante terminó con código {code}. ' + detail, True)
        return False

    def poll(self):
        source = power_source()
        ac = source['ac']
        maximum = source['max_watts']
        battery = f" · {source['battery']} %" if source['battery'] is not None else ''
        self.badge.set_text(('CONECTADA' if ac else 'BATERÍA') + battery)
        self.maximum.set_text(f"{maximum} W · {'corriente' if ac else 'batería'}")
        was_initializing = self.initializing
        self.initializing = True
        self.slider.set_range(3, maximum)
        self.initializing = was_initializing
        self.watts_label.set_text(f'{round(self.slider.get_value())} W')
        if self.last_ac is not None and self.last_ac != ac and not self.busy:
            self.message('Corriente detectada · hasta 30 W.' if ac else
                         'Modo batería · máximo 25 W. El límite activo se adapta automáticamente.')
        self.last_ac = ac
        if not Path(HELPER).is_file():
            self.apply_button.set_sensitive(False)
            self.message('Instalación pendiente: acepta la autorización del sistema.')
        elif not self.busy:
            self.apply_button.set_sensitive(True)
        if self.ready:
            self.send({'action': 'ping'})
        elif not self.ready:
            self.show_state(recorded_state())
        return True

    def on_close(self, *_):
        if self.closing:
            return True
        if self.close_dialog:
            self.close_dialog.present()
            return True
        tray = getattr(self.get_application(), 'tray', None)
        available = bool(tray and tray.registered)
        dialog = Gtk.MessageDialog(transient_for=self, modal=True,
                                   message_type=Gtk.MessageType.QUESTION,
                                   text='¿Qué quieres hacer con Ally Power?',
                                   secondary_text='Dejar en la bandeja mantiene los ajustes y el control de batería. '
                                                  'Cerrar conserva los ajustes aplicados, pero termina la vigilancia '
                                                  'de batería. Los cambios pendientes no se aplican.')
        dialog.add_button('Cancelar', Gtk.ResponseType.CANCEL)
        dialog.add_button('Cerrar y conservar', 2)
        button = dialog.add_button('Dejar en la bandeja', 1)
        button.set_sensitive(available)
        if not available:
            button.set_tooltip_text('La bandeja del escritorio no está disponible.')
        dialog.set_default_response(1 if available else Gtk.ResponseType.CANCEL)
        dialog.connect('response', self.close_response)
        self.close_dialog = dialog
        dialog.present()
        return True

    def close_response(self, dialog, response):
        dialog.destroy()
        self.close_dialog = None
        if response == 1:
            self.set_visible(False)
        elif response == 2:
            self.begin_shutdown()

    def begin_shutdown(self):
        if self.closing:
            return
        if self.ready and not self.can_keep:
            self.message('Actualiza el ayudante antes de cerrar conservando los ajustes.', True)
            return
        self.closing = True
        if self.proc and self.proc.poll() is None:
            self.set_busy(True)
            self.message('Cerrando sin deshacer los ajustes aplicados…')
            if self.ready:
                self.send({'action': 'quit_keep'})
            else:
                self.cancel_auth_on_close = True
                self.proc.terminate()
        else:
            self.get_application().finish()


class Application(Gtk.Application):
    def __init__(self):
        GLib.set_prgname('local.AllyPower')
        GLib.set_application_name('Ally Power')
        super().__init__(application_id='local.AllyPower')
        self.window = None
        self.tray = None
        self.held = False

    def do_activate(self):
        if self.window is None:
            self.window = Window(self)
            self.hold()
            self.held = True
            try:
                self.tray = Tray(self.window, TRAY_ICON)
            except (GLib.Error, OSError) as exc:
                self.window.message('Bandeja no disponible: ' + str(exc), True)
        self.window.present()

    def finish(self):
        if self.tray:
            self.tray.close()
            self.tray = None
        if self.window:
            GLib.source_remove(self.window.poll_id)
        if self.held:
            self.release()
            self.held = False
        self.quit()


if __name__ == '__main__':
    Application().run(sys.argv)
