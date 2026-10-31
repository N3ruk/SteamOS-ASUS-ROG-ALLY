import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from py_modules import sleep_logind as s
from py_modules import live_controller as live
from py_modules import power_backend as hw
from py_modules import manager as m
from py_modules.sleep_guard import SleepGuard


class LogindTests(unittest.IsolatedAsyncioTestCase):
    async def test_watch_only_subscribes_without_acquiring_any_inhibitor(self):
        guard=s.LogindLease(AsyncMock(),Mock());guard.bus=Mock(connected=True)
        guard.manager=Mock()
        guard.manager.get_preparing_for_sleep=AsyncMock(return_value=False)
        guard.manager.get_preparing_for_shutdown=AsyncMock(return_value=False)
        guard.manager.call_inhibit=AsyncMock()
        await guard.watch()
        guard.manager.call_inhibit.assert_not_awaited();self.assertIsNone(guard.fd)

    async def test_watch_only_prepare_ack_is_sent_even_without_fd(self):
        work=AsyncMock()
        guard=SleepGuard(work,Mock());guard.send=Mock();guard.proc=Mock(returncode=None)
        guard.signal(True);await guard.task
        guard.send.assert_called_once_with('release')
        self.assertIsNone(guard.fd)

    async def test_fd_is_held_before_returning_from_arm_and_closed_after_prepare(self):
        manager = Mock()
        manager.call_inhibit = AsyncMock(return_value=87)
        manager.get_preparing_for_sleep = AsyncMock(return_value=False)
        manager.get_preparing_for_shutdown = AsyncMock(return_value=False)
        manager.get_inhibit_delay_max_u_sec = AsyncMock(return_value=5_000_000)
        bus = Mock(connected=True)
        bus.introspect = AsyncMock(return_value=object())
        bus.get_proxy_object.return_value.get_interface.return_value = manager
        calls=[]
        async def work(): calls.append('cpu-complete')
        def prepare(): calls.append('lease-invalidated'); return work()
        guard = s.LogindLease(prepare, Mock())
        with patch.object(s, 'MessageBus') as factory, patch.object(s.os, 'close', side_effect=lambda fd:calls.append('fd-close')):
            factory.return_value.connect=AsyncMock(return_value=bus)
            await guard.arm()
            manager.call_inhibit.assert_awaited_once_with('sleep','Ally Power CPU',
                'Activar CPU/SMT antes de suspender la Ally','delay')
            self.assertEqual(guard.fd,87);self.assertEqual(calls,[])
            guard.signal(True)
            self.assertEqual(calls,['lease-invalidated'])
            await guard.task
            self.assertEqual(calls,['lease-invalidated','cpu-complete','fd-close'])
            guard.signal(False);guard.on_resume.assert_called_once()
            await guard.close()

    async def test_prepare_failure_releases_fd_and_never_retries(self):
        work = AsyncMock(side_effect=RuntimeError('CPU failed'))
        guard = s.LogindLease(work, Mock());guard.fd=87
        with patch.object(s.os,'close') as close, patch('builtins.print'):
            guard.signal(True);await guard.task
        close.assert_called_once_with(87);work.assert_awaited_once()
        self.assertIsNone(guard.fd)

    async def test_sleep_in_progress_rejects_cpu_reduction_and_closes_fd(self):
        guard = s.LogindLease(AsyncMock(),Mock())
        guard.bus = Mock(connected=True)
        guard.manager = Mock()
        guard.manager.call_inhibit = AsyncMock(return_value=87)
        guard.manager.get_preparing_for_sleep=AsyncMock(return_value=True)
        guard.manager.get_preparing_for_shutdown=AsyncMock(return_value=False)
        guard.manager.get_inhibit_delay_max_u_sec=AsyncMock(return_value=5_000_000)
        with patch.object(s.os,'close') as close:
            with self.assertRaises(RuntimeError): await guard.arm()
        close.assert_not_called()
        guard.manager.call_inhibit.assert_not_awaited()

    async def test_insufficient_logind_delay_refuses_before_fd_or_cpu_control(self):
        guard=s.LogindLease(AsyncMock(),Mock());guard.bus=Mock(connected=True)
        guard.manager=Mock();guard.manager.get_inhibit_delay_max_u_sec=AsyncMock(return_value=1_000_000)
        guard.manager.get_preparing_for_sleep=AsyncMock(return_value=False)
        guard.manager.get_preparing_for_shutdown=AsyncMock(return_value=False)
        guard.manager.call_inhibit=AsyncMock()
        with self.assertRaisesRegex(RuntimeError,'insuficiente'):await guard.arm()
        guard.manager.call_inhibit.assert_not_awaited()


class CPUPreparationTests(unittest.TestCase):
    def setUp(self):
        self.groups=[(i,i+8) for i in range(8)]
        self.cpu=dict(smt=False,cores=4,threads=4,online=[0,1,2,3])
        self.patches=[patch.object(hw,'topology',return_value=self.groups),
            patch.object(hw,'cpu_state',side_effect=lambda *a:self.cpu),
            patch.object(hw,'remembered_limits',return_value=None),patch.object(hw,'asus_limits',return_value={}),
            patch.object(hw,'write_cpus'),patch.object(hw,'write_limits'),patch.object(hw,'limits'),
            patch.object(live,'competitors',return_value=[]),patch.object(live,'in_gaming',return_value=True)]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        self.ctl=live.LiveController()
        self.ctl.cpu_target=dict(smt=False,cores=4,threads=4);self.ctl.cpu_changed=True

    def test_normalization_enables_all_cpu_before_sleep_without_any_tdp_or_hid(self):
        self.ctl.tdp_enabled=True;self.ctl.tdp_target=30
        self.ctl.prepare_sleep()
        hw.write_cpus.assert_called_once_with(True,set(range(16)))
        hw.write_limits.assert_not_called();hw.limits.assert_not_called()
        self.assertFalse(self.ctl.tdp_enabled);self.assertIsNone(self.ctl.cpu_target)

    def test_cpu_not_owned_is_never_normalized(self):
        self.ctl.cpu_target=None;self.ctl.cpu_changed=False;self.ctl.prepare_sleep()
        hw.write_cpus.assert_not_called();hw.write_limits.assert_not_called()

    def test_new_cpu_configuration_or_competitor_is_not_overwritten(self):
        self.cpu['online']=[0,1,2,3,4]
        with self.assertRaises(RuntimeError):self.ctl.prepare_sleep()
        self.cpu['online']=[0,1,2,3]
        with patch.object(live,'competitors',return_value=['PowerTools']):
            with self.assertRaises(RuntimeError):self.ctl.prepare_sleep()
        hw.write_cpus.assert_not_called();hw.write_limits.assert_not_called()

    def test_lost_worker_can_normalize_only_exact_config_owned_in_this_manager(self):
        config=self.ctl.cpu_target;self.ctl.cpu_target=None;self.ctl.cpu_changed=False
        self.ctl.prepare_sleep(config)
        hw.write_cpus.assert_called_once_with(True,set(range(16)))

    def test_safety_relinquish_allowed_after_gaming_exit_but_not_over_competitor(self):
        with patch.object(live,'in_gaming',return_value=False):self.ctl.prepare_sleep()
        hw.write_cpus.assert_called_once_with(True,set(range(16)))

    def test_partial_transaction_and_failed_rollback_record_exact_owned_state_for_pm(self):
        calls=[]
        def write(smt, wanted):
            calls.append((smt,wanted))
            if len(calls)<=2:
                self.cpu['online']=[0,1,2]
                self.cpu['cores']=self.cpu['threads']=3
                raise OSError('partial hotplug')
        hw.write_cpus.side_effect=write
        with self.assertRaises(RuntimeError):self.ctl.apply_cpu(dict(smt=False,cores=2,threads=2))
        self.assertEqual(self.ctl.cpu_owned_state,{'smt':False,'online':[0,1,2]})
        self.ctl.prepare_sleep()
        self.assertEqual(calls[-1],(True,set(range(16))))
        hw.write_limits.assert_not_called()


class CPUAcquisitionTests(unittest.IsolatedAsyncioTestCase):
    async def test_reduction_refused_if_guard_cannot_arm_before_cpu_request(self):
        manager=m.Manager();manager._write_gate=AsyncMock();manager._start=AsyncMock()
        manager._request=AsyncMock();manager.get_state=AsyncMock(return_value={})
        manager.sleep_guard.arm=AsyncMock(side_effect=RuntimeError('inhibitor unavailable'))
        with patch.object(hw,'topology',return_value=[(i,i+8) for i in range(8)]):
            await manager.apply_cpu(dict(smt=False,cores=4,threads=4),'lease')
        manager._request.assert_not_awaited()
        self.assertIn('inhibitor',manager.error)

    async def test_pre_sleep_invalidates_before_waiting_and_clears_ownership_only_on_success(self):
        manager=m.Manager();manager.sleep_guard.fd=87
        manager.proc=Mock(returncode=None);manager.cpu_owned_config=dict(smt=False,cores=4,threads=4)
        manager._request=AsyncMock();manager._stop=AsyncMock()
        task=manager._on_prepare()
        self.assertTrue(manager.session.preparing)
        await task
        manager._request.assert_awaited_once()
        self.assertEqual(manager._request.call_args.args[0]['action'],'prepare_sleep')
        manager._stop.assert_awaited_once_with('yield');self.assertIsNone(manager.cpu_owned_config)
        # Fake FD only: never let destructor/cleanup close an unrelated host fd.
        manager.sleep_guard.fd=None

    async def test_replacement_worker_ready_cannot_erase_owned_cpu_before_preparation(self):
        manager=m.Manager();owned={'smt':False,'online':[0,1,2,3]}
        manager.cpu_owned_config=owned
        manager.proc=Mock()
        manager.proc.stdout.readline=AsyncMock(side_effect=[
            b'{"event":"ready","state":{"cpu_owned":false,"cpu_owned_state":null}}\n',b''])
        await manager._read()
        self.assertEqual(manager.cpu_owned_config,owned)
