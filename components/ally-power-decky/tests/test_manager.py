import asyncio
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from py_modules import manager as m
from py_modules import power_backend as hw
from py_modules import live_controller as live


def state(**overrides):
    result = dict(active=False, gaming=True, desktop_busy=False, competitors=[],
                  host={'supported': True, 'reason': ''}, error='')
    result.update(overrides)
    return result


class DiscoveryTests(unittest.TestCase):
    def test_power_tools_and_other_controllers_detected_not_unrelated_apps(self):
        rows = [('backend', '/home/deck/homebrew/plugins/PowerTools/bin/backend'),
                ('PowerTools', 'PowerTools (/home/deck/homebrew/plugins/PowerTools/main.py)'),
                ('python3', 'python3 /home/deck/homebrew/plugins/PowerControl/main.py'),
                ('python3', 'python3 /home/deck/homebrew/plugins/SimpleDeckyTDP/main.py'),
                ('hhd', 'hhd'), ('vpower', '/usr/lib/vpower'),
                ('python3', '/plugins/HueSync/main.py'), ('chrome', 'Chrome')]
        self.assertEqual(m.competitors(rows), ['Handheld Daemon / Adjustor', 'PowerControl', 'PowerTools', 'SimpleDeckyTDP'])

    def test_desktop_and_gamescope_modes(self):
        self.assertFalse(m.in_gaming([('kwin_wayland', 'kwin_wayland')]))
        self.assertTrue(m.in_gaming([('gamescope', '/usr/bin/gamescope')]))
        self.assertTrue(m.in_gaming([('gamescope-wl', '/usr/bin/gamescope -e')]))
        for helper in ('gamescope-sess', 'gamescope-xwm', 'gamescopereaper', 'gamescopectl'):
            self.assertFalse(m.in_gaming([(helper, helper)]))

    def test_host_gate_rejects_other_hardware_and_other_distros(self):
        def read(path):
            return {'/sys/devices/virtual/dmi/id/product_name': 'ROG Ally RC71L_RC71L',
                    '/proc/cpuinfo': 'AMD Ryzen Z1 Extreme', '/etc/os-release': 'ID=steamos'}.get(path, '')
        with patch.object(hw, 'read', side_effect=read), patch.object(m.platform, 'machine', return_value='x86_64'):
            self.assertTrue(m.host_support()['supported'])
        with patch.object(hw, 'read', return_value='Steam Deck'), patch.object(m.platform, 'machine', return_value='x86_64'):
            self.assertFalse(m.host_support()['supported'])

    def test_shared_lock_conflicts_with_desktop_and_is_released(self):
        import fcntl
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'lock'
            path.touch()
            with patch.object(m.os, 'fstat', return_value=Mock(st_uid=0)):
                self.assertFalse(m.lock_busy(path))
                with path.open('r') as held:
                    fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.assertTrue(m.lock_busy(path))
                self.assertFalse(m.lock_busy(path))

    def test_missing_lock_does_not_create_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'missing'
            self.assertFalse(m.lock_busy(path))
            self.assertFalse(path.exists())

    def test_readonly_status_never_calls_ryzenadj_or_writes_hardware(self):
        with patch.object(hw, 'remembered_limits', return_value=None), \
             patch.object(hw, 'asus_limits', return_value=dict(stapm=15, fast=15, slow=15)), \
             patch.object(hw, 'cpu_state', return_value={}), \
             patch.object(hw, 'temperature', return_value=50), \
             patch.object(hw, 'power_source', return_value={}), \
             patch.object(m, 'processes', return_value=[]), \
             patch.object(m, 'host_support', return_value={}), \
             patch.object(hw.subprocess, 'run') as run, \
             patch.object(hw, 'write_limits') as limits, patch.object(hw, 'write_cpus') as cpus:
            self.assertFalse(m.snapshot()['tdp_verified'])
            run.assert_not_called(); limits.assert_not_called(); cpus.assert_not_called()

    def test_yield_keeps_without_tick_or_restore(self):
        controller = Mock()
        controller.status.return_value = {}
        output = io.StringIO()
        from unittest.mock import mock_open
        with patch.object(hw.os, 'geteuid', return_value=0), \
             patch.object(hw.os, 'open', return_value=99), \
             patch.object(hw.os, 'fdopen', mock_open()), \
             patch.object(hw.os, 'fstat', return_value=Mock(st_uid=0)), patch('fcntl.flock'), \
             patch.object(hw.signal, 'signal'), patch.object(hw, 'Controller', return_value=controller), \
             patch.object(hw.sys, 'stdin', io.StringIO('{"action":"yield"}\n')), \
             patch.object(hw.sys, 'stdout', output):
            hw.serve()
        controller.restore.assert_not_called()
        controller.tick.assert_not_called()
        self.assertTrue(json.loads(output.getvalue().splitlines()[-1])['kept'])


class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_conflicts_and_desktop_busy_block_before_worker_creation(self):
        for status in [state(competitors=['PowerTools']), state(desktop_busy=True),
                       state(gaming=False), state(host={'supported': False, 'reason': 'no soportado'})]:
            manager = m.Manager()
            manager.get_state = AsyncMock(return_value=status)
            with patch.object(m.asyncio, 'create_subprocess_exec', new_callable=AsyncMock) as spawn:
                with self.assertRaises(RuntimeError):
                    await manager._start()
                spawn.assert_not_called()

    async def test_invalid_cpu_config_blocks_before_start(self):
        config = dict(smt=True, cores=8, threads=16)
        for current in [dict(config, cores=0), dict(config, watts=15)]:
            manager = m.Manager()
            manager._start = AsyncMock()
            manager.get_state = AsyncMock(return_value=state())
            with patch.object(hw, 'power_source', return_value={'max_watts': 25}), \
                 patch.object(hw, 'topology', return_value=[(i, i+8) for i in range(8)]):
                await manager.apply_cpu(current)
            manager._start.assert_not_called()
            self.assertTrue(manager.error)

    async def test_disabling_tdp_does_not_start_or_write_when_inactive(self):
        manager = m.Manager()
        manager.get_state = AsyncMock(return_value=state())
        manager._request = AsyncMock()
        await manager.set_tdp_mode(False)
        manager._request.assert_not_called()

    async def test_manager_cpu_operation_does_not_require_tdp_mode(self):
        manager = m.Manager()
        manager._start = AsyncMock()
        manager._request = AsyncMock()
        manager.get_state = AsyncMock(return_value=state(tdp_enabled=False))
        config = dict(smt=False, cores=4, threads=4)
        with patch.object(hw, 'topology', return_value=[(i,i+8) for i in range(8)]):
            await manager.apply_cpu(config)
        manager._request.assert_awaited_once_with({'action':'apply_cpu','config':config},{'cpu_applied'})
        self.assertEqual(manager.error,'')

    async def test_manager_blocks_tdp_even_if_cpu_worker_is_active(self):
        manager = m.Manager()
        manager.proc = Mock(returncode=None)
        manager.state = {'tdp_enabled':False}
        manager._request = AsyncMock()
        manager.get_state = AsyncMock(return_value=state(tdp_enabled=False))
        with patch.object(hw,'power_source',return_value={'max_watts':30}):
            await manager.apply_tdp(20)
        manager._request.assert_not_called()
        self.assertIn('desactivado',manager.error)

    async def test_mode_change_and_competitor_yield_no_restore(self):
        for rows in [[('kwin_wayland', '')], [('gamescope', ''), ('PowerTools', '')]]:
            manager = m.Manager()
            manager.proc = Mock(returncode=None)
            async def stop(action):
                self.assertEqual(action, 'yield')
                manager.closing = True
            manager._stop = AsyncMock(side_effect=stop)
            with patch.object(m, 'processes', return_value=rows), \
                 patch.object(m.asyncio, 'sleep', new_callable=AsyncMock):
                await manager.monitor()
            manager._stop.assert_awaited_once_with('yield')

    async def test_plugin_unload_uses_keep_handoff(self):
        manager = m.Manager()
        manager._stop = AsyncMock()
        await manager.close()
        manager._stop.assert_awaited_once_with('yield')

    async def test_renamed_compositor_keeps_worker_alive(self):
        manager = m.Manager()
        manager.proc = Mock(returncode=None)
        manager._send = AsyncMock()
        manager._stop = AsyncMock()
        with patch.object(m, 'processes', return_value=[('gamescope-wl', '/usr/bin/gamescope -e')]), \
             patch.object(m.asyncio, 'sleep', new_callable=AsyncMock,
                          side_effect=[None, asyncio.CancelledError()]):
            with self.assertRaises(asyncio.CancelledError):
                await manager.monitor()
        manager._send.assert_awaited_once_with({'action': 'ping'})
        manager._stop.assert_not_called()

    async def test_worker_eof_fails_pending_request_not_hang(self):
        manager = m.Manager()
        manager.proc = Mock()
        manager.proc.stdout.readline = AsyncMock(return_value=b'')
        future = asyncio.get_running_loop().create_future()
        manager.waiter = ({'applied'}, future)
        await manager._read()
        with self.assertRaises(RuntimeError):
            await future


class IndependentControls(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch.object(live, 'competitors', return_value=[]),
            patch.object(live, 'in_gaming', return_value=True),
            patch.object(hw, 'topology', return_value=[(i,i+8) for i in range(8)]),
            patch.object(hw, 'cpu_state', return_value=dict(smt=True, cores=8, threads=16, online=list(range(16)))),
            patch.object(hw, 'remembered_limits', return_value=None),
            patch.object(hw, 'asus_limits', return_value=dict(stapm=15, fast=15, slow=15)),
            patch.object(hw, 'power_source', return_value={'ac':True,'max_watts':30}),
            patch.object(hw, 'temperature', return_value=50),
            patch.object(hw, 'limits', return_value=dict(stapm=15, fast=15, slow=15)),
            patch.object(hw, 'write_limits', side_effect=lambda values: dict(values)),
            patch.object(hw, 'write_cpus'),
        ]
        for p in self.patches: p.start(); self.addCleanup(p.stop)
        self.ctl = live.LiveController()

    def test_renamed_gaming_compositor_allows_cpu_and_tdp_transactions(self):
        # Exercise the real Gaming detector at the write gate, not a constant True.
        with patch.object(live, 'in_gaming', wraps=m.in_gaming), \
             patch.object(m, 'processes', return_value=[('gamescope-wl', '/usr/bin/gamescope -e')]):
            self.ctl.apply_cpu(dict(smt=False, cores=4, threads=4))
            self.ctl.set_tdp_mode(True)
            self.ctl.apply_tdp(20)
        hw.write_cpus.assert_called_once_with(False, set(range(4)))
        hw.write_limits.assert_called_once_with(dict(stapm=20, fast=20, slow=20))

    def test_cpu_only_start_and_smt_change_never_probe_or_write_tdp(self):
        hw.limits.assert_not_called()
        self.ctl.apply_cpu(dict(smt=False, cores=4, threads=4))
        self.ctl.tick()
        hw.write_cpus.assert_called_once_with(False, set(range(4)))
        hw.limits.assert_not_called(); hw.write_limits.assert_not_called()
        self.assertFalse(self.ctl.tdp_enabled)

    def test_tdp_write_is_rejected_when_native_steam_owns_tdp(self):
        with self.assertRaises(RuntimeError): self.ctl.apply_tdp(20)
        hw.limits.assert_not_called(); hw.write_limits.assert_not_called(); hw.write_cpus.assert_not_called()

    def test_mode_switch_itself_does_not_write_tdp_or_cpu(self):
        self.ctl.set_tdp_mode(True)
        self.assertTrue(self.ctl.tdp_enabled)
        self.ctl.set_tdp_mode(False)
        hw.write_limits.assert_not_called(); hw.write_cpus.assert_not_called()

    def test_tdp_changes_do_not_write_cpu(self):
        self.ctl.set_tdp_mode(True)
        self.ctl.apply_tdp(20)
        hw.write_limits.assert_called_once_with(dict(stapm=20,fast=20,slow=20))
        hw.write_cpus.assert_not_called()

    def test_handoff_to_steam_disables_tdp_clamp_and_crash_restoration(self):
        self.ctl.set_tdp_mode(True); self.ctl.apply_tdp(30)
        self.ctl.set_tdp_mode(False)
        hw.write_limits.reset_mock()
        with patch.object(hw, 'power_source', return_value={'ac':False,'max_watts':25}):
            self.ctl.tick(); self.ctl.restore()
        hw.write_limits.assert_not_called()

    def test_cpu_crash_restore_does_not_restore_native_tdp(self):
        self.ctl.apply_cpu(dict(smt=False,cores=4,threads=4))
        hw.write_cpus.reset_mock()
        self.ctl.restore()
        hw.write_cpus.assert_called_once_with(True,set(range(16)))
        hw.write_limits.assert_not_called()

    def test_unplug_clamps_only_owned_tdp_not_cpu(self):
        self.ctl.set_tdp_mode(True); self.ctl.apply_tdp(30)
        hw.write_limits.reset_mock()
        with patch.object(hw,'power_source',return_value={'ac':False,'max_watts':25}):
            self.ctl.tick()
        hw.write_limits.assert_called_once_with(dict(stapm=25,fast=25,slow=25))
        hw.write_cpus.assert_not_called()

    def test_cpu_failure_rolls_back_cpu_only(self):
        hw.write_cpus.side_effect=[OSError('CPU failed'),None]
        with self.assertRaises(OSError): self.ctl.apply_cpu(dict(smt=False,cores=4,threads=4))
        self.assertEqual(hw.write_cpus.call_count,2)
        hw.write_limits.assert_not_called()

    def test_tdp_failure_rolls_back_tdp_only(self):
        self.ctl.set_tdp_mode(True)
        hw.write_limits.side_effect=[OSError('TDP failed'),dict(stapm=15,fast=15,slow=15)]
        with self.assertRaises(OSError): self.ctl.apply_tdp(20)
        self.assertEqual(hw.write_limits.call_count,2)
        hw.write_cpus.assert_not_called()

    def test_new_competitor_blocks_all_writes_and_crash_restore(self):
        self.ctl.apply_cpu(dict(smt=False,cores=4,threads=4))
        hw.write_cpus.reset_mock()
        with patch.object(live,'competitors',return_value=['PowerTools']):
            with self.assertRaises(RuntimeError): self.ctl.apply_cpu(dict(smt=True,cores=8,threads=16))
            self.ctl.restore(); self.ctl.tick()
        hw.write_cpus.assert_not_called(); hw.write_limits.assert_not_called()


if __name__ == '__main__':
    unittest.main()
