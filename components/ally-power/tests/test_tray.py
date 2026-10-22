from pathlib import Path
import unittest
from unittest.mock import Mock
import app
from tray import Tray
from gi.repository import Gio


class TrayPackagingTests(unittest.TestCase):
    def test_bundled_protocol_and_svg_pixmaps(self):
        # Decode the distributed interface and SVG without touching power or publishing a tray item.
        protocol = Gio.DBusNodeInfo.new_for_xml((app.BASE / 'status-notifier.xml').read_text())
        self.assertEqual(protocol.interfaces[0].name, 'org.kde.StatusNotifierItem')
        item = Tray.__new__(Tray)
        item.icon = str(app.TRAY_ICON)
        item.icon_file = Path(item.icon)
        pixmaps = item.make_pixmaps()
        self.assertEqual([(w, h) for w, h, _ in pixmaps], [(22, 22), (32, 32), (64, 64)])
        for width, height, pixels in pixmaps:
            self.assertEqual(len(pixels), width * height * 4)
