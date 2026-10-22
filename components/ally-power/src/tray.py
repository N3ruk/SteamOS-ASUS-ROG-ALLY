"""KDE StatusNotifierItem + DBusMenu, using the existing Gio session bus."""
from pathlib import Path
import gi
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gio, GLib, GdkPixbuf

MENU_XML = '''<node><interface name="com.canonical.dbusmenu">
<property name="Version" type="u" access="read"/>
<property name="TextDirection" type="s" access="read"/>
<property name="Status" type="s" access="read"/>
<property name="IconThemePath" type="as" access="read"/>
<method name="GetLayout"><arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/><arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/></method>
<method name="GetGroupProperties"><arg type="ai" direction="in"/><arg type="as" direction="in"/><arg type="a(ia{sv})" direction="out"/></method>
<method name="GetProperty"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method>
<method name="Event"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/><arg type="u" direction="in"/></method>
<method name="EventGroup"><arg type="a(isvu)" direction="in"/><arg type="ai" direction="out"/></method>
<method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
<method name="AboutToShowGroup"><arg type="ai" direction="in"/><arg type="ai" direction="out"/><arg type="ai" direction="out"/></method>
<signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
<signal name="ItemsPropertiesUpdated"><arg type="a(ia{sv})"/><arg type="a(ias)"/></signal>
</interface></node>'''


class Tray:
    def __init__(self, window, icon):
        self.window = window
        self.icon = str(icon)
        self.icon_file = Path(self.icon) if Path(self.icon).is_file() else None
        self.icon_name = self.icon_file.stem if self.icon_file else self.icon
        self.icon_theme_path = str(self.icon_file.parent) if self.icon_file else ''
        self.registered = False
        self.tooltip = 'Control de energía del escritorio'
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        # Installed KDE interface is the protocol source of truth.
        xml = Path(__file__).with_name('status-notifier.xml').read_text()
        self.item_info = Gio.DBusNodeInfo.new_for_xml(xml)
        self.menu_info = Gio.DBusNodeInfo.new_for_xml(MENU_XML)
        self.item_id = self.bus.register_object('/StatusNotifierItem', self.item_info.interfaces[0],
                                               self.item_call, self.item_property, None)
        self.menu_id = self.bus.register_object('/MenuBar', self.menu_info.interfaces[0],
                                               self.menu_call, self.menu_property, None)
        self.pixmaps = self.make_pixmaps()
        self.watch_id = Gio.bus_watch_name_on_connection(self.bus, 'org.kde.StatusNotifierWatcher',
                                                        Gio.BusNameWatcherFlags.NONE,
                                                        self.watcher_appeared, self.watcher_vanished)

    def make_pixmaps(self):
        result = []
        if not self.icon_file:
            return result  # The tray host resolves themed icons from the launcher.
        for size in (22, 32, 64):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(self.icon, size, size, True)
            pixels = pixbuf.get_pixels()
            channels = pixbuf.get_n_channels()
            stride = pixbuf.get_rowstride()
            data = bytearray()
            for y in range(pixbuf.get_height()):
                for x in range(pixbuf.get_width()):
                    offset = y * stride + x * channels
                    r, g, b = pixels[offset:offset + 3]
                    a = pixels[offset + 3] if channels == 4 else 255
                    data.extend((a, r, g, b))  # SNI network-order ARGB32.
            result.append((pixbuf.get_width(), pixbuf.get_height(), bytes(data)))
        return result

    def watcher_appeared(self, *_):
        self.bus.call('org.kde.StatusNotifierWatcher', '/StatusNotifierWatcher',
                      'org.kde.StatusNotifierWatcher', 'RegisterStatusNotifierItem',
                      GLib.Variant('(s)', ('/StatusNotifierItem',)), None,
                      Gio.DBusCallFlags.NONE, 3000, None, self.on_registered)

    def on_registered(self, bus, result):
        try:
            bus.call_finish(result)
            self.registered = True
        except GLib.Error:
            self.registered = False

    def watcher_vanished(self, *_):
        self.registered = False
        if not self.window.get_visible() and not self.window.closing:
            self.window.present()

    def item_property(self, connection, sender, path, interface, name):
        strings = {'Category': 'Hardware', 'Id': 'AllyPower', 'Title': 'Ally Power',
                   'Status': 'Active', 'IconThemePath': self.icon_theme_path, 'IconName': self.icon_name,
                   'OverlayIconName': '', 'AttentionIconName': '', 'AttentionMovieName': ''}
        if name in strings:
            return GLib.Variant('s', strings[name])
        if name == 'WindowId':
            return GLib.Variant('i', 0)
        if name == 'Menu':
            return GLib.Variant('o', '/MenuBar')
        if name == 'ItemIsMenu':
            return GLib.Variant('b', False)
        if name in ('IconPixmap', 'OverlayIconPixmap', 'AttentionIconPixmap'):
            return GLib.Variant('a(iiay)', self.pixmaps if name == 'IconPixmap' else [])
        if name == 'ToolTip':
            return GLib.Variant('(sa(iiay)ss)', (self.icon_name, self.pixmaps, 'Ally Power', self.tooltip))
        return None

    def item_call(self, connection, sender, path, interface, method, parameters, invocation):
        if method in ('Activate', 'SecondaryActivate', 'ContextMenu'):
            self.window.present()
        elif method == 'ProvideXdgActivationToken':
            token, = parameters.unpack()
            try:
                self.window.set_startup_id(token)
            except (AttributeError, TypeError):
                pass
        invocation.return_value(None)

    def properties(self, number):
        if number == 0:
            return {'children-display': GLib.Variant('s', 'submenu')}
        return {'label': GLib.Variant('s', 'Abrir Ally Power' if number == 1 else 'Cerrar y conservar'),
                'enabled': GLib.Variant('b', True), 'visible': GLib.Variant('b', True)}

    def menu_property(self, connection, sender, path, interface, name):
        return {'Version': GLib.Variant('u', 3), 'TextDirection': GLib.Variant('s', 'ltr'),
                'Status': GLib.Variant('s', 'normal'), 'IconThemePath': GLib.Variant('as', [])}.get(name)

    def activate_menu(self, number, event):
        if event != 'clicked':
            return
        if number == 1:
            self.window.present()
        elif number == 2:
            self.window.present()
            self.window.begin_shutdown()

    def menu_call(self, connection, sender, path, interface, method, parameters, invocation):
        values = parameters.unpack()
        if method == 'GetLayout':
            parent, depth, requested = values
            children = []
            if parent == 0 and depth != 0:
                children = [GLib.Variant('(ia{sv}av)', (number, self.properties(number), []))
                            for number in (1, 2)]
            result = GLib.Variant('(u(ia{sv}av))', (1, (parent, self.properties(parent), children)))
        elif method == 'GetGroupProperties':
            ids, requested = values
            result = GLib.Variant('(a(ia{sv}))', ([(number, self.properties(number)) for number in ids],))
        elif method == 'GetProperty':
            number, name = values
            result = GLib.Variant('(v)', (self.properties(number).get(name, GLib.Variant('s', '')),))
        elif method == 'AboutToShow':
            result = GLib.Variant('(b)', (False,))
        elif method == 'AboutToShowGroup':
            result = GLib.Variant('(aiai)', ([], []))
        elif method == 'Event':
            self.activate_menu(values[0], values[1])
            result = None
        elif method == 'EventGroup':
            for number, event, data, timestamp in values[0]:
                self.activate_menu(number, event)
            result = GLib.Variant('(ai)', ([],))
        else:
            invocation.return_dbus_error('org.freedesktop.DBus.Error.UnknownMethod', method)
            return
        invocation.return_value(result)

    def update(self, text):
        if self.tooltip != text:
            self.tooltip = text
            self.bus.emit_signal(None, '/StatusNotifierItem', 'org.kde.StatusNotifierItem',
                                 'NewToolTip', None)

    def close(self):
        Gio.bus_unwatch_name(self.watch_id)
        self.bus.unregister_object(self.item_id)
        self.bus.unregister_object(self.menu_id)
        self.registered = False
