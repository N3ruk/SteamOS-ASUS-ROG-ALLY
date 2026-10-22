#!/usr/bin/python3
from pathlib import Path
import sys
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Pango
from bluetooth_backend import Bluez

APP_ID = 'local.BluetoothTrustManager'
BASE = Path(__file__).resolve().parent
CSS = b'''
window { background: #101720; color: #eef3fa; }
.page { padding: 25px; }
.title { font-size: 26px; font-weight: 800; }
.subtitle { color: #9dacc1; font-size: 12px; }
.badge { color: #9ec9ff; background: #1c304b; border-radius: 15px; padding: 7px 12px; font-weight: 700; }
.notice { background: #18283b; border: 1px solid #2b415d; padding: 15px; border-radius: 14px; }
.small { color: #a8b8cb; font-size: 12px; }
.device-name { font-size: 15px; font-weight: 700; }
.address { font-family: monospace; font-size: 11px; color: #90a6c0; }
.connected { color: #85e1bd; font-size: 11px; }
.device { background: #192431; border: 1px solid #2c3b4e; padding: 16px; border-radius: 15px; margin-bottom: 10px; }
list, list row { background: transparent; }
list row { padding: 0; }
button { background: #25364b; color: #edf4ff; border: 1px solid #3a506c; border-radius: 10px; padding: 9px 12px; box-shadow: none; }
button:hover { background: #344e6e; }
button.remove { background: #382b35; color: #ffbec2; border-color: #68414d; }
button.remove:hover { background: #55313f; }
button:disabled { opacity: 0.45; }
entry { background: #192431; color: #edf4ff; border: 1px solid #34475e; border-radius: 10px; padding: 8px; }
.status { color: #99dbbe; font-size: 12px; }
.error { color: #ffb2b9; }
.empty { padding: 38px; color: #a6b8ce; }
'''


def label(text, css=None):
    widget = Gtk.Label(label=text, xalign=0)
    if css:
        widget.add_css_class(css)
    return widget


class Window(Gtk.ApplicationWindow):
    def __init__(self, application, client=None):
        super().__init__(application=application, title='Confianza Bluetooth')
        self.set_default_size(740, 650)
        self.set_icon_name(APP_ID)
        self.client = client
        self.devices = []
        self.busy = False
        self.disposed = False
        self.refreshing = False
        self.refresh_again = False
        self.refresh_source = None
        self.dialog = None
        self.buttons = []
        self.connect('close-request', self.on_close)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                   Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        page.add_css_class('page')
        self.set_child(page)
        header = Gtk.Box(spacing=14)
        icon = Gtk.Image.new_from_file(str(BASE / 'controller.svg'))
        icon.set_pixel_size(62)
        header.append(icon)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        title_box.append(label('Confianza Bluetooth', 'title'))
        title_box.append(label('Gestiona los dispositivos autorizados', 'subtitle'))
        header.append(title_box)
        self.count = label('…', 'badge')
        self.count.set_valign(Gtk.Align.CENTER)
        header.append(self.count)
        page.append(header)
        notice = label('Quitar la confianza no borra el emparejamiento.\n'
                       'El dispositivo podrá pedir autorización al conectarse de nuevo.', 'small')
        notice.add_css_class('notice')
        notice.set_wrap(True)
        page.append(notice)
        toolbar = Gtk.Box(spacing=10)
        self.search = Gtk.SearchEntry(hexpand=True)
        self.search.set_property('placeholder-text', 'Buscar por nombre o dirección Bluetooth…')
        self.search.connect('search-changed', lambda *_: self.render())
        toolbar.append(self.search)
        self.refresh_button = Gtk.Button(label='Actualizar')
        self.refresh_button.connect('clicked', lambda *_: self.refresh())
        toolbar.append(self.refresh_button)
        page.append(toolbar)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.empty = label('Consultando Bluetooth…', 'empty')
        self.empty.set_wrap(True)
        self.empty.set_justify(Gtk.Justification.CENTER)
        self.empty.set_xalign(0.5)
        self.listbox.set_placeholder(self.empty)
        scroll.set_child(self.listbox)
        page.append(scroll)
        self.status = label('Solo se muestran los dispositivos marcados como de confianza.', 'status')
        self.status.set_wrap(True)
        page.append(self.status)
        tip = label('Mando PS3: tras quitar la confianza, desconecta y reconecta el USB\n'
                    'para volver a solicitar autorización.', 'small')
        tip.set_wrap(True)
        page.append(tip)
        if self.client is not None:
            self.client.subscribe(self.queue_refresh)
            self.refresh()
        else:
            self.queue_refresh()

    def message(self, text, error=False):
        self.status.set_text(text)
        self.status.remove_css_class('error')
        if error:
            self.status.add_css_class('error')

    def queue_refresh(self, *_):
        if not self.disposed and self.refresh_source is None:
            self.refresh_source = GLib.timeout_add(180, self.deferred_refresh)

    def deferred_refresh(self):
        self.refresh_source = None
        self.refresh()
        return False

    def refresh(self):
        if self.disposed:
            return
        if self.refreshing:
            self.refresh_again = True
            return
        try:
            if self.client is None:
                self.client = Bluez()
                self.client.subscribe(self.queue_refresh)
        except GLib.Error as exc:
            self.message('No se pudo acceder a Bluetooth: ' + str(exc), True)
            return
        self.refreshing = True
        self.refresh_button.set_sensitive(False)
        self.client.list_devices(self.loaded)

    def loaded(self, devices, error):
        if self.disposed:
            return
        self.refreshing = False
        self.refresh_button.set_sensitive(True)
        self.devices = devices
        if error:
            self.message(error, True)
            self.empty.set_text('No se pudo consultar Bluetooth. Pulsa Actualizar para reintentar.')
        else:
            self.empty.set_text('No hay dispositivos de confianza.' if not devices else 'No hay coincidencias.')
        self.count.set_text(str(len(devices)))
        self.render()
        if self.refresh_again:
            self.refresh_again = False
            self.queue_refresh()

    def render(self):
        child = self.listbox.get_first_child()
        while child:
            following = child.get_next_sibling()
            # A placeholder is managed by GtkListBox, not a row.
            if isinstance(child, Gtk.ListBoxRow):
                self.listbox.remove(child)
            child = following
        self.buttons = []
        query = self.search.get_text().strip().casefold()
        for device in self.devices:
            if query and query not in (device['name'] + ' ' + device['address']).casefold():
                continue
            box = Gtk.Box(spacing=14)
            box.add_css_class('device')
            icon = Gtk.Image.new_from_icon_name(device['icon'])
            icon.set_pixel_size(30)
            box.append(icon)
            details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, hexpand=True)
            title = label(device['name'], 'device-name')
            title.set_ellipsize(Pango.EllipsizeMode.END)
            title.set_max_width_chars(34)
            title.set_tooltip_text(device['name'])
            details.append(title)
            details.append(label(device['address'] + ' · ' + device['adapter'], 'address'))
            state = 'Conectado' if device['connected'] else 'Desconectado'
            state += ' · vinculación por cable' if device['cable'] else (' · emparejado' if device['paired'] else '')
            details.append(label(state, 'connected' if device['connected'] else 'small'))
            box.append(details)
            button = Gtk.Button(label='Quitar confianza', valign=Gtk.Align.CENTER)
            button.add_css_class('remove')
            button.set_sensitive(not self.busy)
            button.connect('clicked', lambda _, selected=dict(device): self.confirm(selected))
            box.append(button)
            self.buttons.append(button)
            self.listbox.append(box)

    def confirm(self, device):
        if self.busy:
            return
        if self.dialog:
            self.dialog.present()
            return
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
            text='¿Quitar la confianza a este dispositivo?',
            secondary_text=device['name'] + '\n' + device['address'] + '\n\n'
            'Se retirará únicamente su autorización de confianza. No se borrará el emparejamiento '
            'ni se enviará una orden de desconexión. Puede pedir autorización en futuras conexiones.')
        dialog.add_button('Cancelar', Gtk.ResponseType.CANCEL)
        dialog.add_button('Quitar confianza', Gtk.ResponseType.ACCEPT)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        dialog.connect('response', self.confirmed, device)
        self.dialog = dialog
        dialog.present()

    def confirmed(self, dialog, response, device):
        dialog.destroy()
        self.dialog = None
        if response != Gtk.ResponseType.ACCEPT or self.disposed:
            return
        self.busy = True
        for button in self.buttons:
            button.set_sensitive(False)
        self.message('Retirando la confianza a ' + device['name'] + '…')
        self.client.remove_trust(device['path'], device['address'], lambda error: self.removed(device, error))

    def removed(self, device, error):
        if self.disposed:
            return
        self.busy = False
        if error:
            self.message(error, True)
        else:
            self.message('Confianza retirada: ' + device['name'] + ' · ' + device['address'])
        self.render()
        self.refresh()

    def on_close(self, *_):
        self.disposed = True
        if self.refresh_source is not None:
            GLib.source_remove(self.refresh_source)
            self.refresh_source = None
        if self.client:
            self.client.close()
        return False


class Application(Gtk.Application):
    def __init__(self):
        GLib.set_prgname(APP_ID)
        GLib.set_application_name('Confianza Bluetooth')
        super().__init__(application_id=APP_ID)
        self.window = None

    def do_activate(self):
        if self.window is None or self.window.disposed:
            self.window = Window(self)
        self.window.present()


if __name__ == '__main__':
    Application().run(sys.argv)
