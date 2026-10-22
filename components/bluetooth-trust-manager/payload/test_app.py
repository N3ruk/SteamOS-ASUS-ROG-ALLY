import os
import unittest
from unittest.mock import Mock
from gi.repository import GLib
import bluetooth_backend as backend
import app

MAC = '02:00:00:00:0F:13'
PATH = '/org/bluez/hci0/dev_02_00_00_00_0F_13'


def props(**changes):
    result = {'Address': MAC, 'Alias': 'PLAYSTATION(R)3 Controller', 'Trusted': True,
              'Connected': False, 'Paired': False, 'CablePairing': True, 'Icon': 'input-gaming'}
    result.update(changes)
    return result


class FakeBus:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def call(self, *args):
        self.calls.append(args[:5])
        result = self.responses.pop(0)
        args[-1](self, result)

    def call_finish(self, result):
        if isinstance(result, Exception):
            raise result
        return result


class BackendTests(unittest.TestCase):
    def client(self, responses):
        client = backend.Bluez.__new__(backend.Bluez)
        client.bus = FakeBus(responses)
        client.cancel = None
        return client

    def getall(self, **changes):
        return GLib.Variant('(a{sv})', ({key: GLib.Variant('b' if isinstance(value, bool) else 's', value)
                                      for key, value in props(**changes).items()},))

    def test_only_trusted_devices_and_duplicate_names_remain_distinct(self):
        other = PATH.replace('0F_13', '0F_14')
        objects = {PATH: {backend.DEVICE: props()},
                   other: {backend.DEVICE: props(Address=MAC[:-2] + '14')},
                   '/org/bluez/hci0/dev_00_00_00_00_00_00': {backend.DEVICE: props(Trusted=False)}}
        devices = backend.trusted_devices(objects)
        self.assertEqual(len(devices), 2)
        self.assertNotEqual(devices[0]['path'], devices[1]['path'])
        self.assertEqual(devices[0]['adapter'], 'hci0')

    def test_set_is_exactly_trusted_false_and_verifies(self):
        client = self.client([self.getall(), GLib.Variant('()', ()),
                              GLib.Variant('(v)', (GLib.Variant('b', False),))])
        done = Mock()
        client.remove_trust(PATH, MAC, done)
        done.assert_called_once_with(None)
        self.assertEqual([call[3] for call in client.bus.calls], ['GetAll', 'Set', 'Get'])
        self.assertEqual(client.bus.calls[1][1], PATH)
        self.assertEqual(client.bus.calls[1][4].unpack(), (backend.DEVICE, 'Trusted', False))

    def test_invalid_path_or_wrong_address_never_touches_bus(self):
        for path, address in [('/org/bluez/hci0', MAC), (PATH, '00:00:00:00:00:00')]:
            client = self.client([])
            done = Mock()
            client.remove_trust(path, address, done)
            self.assertTrue(done.call_args.args[0])
            self.assertEqual(client.bus.calls, [])

    def test_changed_identity_cannot_be_mutated(self):
        client = self.client([self.getall(Address='00:00:00:00:00:00')])
        done = Mock()
        client.remove_trust(PATH, MAC, done)
        self.assertTrue(done.call_args.args[0])
        self.assertEqual(len(client.bus.calls), 1)

    def test_already_untrusted_is_noop(self):
        client = self.client([self.getall(Trusted=False)])
        done = Mock()
        client.remove_trust(PATH, MAC, done)
        done.assert_called_once_with(None)
        self.assertEqual(len(client.bus.calls), 1)

    def test_set_error_is_not_reported_as_success(self):
        client = self.client([self.getall(), GLib.Error('org.bluez.Error.NotAuthorized')])
        done = Mock()
        client.remove_trust(PATH, MAC, done)
        self.assertIn('denegó', done.call_args.args[0])

    def test_unsuccessful_readback_is_not_success(self):
        client = self.client([self.getall(), GLib.Variant('()', ()),
                              GLib.Variant('(v)', (GLib.Variant('b', True),))])
        done = Mock()
        client.remove_trust(PATH, MAC, done)
        self.assertIn('no confirmó', done.call_args.args[0])


class InterfaceTests(unittest.TestCase):
    def test_confirmation_and_refresh_without_real_bluetooth_changes(self):
        app.Gtk.init()
        application = app.Application()
        application.set_application_id('local.BluetoothTrustManager.Test' + str(os.getpid()))
        application.register(None)
        client = Mock()
        devices = backend.trusted_devices({PATH: {backend.DEVICE: props()}})
        client.list_devices.side_effect = lambda done: done(devices, None)
        window = app.Window(application, client)
        self.assertEqual(window.count.get_text(), '1')
        self.assertEqual(len(window.buttons), 1)
        window.search.set_text('no existe')
        window.render()
        self.assertEqual(len(window.buttons), 0)
        window.search.set_text('0F:13')
        window.render()
        self.assertEqual(len(window.buttons), 1)
        window.confirm(devices[0])
        window.dialog.response(app.Gtk.ResponseType.CANCEL)
        client.remove_trust.assert_not_called()
        window.confirm(devices[0])
        window.dialog.response(app.Gtk.ResponseType.ACCEPT)
        self.assertEqual(client.remove_trust.call_args.args[:2], (PATH, MAC))
        self.assertTrue(window.busy)
        client.list_devices.side_effect = lambda done: done([], None)
        client.remove_trust.call_args.args[2](None)
        self.assertFalse(window.busy)
        self.assertEqual(window.count.get_text(), '0')
        self.assertIn('Confianza retirada', window.status.get_text())
        window.on_close()
        window.destroy()
        client.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
