"""Offline CPU topology regressions; all hardware writes are simulated."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from py_modules import power_backend as hw


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
                     patch.object(hw, 'TOPOLOGY_FILE', Path(temporary.name) / 'no-snapshot'),
                     patch.object(hw, 'TOPOLOGY_CACHE', None)]:
            item.start()
            self.addCleanup(item.stop)

    def snapshot_file(self, snapshot):
        return Mock(lstat=Mock(return_value=SimpleNamespace(st_uid=0, st_mode=0o100644)),
                    read_text=Mock(return_value=json.dumps(snapshot)))

    def test_cold_start_off_and_restart_with_whole_cores_offline(self):
        for smt, wanted, count in [(False, set(range(8)), (8, 8)),
                                   (True, {0, 8, 1, 9}, (2, 4))]:
            hw.TOPOLOGY_CACHE = None
            self.kernel.write(smt, wanted)
            self.assertEqual(hw.topology(), self.kernel.groups)
            state = hw.cpu_state()
            self.assertEqual((state['cores'], state['threads']), count)
            self.assertEqual((state['max_cores'], state['max_threads']), (8, 16))
            self.assertEqual(hw.target_cpus(hw.topology(), 8, 16, True), set(range(16)))

    def test_verified_groups_survive_sysfs_removal_without_debug_or_snapshot(self):
        self.assertEqual(hw.topology(), self.kernel.groups)
        self.kernel.write(False, {0, 1})
        with patch.object(hw, 'CPU_DEBUG', self.kernel.debug / 'denied'):
            self.assertEqual(hw.topology(), self.kernel.groups)

    def test_unprivileged_cold_start_uses_complete_verified_snapshot(self):
        snapshot = hw.topology_snapshot()
        self.kernel.write(False, set(range(8)))
        hw.TOPOLOGY_CACHE = None
        with patch.object(hw, 'CPU_DEBUG', self.kernel.debug / 'denied'), \
             patch.object(hw, 'TOPOLOGY_FILE', self.snapshot_file(snapshot)):
            self.assertEqual(hw.topology(), self.kernel.groups)
            self.assertEqual(hw.cpu_state()['max_cores'], 8)
            self.assertEqual(hw.topology_snapshot(), snapshot)

    def test_zeroed_offline_debug_ids_never_override_verified_snapshot(self):
        snapshot = hw.topology_snapshot()
        self.kernel.write(False, set(range(8)))
        hw.TOPOLOGY_CACHE = None
        for cpu in range(8, 16):
            (self.kernel.debug / str(cpu)).write_text('pkg_id: 0\ncore_id: 0\n')
        with patch.object(hw, 'TOPOLOGY_FILE', self.snapshot_file(snapshot)):
            self.assertEqual(hw.topology(), self.kernel.groups)

    def test_zeroed_offline_debug_ids_without_snapshot_are_not_cached(self):
        self.kernel.write(False, set(range(8)))
        for cpu in range(8, 16):
            (self.kernel.debug / str(cpu)).write_text('pkg_id: 0\ncore_id: 0\n')
        with self.assertRaisesRegex(RuntimeError, 'identificadores incompletos'):
            hw.topology()
        self.assertIsNone(hw.TOPOLOGY_CACHE)

    def test_plugin_snapshot_recovers_offline_restart_without_desktop_install(self):
        snapshot = hw.topology_snapshot()
        self.kernel.write(False, set(range(8)))
        hw.TOPOLOGY_CACHE = None
        for cpu in range(8, 16):
            (self.kernel.debug / str(cpu)).write_text('pkg_id: 0\ncore_id: 0\n')
        with patch.object(hw, 'PLUGIN_TOPOLOGY_FILE', self.snapshot_file(snapshot)):
            self.assertEqual(hw.topology(), self.kernel.groups)
            self.assertEqual(hw.target_cpus(hw.topology(), 8, 16, True), set(range(16)))

    def test_only_fully_visible_topology_is_offered_for_metadata_persistence(self):
        with patch.object(hw, 'remember_cpu_topology') as remember, \
             patch.object(hw, 'write_cpus') as cpus, patch.object(hw, 'write_limits') as watts:
            self.assertEqual(hw.topology(), self.kernel.groups)
            remember.assert_called_once()
            remember.reset_mock()
            hw.TOPOLOGY_CACHE = None
            self.kernel.write(False, set(range(8)))
            self.assertEqual(hw.topology(), self.kernel.groups)
            remember.assert_not_called()
            cpus.assert_not_called()
            watts.assert_not_called()

    def test_unsafe_stale_incomplete_or_symlink_snapshot_is_rejected(self):
        snapshot = hw.topology_snapshot()
        self.kernel.write(False, set(range(8)))
        for variant in ('owner', 'writable', 'symlink', 'machine', 'present', 'ids', 'visible_id', 'boolean'):
            with self.subTest(variant=variant):
                hw.TOPOLOGY_CACHE = None
                data = json.loads(json.dumps(snapshot))
                fake = self.snapshot_file(data)
                info = fake.lstat.return_value
                if variant == 'owner': info.st_uid = 1000
                elif variant == 'writable': info.st_mode = 0o100666
                elif variant == 'symlink': info.st_mode = 0o120777
                elif variant == 'machine': data['identity'] = {}
                elif variant == 'present': data['present'] = [0]
                elif variant == 'ids': del data['ids']['15']
                elif variant == 'visible_id': data['ids']['0'] = [0, 99]
                elif variant == 'boolean': data['ids']['8'] = [False, 0]
                fake.read_text.return_value = json.dumps(data)
                with patch.object(hw, 'CPU_DEBUG', self.kernel.debug / 'denied'), \
                     patch.object(hw, 'TOPOLOGY_FILE', fake):
                    with self.assertRaisesRegex(RuntimeError, 'topología física'):
                        hw.topology()
                    self.assertIsNone(hw.TOPOLOGY_CACHE)
