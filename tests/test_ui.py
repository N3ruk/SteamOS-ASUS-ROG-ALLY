"""Exercise selection defaults with GTK, without running any installation."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch
from installer import engine, ui

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec('gi'), 'Requires system PyGObject/GTK4')
class SelectionTests(unittest.TestCase):
    def test_nothing_preselected_and_unavailable_decky_not_offered(self):
        import gi
        gi.require_version('Gtk', '4.0')
        from gi.repository import Gtk
        failures = {i: [] for i in engine.CATALOG}
        failures['ally-power-decky'] = ['Decky inactivo']
        failures['ally-rgb'] = ['Decky inactivo']
        def inspect(app, _args):
            app.register(None)
            app.activate()
            try:
                self.assertNotIn('ally-power-decky', app.boxes)
                self.assertNotIn('ally-rgb', app.boxes)
                self.assertEqual(len(app.boxes), len(engine.CATALOG)-2)
                self.assertTrue(all(not box.get_active() for box in app.boxes.values()))
                app.start()
                self.assertIn('No has seleccionado', app.status.get_text())
                self.assertFalse(app.busy)
            finally:
                app.win.destroy()
                app.quit()
            return 0
        with patch.object(Gtk.Application, 'run', inspect), patch.object(engine, 'install') as install:
            self.assertEqual(ui.run(ROOT, list(engine.CATALOG), failures), 0)
            install.assert_not_called()
