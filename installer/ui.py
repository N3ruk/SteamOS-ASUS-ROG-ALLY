"""Optional GTK4 selection UI; native KDE fallback lives in install.py."""
import threading
from . import engine


def run(root, ids, failures):
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk, GLib, Gio

    class App(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='local.SteamOSAllyInstaller', flags=Gio.ApplicationFlags.NON_UNIQUE)
            self.connect('activate', self.activate)
            self.busy = False
            self.failed = False
            self.boxes = {}

        def activate(self, *_):
            self.win = Gtk.ApplicationWindow(application=self, title='SteamOS ASUS ROG ALLY — Instalador 1.0.0')
            self.win.set_default_size(820, 680)
            self.win.connect('close-request', lambda *_: self.busy)
            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            for method in ('set_margin_top', 'set_margin_bottom', 'set_margin_start', 'set_margin_end'):
                getattr(outer, method)(18)
            self.win.set_child(outer)
            intro = Gtk.Label(label='Elige qué quieres instalar', xalign=0)
            intro.add_css_class('title-1')
            outer.append(intro)
            label = Gtk.Label(label='Nada está seleccionado por defecto. Instalar no cambia el arranque, TDP, SMT ni dispositivos Bluetooth. Los paquetes originales pueden mostrar su propia autorización.', wrap=True, xalign=0)
            outer.append(label)
            scroll = Gtk.ScrolledWindow(vexpand=True)
            rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
            scroll.set_child(rows)
            outer.append(scroll)
            for component in ids:
                item = engine.CATALOG[component]
                card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
                rows.append(card)
                # An unavailable Decky is explained, but not offered as a checkbox.
                if component in ('ally-power-decky', 'ally-rgb') and failures[component]:
                    title = Gtk.Label(label=item['name'] + ' — No disponible', xalign=0)
                    title.add_css_class('heading')
                    card.append(title)
                else:
                    checkbox = Gtk.CheckButton(label=item['name'] + ' ' + item['version'])
                    checkbox.set_sensitive(not failures[component])
                    self.boxes[component] = checkbox
                    card.append(checkbox)
                card.append(Gtk.Label(label=item['description'], wrap=True, xalign=0))
                note = '; '.join(failures[component]) if failures[component] else item['requirements']
                detail = Gtk.Label(label=note, wrap=True, xalign=0)
                detail.add_css_class('error' if failures[component] else 'dim-label')
                card.append(detail)
            self.status = Gtk.Label(label='Selecciona componentes y pulsa Instalar seleccionados.', wrap=True, xalign=0)
            outer.append(self.status)
            self.button = Gtk.Button(label='Instalar seleccionados')
            self.button.add_css_class('suggested-action')
            self.button.connect('clicked', self.start)
            outer.append(self.button)
            self.win.present()

        def start(self, *_):
            chosen = [i for i in ids if i in self.boxes and self.boxes[i].get_active() and not failures[i]]
            if not chosen:
                self.status.set_text('No has seleccionado ningún componente disponible.')
                return
            self.busy = True
            self.button.set_sensitive(False)
            for box in self.boxes.values():
                box.set_sensitive(False)
            self.status.set_text('Instalando… No cierres esta ventana. Atiende los diálogos de los instaladores originales.')
            threading.Thread(target=self.worker, args=(chosen,), daemon=True).start()

        def set_status(self, text):
            self.status.set_text(text)
            return False

        def worker(self, chosen):
            results = []
            for component in chosen:
                GLib.idle_add(self.set_status, 'Instalando: ' + engine.CATALOG[component]['name'])
                try:
                    text = engine.install(component, root)
                except Exception as exc:
                    self.failed = True
                    text = 'ERROR — ' + str(exc)
                results.append(engine.CATALOG[component]['name'] + ': ' + text)
            GLib.idle_add(self.finish, '\n\n'.join(results))

        def finish(self, text):
            self.busy = False
            self.status.set_text(text + '\n\nPuedes cerrar esta ventana.')
            self.button.set_label('Finalizado')
            return False

    app = App()
    app.run([])
    return 1 if app.failed else 0
