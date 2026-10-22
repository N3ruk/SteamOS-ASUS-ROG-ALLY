"""BlueZ client: reads devices and can ONLY set Trusted=false on a selected device."""
import re
from gi.repository import Gio, GLib

DEVICE = 'org.bluez.Device1'
PROPERTIES = 'org.freedesktop.DBus.Properties'
MANAGER = 'org.freedesktop.DBus.ObjectManager'
PATH = re.compile(r'^/org/bluez/hci[0-9]+/dev_([0-9A-Fa-f]{2}(?:_[0-9A-Fa-f]{2}){5})$')


def trusted_devices(objects):
    devices = []
    for path, interfaces in objects.items():
        props = interfaces.get(DEVICE, {})
        if props.get('Trusted') is not True or not PATH.fullmatch(path):
            continue
        adapter_path = props.get('Adapter', path.rsplit('/dev_', 1)[0])
        adapter = objects.get(adapter_path, {}).get('org.bluez.Adapter1', {})
        address = props.get('Address', path.rsplit('dev_', 1)[1].replace('_', ':')).upper()
        devices.append({'path': path, 'address': address,
                        'name': props.get('Alias') or props.get('Name') or address,
                        'connected': bool(props.get('Connected')), 'paired': bool(props.get('Paired')),
                        'cable': bool(props.get('CablePairing')), 'icon': props.get('Icon') or 'bluetooth',
                        'adapter': adapter.get('Alias') or adapter_path.rsplit('/', 1)[-1]})
    return sorted(devices, key=lambda item: (item['name'].casefold(), item['address'], item['path']))


def friendly_error(error):
    text = str(error)
    if any(word in text for word in ('AccessDenied', 'NotAuthorized', 'Permission denied')):
        return 'El sistema denegó el permiso. Comprueba que estás en una sesión local activa de KDE.'
    if any(word in text for word in ('ServiceUnknown', 'NameHasNoOwner')):
        return 'El servicio Bluetooth no está disponible. Actívalo en los ajustes de KDE y pulsa Actualizar.'
    if any(word in text for word in ('UnknownObject', 'DoesNotExist', 'UnknownInterface')):
        return 'El dispositivo ya no está disponible. Actualiza la lista.'
    return text


class Bluez:
    def __init__(self):
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.cancel = Gio.Cancellable()
        self.subscriptions = []
        self.watch = None

    def _call(self, path, interface, method, parameters, callback):
        def finished(bus, result):
            try:
                value = bus.call_finish(result)
            except GLib.Error as exc:
                callback(None, friendly_error(exc))
                return
            callback(value.unpack() if value is not None else None, None)
        self.bus.call('org.bluez', path, interface, method, parameters, None,
                      Gio.DBusCallFlags.NONE, 5000, self.cancel, finished)

    def list_devices(self, done):
        def loaded(result, error):
            if error:
                done([], error)
                return
            done(trusted_devices(result[0]), None)
        self._call('/', MANAGER, 'GetManagedObjects', None, loaded)

    def remove_trust(self, path, address, done):
        match = PATH.fullmatch(path)
        if not match or match[1].replace('_', ':').upper() != address.upper():
            done('La identidad del dispositivo no coincide. Actualiza la lista.')
            return

        def verified(result, error):
            if error:
                done('No se pudo comprobar el resultado: ' + error)
            elif result[0] is not False:
                done('Bluetooth no confirmó la retirada de confianza. Actualiza la lista.')
            else:
                done(None)

        def changed(result, error):
            if error:
                done(error)
                return
            self._call(path, PROPERTIES, 'Get', GLib.Variant('(ss)', (DEVICE, 'Trusted')), verified)

        def checked(result, error):
            if error:
                done(error)
                return
            props = result[0]
            if str(props.get('Address', '')).upper() != address.upper():
                done('El dispositivo cambió mientras confirmabas. Actualiza la lista.')
                return
            if props.get('Trusted') is False:
                done(None)
                return
            if props.get('Trusted') is not True:
                done('No se pudo comprobar la confianza actual del dispositivo.')
                return
            self._call(path, PROPERTIES, 'Set',
                       GLib.Variant('(ssv)', (DEVICE, 'Trusted', GLib.Variant('b', False))), changed)

        # Recheck the exact MAC before changing anything; no name-based matching.
        self._call(path, PROPERTIES, 'GetAll', GLib.Variant('(s)', (DEVICE,)), checked)

    def subscribe(self, callback):
        def changed(*args):
            callback()
        for interface, signal in ((PROPERTIES, 'PropertiesChanged'),
                                  (MANAGER, 'InterfacesAdded'), (MANAGER, 'InterfacesRemoved')):
            self.subscriptions.append(self.bus.signal_subscribe('org.bluez', interface, signal,
                                      None, None, Gio.DBusSignalFlags.NONE, changed))
        self.watch = Gio.bus_watch_name_on_connection(self.bus, 'org.bluez', Gio.BusNameWatcherFlags.NONE,
                                                     changed, changed)

    def close(self):
        self.cancel.cancel()
        for subscription in self.subscriptions:
            self.bus.signal_unsubscribe(subscription)
        if self.watch:
            Gio.bus_unwatch_name(self.watch)
