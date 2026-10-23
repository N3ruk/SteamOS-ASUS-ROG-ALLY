"""Model Linux hotplug: offline CPUs lose topology/, but retain x86 debug IDs."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from py_modules import power_backend as hw
from py_modules import manager as m
from py_modules.live_controller import LiveController


class HotplugFixture:
    groups = [(i, i + 8) for i in range(8)]

    def __init__(self, root):
        self.cpu = root / 'cpu'
        self.debug = root / 'debug'
        self.debug.mkdir()
        (self.cpu / 'smt').mkdir(parents=True)
        (self.cpu / 'present').write_text('0-15')
        for cpu in range(16):
            (self.debug / str(cpu)).write_text(
                f'online: 0\npkg_id: 0\ncore_id: {cpu % 8}\n')
        self.write(True, set(range(16)))

    def write(self, smt, wanted):
        (self.cpu / 'smt/control').write_text('on' if smt else 'off')
        (self.cpu / 'online').write_text(','.join(map(str, sorted(wanted))))
        for cpu in range(16):
            base = self.cpu / f'cpu{cpu}/topology'
            if cpu in wanted:
                base.mkdir(parents=True, exist_ok=True)
                (base / 'physical_package_id').write_text('0')
                (base / 'core_id').write_text(str(cpu % 8))
                siblings = set(self.groups[cpu % 8]) & wanted
                (base / 'thread_siblings_list').write_text(','.join(map(str, sorted(siblings))))
            elif base.exists():
                for path in base.iterdir():
                    path.unlink()
                base.rmdir()


class OfflineTopologyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.kernel = HotplugFixture(Path(temporary.name))
        for item in [patch.object(hw, 'CPU', self.kernel.cpu),
                     patch.object(hw, 'CPU_DEBUG', self.kernel.debug),
                     patch.object(hw, 'PLUGIN_TOPOLOGY_FILE', self.kernel.debug / 'no-snapshot'),
                     patch.object(hw, 'TOPOLOGY_FILE', self.kernel.debug / 'no-desktop-snapshot'),
                     patch.object(hw, 'TOPOLOGY_CACHE', None)]:
            item.start()
            self.addCleanup(item.stop)

    def test_cold_start_with_smt_off_still_reports_eight_cores_sixteen_threads(self):
        self.kernel.write(False, set(range(8)))
        self.assertEqual(hw.topology(), self.kernel.groups)
        state = hw.cpu_state()
        self.assertEqual((state['cores'], state['threads']), (8, 8))
        self.assertEqual((state['max_cores'], state['max_threads']), (8, 16))
        self.assertEqual(hw.target_cpus(hw.topology(), 8, 16, True), set(range(16)))

    def test_verified_topology_survives_offline_sysfs_removal_without_debugfs(self):
        self.assertEqual(hw.topology(), self.kernel.groups)
        self.kernel.write(False, {0, 1})
        with patch.object(hw, 'CPU_DEBUG', self.kernel.debug / 'unavailable'):
            self.assertEqual(hw.topology(), self.kernel.groups)
            self.assertEqual(hw.cpu_state()['max_cores'], 8)

    def test_restart_with_whole_cores_offline_recovers_their_identity(self):
        self.kernel.write(True, {0, 8, 1, 9})
        self.assertEqual(hw.topology(), self.kernel.groups)
        self.assertEqual(hw.cpu_state()['cores'], 2)
        self.assertEqual(hw.cpu_state()['threads'], 4)

    def test_missing_identity_never_invents_a_physical_core_or_caches_partial_data(self):
        self.kernel.write(False, set(range(8)))
        with patch.object(hw, 'CPU_DEBUG', self.kernel.debug / 'unavailable'):
            with self.assertRaisesRegex(RuntimeError, 'topología física'):
                hw.topology()
        self.assertIsNone(hw.TOPOLOGY_CACHE)
        self.assertEqual(hw.topology(), self.kernel.groups)

    def test_repeated_smt_cycles_and_all_valid_core_thread_combinations(self):
        self.kernel.write(False, set(range(8)))
        with patch.object(hw, 'write_cpus', side_effect=self.kernel.write), \
             patch.object(hw, 'remembered_limits', return_value=None), \
             patch.object(hw, 'asus_limits', return_value={}), \
             patch.object(hw, 'limits') as limits, patch.object(hw, 'write_limits') as watts, \
             patch('py_modules.live_controller.in_gaming', return_value=True), \
             patch('py_modules.live_controller.competitors', return_value=[]):
            controller = LiveController()
            for cycle in range(10):
                for cores in range(1, 9):
                    for smt, threads in [(False, cores), (True, cores), (True, cores * 2)]:
                        config = dict(smt=smt, cores=cores, threads=threads)
                        # Manager prevalidation uses a freshly requested topology too.
                        hw.target_cpus(hw.topology(), cores, threads, smt)
                        controller.apply_cpu(config)
                        actual = hw.cpu_state()
                        self.assertEqual({key: actual[key] for key in config}, config,
                                         (cycle, config))
                        self.assertEqual((actual['max_cores'], actual['max_threads']), (8, 16))
            limits.assert_not_called()
            watts.assert_not_called()


class ManagerHotplugTests(unittest.IsolatedAsyncioTestCase):
    async def test_manager_accepts_reenable_after_smt_off_even_after_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            kernel = HotplugFixture(Path(temporary))
            kernel.write(False, set(range(8)))
            with patch.object(hw, 'CPU', kernel.cpu), patch.object(hw, 'CPU_DEBUG', kernel.debug), \
                 patch.object(hw, 'TOPOLOGY_CACHE', None):
                manager = m.Manager()
                manager._start = AsyncMock()
                manager._request = AsyncMock()
                manager.get_state = AsyncMock(return_value={})
                config = dict(smt=True, cores=8, threads=16)
                await manager.apply_cpu(config)
                self.assertEqual(manager.error, '')
                manager._request.assert_awaited_once_with(
                    {'action': 'apply_cpu', 'config': config}, {'cpu_applied'})
