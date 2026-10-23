import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
from installer import decky, engine, launchers

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='suite-tests-')
        self.home = Path(self.tmp.name) / 'usuario con espacios $dolar'
        self.home.mkdir()
        self.desktop = self.home / 'Escritorio'
        self.data = self.home / '.local/share'
        self.state = self.home / '.local/state'
        self.env = patch.dict(os.environ, {'XDG_DATA_HOME': str(self.data), 'XDG_STATE_HOME': str(self.state)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def install(self, component='return-gaming'):
        return launchers.install(component, ROOT / 'components' / component, self.home, self.desktop)

    def target(self):
        return self.data / 'applications/Return.desktop'

    def test_installs_without_running_commands_or_switching_session(self):
        with patch.object(launchers.subprocess, 'run', side_effect=AssertionError('No commands during file installation')):
            self.install()
        self.assertIn('Volver', self.target().read_text())
        self.assertIn(str(self.home).replace('$', '\\$'), self.target().read_text())
        self.assertTrue((self.desktop / 'Return.desktop').exists())

    def test_restores_original_bytes_and_permissions(self):
        self.target().parent.mkdir(parents=True)
        self.target().write_text('Original\n')
        self.target().chmod(0o700)
        self.install()
        backup = launchers.uninstall('return-gaming', self.home)
        self.assertEqual(self.target().read_text(), 'Original\n')
        self.assertEqual(self.target().stat().st_mode & 0o777, 0o700)
        self.assertTrue(backup.exists())

    def test_restores_original_dangling_desktop_symlink(self):
        self.desktop.mkdir()
        target = self.desktop / 'Return.desktop'
        target.symlink_to('/usr/share/applications/SteamOS-Return.desktop')
        self.install()
        self.assertFalse(target.is_symlink())
        launchers.uninstall('return-gaming', self.home)
        self.assertTrue(target.is_symlink())
        self.assertEqual(os.readlink(target), '/usr/share/applications/SteamOS-Return.desktop')

    def test_reinstall_keeps_first_original(self):
        self.target().parent.mkdir(parents=True)
        self.target().write_text('Initial')
        self.install()
        self.install()
        launchers.uninstall('return-gaming', self.home)
        self.assertEqual(self.target().read_text(), 'Initial')

    def test_removes_new_files_and_preserves_recoverable_receipt(self):
        self.install()
        backup = launchers.uninstall('return-gaming', self.home)
        self.assertFalse(self.target().exists())
        self.assertFalse((self.desktop / 'Return.desktop').exists())
        self.assertEqual(json.loads(backup.read_text())['component'], 'return-gaming')

    def test_install_and_uninstall_refuse_user_changes_before_any_write(self):
        receipt = self.install()
        self.target().write_text('My edit')
        before = receipt.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'modificado'):
            self.install()
        with self.assertRaisesRegex(RuntimeError, 'modificado'):
            launchers.uninstall('return-gaming', self.home)
        self.assertEqual(receipt.read_bytes(), before)
        self.assertEqual(self.target().read_text(), 'My edit')
        self.assertTrue((self.desktop / 'Return.desktop').exists())

    def test_rejects_symlink_parent_without_modifying_outside(self):
        outside = self.home / 'outside'
        outside.mkdir()
        (self.home / '.local').symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, 'enlazado'):
            self.install()
        self.assertEqual(list(outside.iterdir()), [])

    def test_rollback_after_intermediate_write_failure(self):
        first = self.home / 'first'
        second = self.home / 'second'
        first.write_text('before')
        real_put = launchers.put
        failed = False
        def fail_once(path, state):
            nonlocal failed
            if path == second and not failed:
                failed = True
                raise OSError('Simulated disk failure')
            return real_put(path, state)
        with patch.object(launchers, 'put', side_effect=fail_once):
            with self.assertRaises(OSError):
                launchers.transaction({first: launchers.file_state('after'), second: launchers.file_state('new')})
        self.assertEqual(first.read_text(), 'before')
        self.assertFalse(second.exists())

    def test_preflight_validates_all_targets_before_changing_any(self):
        self.desktop.mkdir()
        (self.desktop / 'Return.desktop').mkdir()
        with self.assertRaises(RuntimeError):
            self.install()
        self.assertFalse(self.target().exists())

    def test_toggle_install_does_not_create_desktop_shortcut_or_run_script(self):
        with patch.object(launchers.subprocess, 'run', side_effect=AssertionError):
            self.install('default-mode')
        target = self.data / 'applications/steamos-default-mode-toggle.desktop'
        self.assertTrue(target.exists())
        self.assertFalse(self.desktop.exists())
        launchers.uninstall('default-mode', self.home)
        self.assertFalse(target.exists())

    def test_concurrent_install_rejected(self):
        with launchers.locked('return-gaming', self.home):
            with self.assertRaisesRegex(RuntimeError, 'en curso'):
                self.install()
        self.assertFalse(self.target().exists())

    def test_relative_xdg_rejected(self):
        with patch.dict(os.environ, {'XDG_DATA_HOME': 'relative'}):
            with self.assertRaisesRegex(RuntimeError, 'absolutas'):
                self.install()

    def test_generated_desktop_files_validate(self):
        self.install()
        self.install('default-mode')
        for path in (self.data / 'applications').glob('*.desktop'):
            result = subprocess.run(['desktop-file-validate', str(path)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'test').write_bytes(b'good')
        self.manifest = {'schema': 1, 'components': ['return-gaming'],
                         'sha256': {'test': hashlib.sha256(b'good').hexdigest()}}
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        (self.root / 'manifest.json').write_text(json.dumps(self.manifest))

    def test_valid_manifest_and_corruption(self):
        engine.verify(self.root)
        (self.root / 'test').write_bytes(b'bad')
        with self.assertRaisesRegex(RuntimeError, 'Integridad'):
            engine.verify(self.root)

    def test_traversal_rejected(self):
        self.manifest['sha256'] = {'../outside': 'abc'}
        self.save()
        with self.assertRaisesRegex(RuntimeError, 'segura'):
            engine.verify(self.root)

    def test_symlink_payload_rejected(self):
        (self.root / 'test').unlink()
        (self.root / 'test').symlink_to(ROOT / 'README.md')
        with self.assertRaises(RuntimeError):
            engine.verify(self.root)

    def test_unknown_catalog_rejected(self):
        self.manifest['components'] = ['foreign']
        self.save()
        with self.assertRaisesRegex(RuntimeError, 'Catálogo'):
            engine.verify(self.root)

    def test_disabled_decky_is_not_eligible(self):
        with patch.object(engine, 'host_errors', return_value=[]), patch.object(engine, 'ally_errors', return_value=[]), \
             patch.object(decky, 'availability', return_value=(False, 'Decky apagado')):
            self.assertEqual(engine.requirements('ally-power-decky', ROOT), ['Decky apagado'])


class DeckyDiscoveryTests(unittest.TestCase):
    def test_requires_active_service_and_installed_unit(self):
        for active, unit, expected in [(0, '/usr/bin/PluginLoader', True), (1, '/usr/bin/PluginLoader', False), (0, '', False)]:
            with self.subTest(active=active, unit=unit):
                with patch.object(decky.subprocess, 'run', side_effect=[Mock(returncode=active), Mock(returncode=0, stdout=unit)]), \
                     patch.object(decky.importlib.util, 'find_spec', return_value=True):
                    self.assertEqual(decky.availability()[0], expected)

    def test_missing_dependency_does_not_install_anything(self):
        with patch.object(decky.subprocess, 'run', side_effect=[Mock(returncode=0), Mock(returncode=0, stdout='loader')]) as run, \
             patch.object(decky.importlib.util, 'find_spec', return_value=None):
            self.assertFalse(decky.availability()[0])
            self.assertEqual(run.call_count, 2)


class DeckyProtocolTests(unittest.IsolatedAsyncioTestCase):
    def client(self, previous=None, active=False):
        client = decky.Client(None, None)
        version = '1.1.2'
        async def call(route, *args):
            if route == 'loader/get_plugins':
                if not hasattr(client, 'registered'):
                    return [previous] if previous else []
                return [{'name': 'Ally Power', 'version': version}]
            if route == 'loader/call_plugin_method':
                return {'active': active, 'version': version}
            if route == 'utilities/confirm_plugin_install':
                client.registered = True
        client.call = AsyncMock(side_effect=call)
        client.prompt = AsyncMock(return_value=['Ally Power', version, 'request-id', 'digest', 2 if previous else 0])
        return client

    async def test_only_expected_request_is_confirmed_no_hardware_methods(self):
        client = self.client()
        result = await client.install(ROOT / 'test.zip', 'digest', '1.1.2')
        self.assertIn('backend comprobado', result)
        routes = [c.args[0] for c in client.call.call_args_list]
        self.assertNotIn('set_tdp', str(client.call.call_args_list))
        self.assertEqual(routes.count('utilities/confirm_plugin_install'), 1)
        method = [c for c in client.call.call_args_list if c.args[0] == 'loader/call_plugin_method'][0]
        self.assertEqual(method.args, ('loader/call_plugin_method', 'Ally Power', 'get_state'))

    async def test_mismatched_hash_never_confirmed(self):
        client = self.client()
        client.prompt.return_value[3] = 'wrong'
        with self.assertRaisesRegex(RuntimeError, 'no coincide'):
            await client.install(ROOT / 'test.zip', 'digest', '1.1.2')
        self.assertNotIn('utilities/confirm_plugin_install', [c.args[0] for c in client.call.call_args_list])

    async def test_active_existing_plugin_never_updated(self):
        client = self.client({'name': 'Ally Power', 'version': '1.1.0'}, active=True)
        with self.assertRaisesRegex(RuntimeError, 'controla el hardware'):
            await client.install(ROOT / 'test.zip', 'digest', '1.1.2')
        self.assertNotIn('utilities/install_plugin', [c.args[0] for c in client.call.call_args_list])

    async def test_update_makes_backup_before_request(self):
        client = self.client({'name': 'Ally Power', 'version': '1.1.0'})
        with patch.object(decky, 'backup_previous', return_value=Path('/tmp/backup.zip')) as backup:
            result = await client.install(ROOT / 'test.zip', 'digest', '1.1.2')
        backup.assert_called_once_with('1.1.0')
        self.assertIn('/tmp/backup.zip', result)


class SessionScriptTests(unittest.TestCase):
    def test_return_cancel_never_calls_steamosctl(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            for name, text in [('kdialog', '#!/bin/sh\nexit 1\n'), ('steamosctl', '#!/bin/sh\necho called >> "$LOG"\n')]:
                path = folder / name
                path.write_text(text)
                path.chmod(0o755)
            log = folder / 'log'
            result = subprocess.run(['/bin/bash', str(ROOT / 'components/return-gaming/return-to-gaming.sh')],
                                    env={**os.environ, 'PATH': str(folder), 'LOG': str(log)})
            self.assertEqual(result.returncode, 0)
            self.assertFalse(log.exists())

    def test_toggle_fake_state_is_read_back_and_verified(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            state = folder / 'state'
            state.write_text('game')
            script = folder / 'steamosctl'
            script.write_text('#!/bin/sh\ncase "$1" in\nget-default-login-mode) /bin/cat "$STATE";;\nset-default-login-mode) printf %s "$2" > "$STATE";;\n*) exit 1;;\nesac\n')
            script.chmod(0o755)
            dialog = folder / 'kdialog'
            dialog.write_text('#!/bin/sh\nexit 0\n')
            dialog.chmod(0o755)
            env = {**os.environ, 'PATH': str(folder) + ':/usr/bin', 'STATE': str(state)}
            result = subprocess.run(['/bin/bash', str(ROOT / 'components/default-mode/toggle-default-mode.sh')], env=env, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(state.read_text(), 'desktop')


if __name__ == '__main__':
    unittest.main()
