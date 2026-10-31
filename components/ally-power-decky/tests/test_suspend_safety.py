import asyncio
import io
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, mock_open, patch

from py_modules.session_lease import SessionLease
from py_modules.session_io import SessionBoundary
from py_modules import manager as m
from py_modules import power_backend as hw


class LeaseTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.epoch = 0
        self.frozen = False
        self.lease = SessionLease(lambda: self.now, lambda: self.epoch, lambda: self.frozen)

    def stable(self):
        for self.now in range(0, 11, 2):
            self.lease.observe(pulse=True)
        self.lease.check(self.lease.token)

    def test_requires_ten_seconds_of_continuous_session_pulses(self):
        self.lease.observe(pulse=True)
        with self.assertRaises(SessionBoundary): self.lease.check(self.lease.token)
        self.stable()

    def test_boottime_jump_rejects_old_lease_even_without_monotonic_gap(self):
        self.stable(); old = self.lease.token
        self.epoch += 60
        with self.assertRaises(SessionBoundary): self.lease.check(old)
        self.assertNotEqual(self.lease.token, old)
        self.assertFalse(self.lease.ready)

    def test_gap_discards_lease_and_needs_full_new_countdown(self):
        self.stable(); old = self.lease.token; self.now += 5
        self.lease.observe(pulse=True)
        self.assertFalse(self.lease.ready)
        for self.now in range(17, 26, 2): self.lease.observe(pulse=True)
        self.assertTrue(self.lease.ready)
        with self.assertRaises(SessionBoundary): self.lease.check(old)

    def test_freezer_immediately_invalidates_without_any_system_write(self):
        self.stable(); self.frozen = True
        with self.assertRaises(SessionBoundary): self.lease.check(self.lease.token)
        self.lease.observe(pulse=True)
        self.assertFalse(self.lease.ready)


class ManagerBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_gate_rechecks_lease_after_waiting_for_logind(self):
        manager = m.Manager()
        manager.session = Mock()
        manager.session.check.side_effect = [None, SessionBoundary('resume')]
        with patch.object(m, 'session_awake', AsyncMock(return_value=True)):
            with self.assertRaises(SessionBoundary): await manager._write_gate('old')
        self.assertEqual(manager.session.check.call_count, 2)

    async def test_prepare_sleep_blocks_before_start_and_writes(self):
        manager = m.Manager(); manager.session = Mock()
        manager._start = AsyncMock(); manager._request = AsyncMock()
        manager.get_state = AsyncMock(return_value={})
        with patch.object(m, 'session_awake', AsyncMock(return_value=False)):
            await manager.apply_cpu(dict(smt=False, cores=4, threads=4), 'old')
        manager._start.assert_not_awaited(); manager._request.assert_not_awaited()

    async def test_frozen_worker_is_not_signalled_or_waited_on(self):
        manager = m.Manager(); process = Mock(returncode=None); manager.proc = process
        manager._send = AsyncMock()
        with patch.object(m, 'session_frozen', return_value=True): await manager._stop()
        manager._send.assert_not_awaited()
        process.kill.assert_not_called(); process.terminate.assert_not_called(); process.wait.assert_not_called()
        self.assertIs(manager.proc, process)

    async def test_scope_must_be_enrolled_before_begin_or_ready_reader(self):
        manager = m.Manager(); manager.get_state = AsyncMock(return_value={
            'host': {'supported': True}, 'gaming': True, 'competitors': [],
            'desktop_busy': False, 'active': False})
        process = Mock(returncode=None)
        manager._send = AsyncMock(); manager._stop = AsyncMock()
        with patch.object(m, 'ryzenadj_path', return_value='unused'), \
             patch.object(m.asyncio, 'create_subprocess_exec', AsyncMock(return_value=process)), \
             patch.object(m, 'enroll_session_scope', AsyncMock(side_effect=SessionBoundary('not scoped'))):
            with self.assertRaises(SessionBoundary): await manager._start()
        manager._send.assert_not_awaited(); self.assertIsNone(manager.reader)


class HardwareBoundaryTests(unittest.TestCase):
    def test_expired_preparation_cannot_continue_cpu_or_smu_io(self):
        with patch.object(hw, 'IO_DEADLINE', 0), patch.object(hw, 'IO_GUARD'), \
             patch.object(hw.subprocess, 'run') as run, patch.object(Path, 'write_text') as write:
            with self.assertRaisesRegex(RuntimeError,'caducada'):hw.write_cpus(True,{0})
            with self.assertRaisesRegex(RuntimeError,'caducada'):hw.write_limits(dict(stapm=15,fast=15,slow=15))
            run.assert_not_called();write.assert_not_called()

    def test_guard_blocks_smu_read_write_and_cpu_hotplug(self):
        with patch.object(hw, 'IO_GUARD', side_effect=SessionBoundary('resume')), \
             patch.object(hw.subprocess, 'run') as run, patch.object(Path, 'write_text') as write:
            for action in [hw.limits, lambda: hw.write_limits(dict(stapm=15, fast=15, slow=15)),
                           lambda: hw.write_cpus(False, {0})]:
                with self.assertRaises(SessionBoundary): action()
            run.assert_not_called(); write.assert_not_called()

    def run_server(self, stdin, session=None):
        controller = Mock(); controller.status.return_value = {}
        output = io.StringIO()
        with patch.object(hw.os, 'geteuid', return_value=0), patch.object(hw.os, 'open', return_value=99), \
             patch.object(hw.os, 'fdopen', mock_open()), patch.object(hw.os, 'fstat', return_value=Mock(st_uid=0)), \
             patch('fcntl.flock'), patch.object(hw.signal, 'signal'), \
             patch.object(hw, 'Controller', return_value=controller), \
             patch.object(hw.sys, 'stdin', io.StringIO(stdin)), patch.object(hw.sys, 'stdout', output):
            try: hw.serve(session=session, restore_on_exit=False)
            except SessionBoundary: pass
        return controller, output.getvalue()

    def test_eof_never_restores_owned_domains(self):
        controller, _ = self.run_server('')
        controller.restore.assert_not_called(); controller.tick.assert_not_called()

    def test_resume_before_dequeue_never_applies_queued_cpu_or_clamp(self):
        session = Mock(); session.check.side_effect = SessionBoundary('resume')
        controller, _ = self.run_server('{"action":"apply_cpu","epoch":0,"config":{"smt":false,"cores":4,"threads":4}}\n', session)
        controller.apply_cpu.assert_not_called(); controller.tick.assert_not_called(); controller.restore.assert_not_called()
