import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build
import installer


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ally-package-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.package = self.base / 'package'
        build.populate(self.package)
        self.root = self.base / 'fake-system'
        self.root.mkdir()

    def test_compatible_and_unsupported_models(self):
        for model in ('ROG Ally RC71L_RC71L', 'ROG Ally X RC72LA_RC72LA'):
            for cpu in ('AMD Ryzen Z1', 'AMD Ryzen Z1 Extreme'):
                self.assertEqual(installer.compatibility('steamos', model, cpu, 'x86_64'), [])
        self.assertTrue(installer.compatibility('steamos', 'ROG Xbox Ally', 'AMD Ryzen Z2', 'x86_64'))
        self.assertTrue(installer.compatibility('ubuntu', 'ROG Ally RC71L', 'AMD Ryzen Z1', 'x86_64'))

    def test_tamper_blocks_install_before_writes(self):
        (self.package / 'payload/app.py').write_text('tampered')
        with self.assertRaisesRegex(RuntimeError, 'dañado'):
            installer.install_system(self.package, self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_install_update_uninstall_preserves_backups(self):
        self.assertIsNone(installer.install_system(self.package, self.root))
        directory = self.root / installer.LIB.relative_to('/')
        helper = self.root / installer.HELPER.relative_to('/')
        command = self.root / installer.COMMAND.relative_to('/')
        self.assertEqual((directory / 'VERSION').read_text().strip(), installer.VERSION)
        self.assertIn('-I /usr/local/lib/desktop-power/backend.py', helper.read_text())
        self.assertNotIn('-I', command.read_text())
        self.assertTrue((directory / 'source/RyzenAdj-v0.19.0-source.tar.gz').is_file())
        old = installer.install_system(self.package, self.root)
        self.assertTrue(Path(old).is_dir())
        removed = installer.uninstall_system(self.root)
        self.assertFalse(directory.exists())
        self.assertFalse(helper.exists())
        self.assertFalse(command.exists())
        self.assertTrue((Path(removed) / 'ally-power').exists())
        self.assertTrue(Path(old).exists())

    def test_failed_update_rolls_back(self):
        installer.install_system(self.package, self.root)
        directory = self.root / installer.LIB.relative_to('/')
        (directory / 'user-note.txt').write_text('keep')
        original = installer.atomic_text
        counter = 0
        def fail_once(*args, **kwargs):
            nonlocal counter
            counter += 1
            if counter == 1:
                raise OSError('simulated write failure')
            return original(*args, **kwargs)
        with patch.object(installer, 'atomic_text', side_effect=fail_once):
            with self.assertRaises(OSError):
                installer.install_system(self.package, self.root)
        self.assertEqual((directory / 'user-note.txt').read_text(), 'keep')
        self.assertTrue((self.root / installer.HELPER.relative_to('/')).exists())

    def test_symlink_destination_rejected(self):
        destination = self.root / installer.LIB.relative_to('/')
        destination.parent.mkdir(parents=True)
        elsewhere = self.base / 'unrelated'
        elsewhere.mkdir()
        destination.symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            installer.install_system(self.package, self.root)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_unrelated_directory_is_not_replaced(self):
        destination = self.root / installer.LIB.relative_to('/')
        destination.mkdir(parents=True)
        with self.assertRaises(RuntimeError):
            installer.install_system(self.package, self.root)

    def test_readonly_restored_after_install_failure(self):
        from unittest.mock import Mock, mock_open
        run = Mock(return_value=Mock(stdout='enabled\n'))
        with patch.object(installer.os, 'geteuid', return_value=0), \
             patch.object(installer.os, 'open', return_value=99), \
             patch.object(installer.os, 'fdopen', mock_open()), \
             patch.object(installer.os, 'fstat', return_value=Mock(st_uid=0)), \
             patch.object(installer.fcntl, 'flock'), \
             patch.object(installer, 'preflight', return_value=([], [])), \
             patch.object(installer, 'verify_package'), \
             patch.object(installer, 'install_system', side_effect=OSError('disk full')), \
             patch.object(installer.subprocess, 'run', run):
            with self.assertRaises(OSError):
                installer.root_action()
        self.assertEqual([c.args[0][-1] for c in run.call_args_list], ['status', 'disable', 'enable'])

    def test_invalid_readonly_state_never_installs(self):
        from unittest.mock import Mock, mock_open
        with patch.object(installer.os, 'geteuid', return_value=0), \
             patch.object(installer.os, 'open', return_value=99), \
             patch.object(installer.os, 'fdopen', mock_open()), \
             patch.object(installer.os, 'fstat', return_value=Mock(st_uid=0)), \
             patch.object(installer.fcntl, 'flock'), \
             patch.object(installer, 'preflight', return_value=([], [])), \
             patch.object(installer, 'verify_package'), \
             patch.object(installer, 'install_system') as install, \
             patch.object(installer.subprocess, 'run', return_value=Mock(stdout='unknown')):
            with self.assertRaises(RuntimeError):
                installer.root_action()
            install.assert_not_called()


if __name__ == '__main__':
    unittest.main()
