import unittest
import os
from unittest.mock import patch
from gi.repository import GLib
import app


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        # Existing UI tests must not depend on the real CPU's current SMT state.
        state = dict(smt=True, smt_control='on', cores=8, threads=16,
                     max_cores=8, max_threads=16, online=list(range(16)))
        item = patch.object(app, 'cpu_state', return_value=state)
        item.start()
        self.addCleanup(item.stop)

    def test_separate_launcher_and_tray_icons(self):
        self.assertEqual(app.Path(app.launcher_icon()).name, 'icon-gaming.png')
        self.assertEqual(app.TRAY_ICON, app.BASE / 'icon.svg')
        self.assertTrue(app.TRAY_ICON.is_file())

    def test_controls_and_battery_range_without_hardware_writes(self):
        app.Gtk.init()
        application = app.Application()
        application.set_application_id('local.AllyPower.Test' + str(os.getpid()))
        application.register(None)
        window = app.Window(application)
        # Start at the registered hardware configuration, not a hard-coded 16 W.
        self.assertEqual(window.config()['watts'], round(app.recorded_state()['limits']['stapm']))
        state = {'cpu': {'smt': True, 'cores': 8, 'threads': 16},
                 'limits': {'stapm': 18}, 'tdp_verified': False, 'tdp_note': 'sin telemetría',
                 'temperature': 48, 'target': None}
        window.show_state(state)
        self.assertEqual(window.config()['watts'], 18)
        self.assertEqual(window.active_tdp.get_text(), '18 W')
        with patch.object(app, 'battery_consumption', return_value='Consumo global actual: 14.2 W'):
            window.poll()
        self.assertEqual(window.tdp_note.get_text(), 'Consumo global actual: 14.2 W')
        window.show_state(state)
        self.assertEqual(window.tdp_note.get_text(), 'Consumo global actual: 14.2 W')
        with patch.object(app, 'battery_consumption', return_value='Consumo global actual: 12.5 W'):
            window.poll()
        self.assertEqual(window.tdp_note.get_text(), 'Consumo global actual: 12.5 W')
        window.slider.set_value(12)
        state['limits']['stapm'] = 20
        window.show_state(state)
        self.assertEqual(window.config()['watts'], 12)
        self.assertEqual(window.active_tdp.get_text(), '20 W')
        self.assertIn('pendiente', window.slider_hint.get_text())
        window.smt.set_active(False)
        self.assertEqual(window.threads.get_value_as_int(), window.cores.get_value_as_int())
        self.assertFalse(window.threads.get_sensitive())
        window.smt.set_active(True)
        window.cores.set_value(4)
        self.assertEqual(window.threads.get_value_as_int(), 8)
        window.threads.set_value(6)
        self.assertEqual(window.config()['threads'], 6)
        with patch.object(app, 'power_source', return_value={'ac': False, 'max_watts': 25, 'battery': 80}):
            window.slider.set_value(30)
            window.poll()
            self.assertEqual(window.slider.get_adjustment().get_upper(), 25)
            self.assertEqual(window.config()['watts'], 25)
            self.assertIn('BATERÍA', window.badge.get_text())
        with patch.object(app, 'power_source', return_value={'ac': True, 'max_watts': 30, 'battery': 80}):
            window.poll()
            self.assertEqual(window.slider.get_adjustment().get_upper(), 30)
            self.assertEqual(window.config()['watts'], 25)
        self.assertIsNone(window.proc)
        # Hiding does not shut down the controller or stop its heartbeat.
        from unittest.mock import Mock
        application.tray = Mock(registered=True)
        window.present()
        self.assertTrue(window.on_close())
        window.close_dialog.response(1)
        self.assertFalse(window.get_visible())
        self.assertFalse(window.closing)
        window.ready = True
        with patch.object(window, 'send') as send:
            window.poll()
            send.assert_called_with({'action': 'ping'})
        window.ready = False
        window.present()
        self.assertTrue(window.get_visible())
        window.on_close()
        window.close_dialog.response(app.Gtk.ResponseType.CANCEL)
        self.assertFalse(window.closing)
        application.tray.registered = False
        window.on_close()
        self.assertFalse(window.close_dialog.get_widget_for_response(1).get_sensitive())
        window.close_dialog.response(app.Gtk.ResponseType.CANCEL)
        # Explicit exit keeps applied settings; hiding never stops the helper.
        from unittest.mock import Mock
        process = Mock()
        process.poll.return_value = None
        window.proc = process
        window.ready = True
        window.can_keep = True
        with patch.object(window, 'send') as send:
            window.on_close()
            window.close_dialog.response(2)
            send.assert_called_once_with({'action': 'quit_keep'})
        self.assertTrue(window.closing)
        window.closing = False
        window.ready = False
        process = object()
        window.proc = process
        window.on_event({'event': 'error', 'message': 'Error concreto de la APU'})
        window.on_exit(process, 1, '')
        self.assertEqual(window.status.get_text(), 'Error concreto de la APU')
        GLib.source_remove(window.poll_id)
        window.destroy()


if __name__ == '__main__':
    unittest.main()
