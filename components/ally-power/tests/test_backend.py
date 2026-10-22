import unittest
import io
import json
from unittest.mock import patch
import power_backend as backend


class LogicTests(unittest.TestCase):
    groups = [(i, i + 8) for i in range(8)]

    def test_official_v019_acknowledgement_is_supported(self):
        from unittest.mock import Mock
        result = Mock(returncode=0, stderr='', stdout='\n'.join(
            'Successfully set ' + name + '_limit to 15000' for name in ('stapm', 'fast', 'slow')))
        with patch.object(backend, 'FALLBACK_LIMITS', dict(stapm=16, fast=16, slow=16)), \
             patch.object(backend.subprocess, 'run', return_value=result), \
             patch.object(backend, 'remember_limits') as remember:
            values = dict(stapm=15, fast=15, slow=15)
            self.assertEqual(backend.write_limits(values), values)
            remember.assert_called_once_with(values)

    def test_intentional_close_keeps_but_eof_and_legacy_quit_restore(self):
        from unittest.mock import Mock, mock_open
        for action in ('quit_keep', 'quit', None):
            with self.subTest(action=action):
                controller = Mock()
                controller.status.return_value = {'test': True}
                incoming = '' if action is None else json.dumps({'action': action}) + '\n'
                output = io.StringIO()
                with patch.object(backend.os, 'geteuid', return_value=0), \
                     patch.object(backend.os, 'open', return_value=99), \
                     patch.object(backend.os, 'fdopen', mock_open()), \
                     patch.object(backend.os, 'fstat', return_value=Mock(st_uid=0)), patch('fcntl.flock'), \
                     patch.object(backend.signal, 'signal'), \
                     patch.object(backend, 'Controller', return_value=controller), \
                     patch.object(backend.sys, 'stdin', io.StringIO(incoming)), \
                     patch.object(backend.sys, 'stdout', output):
                    backend.serve()
                events = [json.loads(line) for line in output.getvalue().splitlines()]
                self.assertIn('quit_keep', events[0]['capabilities'])
                self.assertEqual(events[-1]['kept'], action == 'quit_keep')
                if action == 'quit_keep':
                    controller.restore.assert_not_called()
                    controller.tick.assert_called_once()
                else:
                    controller.restore.assert_called_once()

    def test_remembered_limits_require_root_and_matching_asus_configuration(self):
        from unittest.mock import Mock
        path = Mock()
        stat = Mock(st_uid=0, st_mode=0o100644)
        path.stat.return_value = stat
        old = dict(stapm=15, fast=15, slow=15)
        saved = dict(stapm=25, fast=25, slow=25)
        path.read_text.return_value = json.dumps({'asus': old, 'limits': saved})
        with patch.object(backend, 'STATE_FILE', path), \
             patch.object(backend, 'asus_limits', return_value=old):
            self.assertEqual(backend.remembered_limits(), saved)
            stat.st_uid = 1000
            self.assertIsNone(backend.remembered_limits())
            stat.st_uid = 0
            with patch.object(backend, 'asus_limits', return_value=saved):
                self.assertIsNone(backend.remembered_limits())

    def test_blocked_telemetry_uses_explicit_unverified_fallback(self):
        result = type('Result', (), {'returncode': 251, 'stdout': 'Unable to get memory access',
                                     'stderr': ''})()
        with patch.object(backend, 'FALLBACK_LIMITS', None), \
             patch.object(backend.subprocess, 'run', return_value=result) as run, \
             patch.object(backend, 'read', return_value='16'):
            self.assertEqual(backend.limits(), dict(stapm=16, fast=16, slow=16))
            self.assertIsNotNone(backend.FALLBACK_LIMITS)
            backend.limits()
            self.assertEqual(run.call_count, 1)

    def test_fallback_requires_explicit_smu_acknowledgement(self):
        result = type('Result', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()
        with patch.object(backend, 'FALLBACK_LIMITS', dict(stapm=16, fast=16, slow=16)), \
             patch.object(backend.subprocess, 'run', return_value=result):
            with self.assertRaises(RuntimeError):
                backend.write_limits(dict(stapm=3, fast=3, slow=3))
            self.assertEqual(backend.FALLBACK_LIMITS['stapm'], 16)

    def test_every_valid_topology_keeps_cpu_zero_and_exact_counts(self):
        for smt in (False, True):
            for cores in range(1, 9):
                for threads in range(cores, cores * (2 if smt else 1) + 1):
                    target = backend.target_cpus(self.groups, cores, threads, smt)
                    self.assertIn(0, target)
                    self.assertEqual(len(target), threads)
                    self.assertEqual(sum(bool(set(group) & target) for group in self.groups), cores)

    def test_invalid_and_boolean_numbers_rejected(self):
        for config in [dict(watts=31, smt=True, cores=8, threads=16),
                       dict(watts=2, smt=True, cores=8, threads=16),
                       dict(watts=True, smt=True, cores=8, threads=16),
                       dict(watts=10, smt=False, cores=4, threads=8),
                       dict(watts=10, smt=True, cores=0, threads=1),
                       dict(watts=10, smt='on', cores=8, threads=16)]:
            with self.assertRaises(ValueError):
                backend.validate(config, {'max_watts': 30}, self.groups)

    def test_ac_and_battery_caps(self):
        for maximum in (25, 30):
            for watts in range(3, maximum + 1):
                backend.validate(dict(watts=watts, smt=True, cores=8, threads=16),
                                 {'max_watts': maximum}, self.groups)
            with self.assertRaises(ValueError):
                backend.validate(dict(watts=maximum + 1, smt=True, cores=8, threads=16),
                                 {'max_watts': maximum}, self.groups)

    def test_failed_cpu_write_rolls_back_and_does_not_claim_applied(self):
        old_cpu = dict(smt=True, online=list(range(16)))
        old_limits = dict(stapm=16, fast=16, slow=16)
        with patch.object(backend, 'topology', return_value=self.groups), \
             patch.object(backend, 'cpu_state', return_value=old_cpu), \
             patch.object(backend, 'limits', return_value=old_limits), \
             patch.object(backend, 'power_source', return_value={'ac': True, 'max_watts': 30}), \
             patch.object(backend, 'write_limits', return_value=old_limits), \
             patch.object(backend, 'write_cpus', side_effect=[OSError('write failed'), None]) as write:
            controller = backend.Controller()
            with self.assertRaises(OSError):
                controller.apply(dict(watts=15, smt=False, cores=4, threads=4))
            self.assertIsNone(controller.target)
            self.assertEqual(write.call_args.args, (True, set(range(16))))

    def test_unplug_clamps_active_target(self):
        old_cpu = dict(smt=True, online=list(range(16)), cores=8, threads=16)
        with patch.object(backend, 'topology', return_value=self.groups), \
             patch.object(backend, 'cpu_state', return_value=old_cpu), \
             patch.object(backend, 'limits', return_value=dict(stapm=25, fast=25, slow=25)), \
             patch.object(backend, 'temperature', return_value=50), \
             patch.object(backend, 'power_source', return_value={'ac': False, 'max_watts': 25}), \
             patch.object(backend, 'write_limits', return_value=dict(stapm=25, fast=25, slow=25)), \
             patch.object(backend, 'write_cpus'):
            controller = backend.Controller()
            controller.target = dict(watts=30, smt=True, cores=8, threads=16)
            self.assertEqual(controller.tick()['target']['watts'], 25)


if __name__ == '__main__':
    unittest.main()
