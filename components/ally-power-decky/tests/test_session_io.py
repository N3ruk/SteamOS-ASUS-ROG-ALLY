import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
from py_modules import session_io as s

class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_awake_requires_exact_two_false_properties(self):
        for output,expected in ((b'{"type":"b","data":false}\n{"type":"b","data":false}\n',True),
            (b'{"type":"b","data":true}\n{"type":"b","data":false}',False),
            (b'{"type":"b","data":false}',False),(b'{"type":"b","data":[false]}\n{"type":"b","data":false}',False),(b'bad',False)):
            with patch.object(s,'session_frozen',return_value=False),patch.object(s,'bus_call',AsyncMock(return_value=output)):
                self.assertEqual(await s.session_awake(),expected)
    async def test_awake_fails_closed_on_timeout(self):
        with patch.object(s,'session_frozen',return_value=False),patch.object(s,'bus_call',AsyncMock(side_effect=asyncio.TimeoutError)):
            self.assertFalse(await s.session_awake())
    async def test_frozen_session_never_starts_dbus(self):
        with patch.object(s,'session_frozen',return_value=True),patch.object(s,'bus_call',AsyncMock()) as call:
            self.assertFalse(await s.session_awake())
            with self.assertRaises(s.SessionBoundary): await s.enroll_session_scope(SimpleNamespace(returncode=None,pid=42))
        call.assert_not_awaited()
    async def test_enrollment_uses_only_own_pid_and_user_slice(self):
        process=SimpleNamespace(returncode=None,pid=42)
        async def call(*args):
            unit=args[6]
            self.assertTrue(unit.startswith('ally-power-io-42-'));self.assertTrue(unit.endswith('.scope'))
            self.assertEqual(args[7:],('fail','3','PIDs','au','1','42','Slice','s','user.slice','CollectMode','s','inactive-or-failed','0'))
            return b''
        unit='ally-power-io-42-12345678.scope'
        with patch.object(s,'session_frozen',return_value=False),patch.object(s.uuid,'uuid4',return_value=SimpleNamespace(hex='12345678')), \
            patch.object(s,'bus_call',AsyncMock(side_effect=call)),patch.object(Path,'read_text',return_value='0::/user.slice/'+unit+'\n'):
            self.assertEqual(await s.enroll_session_scope(process),'/user.slice/'+unit)
    async def test_enrollment_waits_for_async_pid_migration(self):
        unit='ally-power-io-42-12345678.scope'
        with patch.object(s,'session_frozen',return_value=False),patch.object(s.uuid,'uuid4',return_value=SimpleNamespace(hex='12345678')), \
            patch.object(s,'bus_call',AsyncMock()) as call,patch.object(Path,'read_text',side_effect=['0::/system.slice/loader.service','0::/user.slice/'+unit]), \
            patch.object(asyncio,'sleep',AsyncMock()) as sleep:
            result=await s.enroll_session_scope(SimpleNamespace(returncode=None,pid=42))
        self.assertEqual(result,'/user.slice/'+unit);sleep.assert_awaited_once_with(.01)
        self.assertEqual(call.await_count,1)
    async def test_unscoped_child_is_rejected_even_after_successful_dbus(self):
        with patch.object(s,'session_frozen',return_value=False),patch.object(s,'bus_call',AsyncMock()),patch.object(Path,'read_text',return_value='0::/system.slice/plugin_loader.service\n'),patch.object(asyncio,'sleep',AsyncMock()):
            with self.assertRaises(s.SessionBoundary): await s.enroll_session_scope(SimpleNamespace(returncode=None,pid=42))

class GuardTests(unittest.TestCase):
    def test_worker_rejects_unscoped_io(self):
        guard=s.WorkerSessionGuard(offset=lambda:0)
        with patch.object(Path,'read_text',return_value='0::/system.slice/plugin_loader.service'):
            with self.assertRaises(s.SessionBoundary): guard.check()
    def test_guard_rechecks_freezer_and_sleep_epoch_before_every_report(self):
        offset=[0.];guard=s.WorkerSessionGuard(offset=lambda:offset[0])
        with patch.object(Path,'read_text',return_value='0::/user.slice/ally-power-io-42-12345678.scope'),patch.object(s,'session_frozen',return_value=False) as frozen:
            guard.check();frozen.return_value=True
            with self.assertRaises(s.SessionBoundary): guard.check()
            frozen.return_value=False;offset[0]=60
            with self.assertRaises(s.SessionBoundary): guard.check()
    def test_missing_freezer_is_not_treated_as_awake(self):
        with patch.object(Path,'read_text',side_effect=FileNotFoundError): self.assertTrue(s.session_frozen())
