from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build
import installer


class InstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='trust-package-test-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.package = self.base / 'package'
        self.data = self.base / 'other user' / 'share'
        build.populate(self.package)

    def test_install_update_and_recoverable_uninstall(self):
        self.assertIsNone(installer.install(self.package, self.data))
        directory, desktop, remove, icon = installer.locations(self.data)
        self.assertIn(str(directory / 'app.py'), desktop.read_text())
        self.assertNotIn('/home/deck/', desktop.read_text())
        self.assertTrue(icon.exists())
        backup = installer.install(self.package, self.data)
        self.assertTrue((backup / 'app/app.py').exists())
        recovery = installer.uninstall(self.data)
        self.assertTrue((recovery / 'app/app.py').exists())
        self.assertTrue((recovery / desktop.name).exists())
        for path in (directory, desktop, remove, icon):
            self.assertFalse(path.exists())

    def test_tamper_stops_before_install(self):
        (self.package / 'payload/app.py').write_text('tampered')
        with self.assertRaises(RuntimeError):
            installer.install(self.package, self.data)
        self.assertFalse(self.data.exists())

    def test_symlink_destination_is_not_followed(self):
        directory = installer.locations(self.data)[0]
        directory.parent.mkdir(parents=True)
        directory.symlink_to(self.package, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            installer.install(self.package, self.data)
        installer.verify(self.package)

    def test_failed_update_preserves_previous_app(self):
        installer.install(self.package, self.data)
        directory = installer.locations(self.data)[0]
        (directory / 'note.txt').write_text('keep')
        original = installer.atomic
        calls = 0
        def fail_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError('write failure')
            return original(*args, **kwargs)
        with patch.object(installer, 'atomic', side_effect=fail_once):
            with self.assertRaises(OSError):
                installer.install(self.package, self.data)
        self.assertEqual((directory / 'note.txt').read_text(), 'keep')

    def test_unmanaged_uninstall_refused(self):
        directory = installer.locations(self.data)[0]
        directory.mkdir(parents=True)
        with self.assertRaises(RuntimeError):
            installer.uninstall(self.data)
        self.assertTrue(directory.exists())


if __name__ == '__main__':
    unittest.main()
