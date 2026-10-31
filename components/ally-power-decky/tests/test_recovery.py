import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
from py_modules.recovery import Recovery
from py_modules import manager as m
from py_modules import power_backend as hw

CPU = dict(smt=False, cores=4, threads=4)
BASE = dict(smt=True, online=list(range(16)))
CONTEXT = dict(awake=True, game_id='123', native_tdp=False, tdp_key='false:15')


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.now=0
        self.r=Recovery(clock=lambda:self.now);self.r.enabled=True

    def arm(self, cpu=CPU, tdp=30, prepared=True):
        self.r.arm(cpu,tdp,CONTEXT,0)
        if prepared:self.r.prepared(BASE)
        self.r.resume(60)

    def ready(self):
        for self.now in range(0,11,2):self.r.pulse(CONTEXT,60,True,True,False,[])
        self.assertEqual(self.r.phase,'ready')
        return self.r.pending['id']

    def test_exactly_ten_seconds_of_fresh_pulses_not_twenty(self):
        self.arm()
        for self.now in range(0,10,2):self.r.pulse(CONTEXT,60,False,True,False,[])
        self.assertEqual(self.r.seconds,2)
        self.now=10;self.r.pulse(CONTEXT,60,True,True,False,[])
        self.assertEqual(self.r.phase,'ready')

    def test_each_stage_consumed_once_before_await(self):
        self.arm();identity=self.ready();self.r.claim(identity)
        with self.assertRaises(RuntimeError):self.r.claim(identity)
        self.r.await_cpu(identity);self.r.claim_cpu(identity,60)
        with self.assertRaises(RuntimeError):self.r.claim_cpu(identity,60)
        self.r.finish(identity);self.assertEqual(self.r.phase,'restored')

    def test_snapshot_is_immutable_and_cold_start_never_arms(self):
        original=dict(CPU);self.r.arm(original,20,CONTEXT,0);original['cores']=1
        self.assertEqual(self.r.pending['cpu'],CPU)
        self.assertIsNone(Recovery().pending)

    def test_gap_resets_full_countdown(self):
        self.arm();self.r.pulse(CONTEXT,60,True,True,False,[])
        self.now=6;self.r.pulse(CONTEXT,60,True,True,False,[])
        self.assertEqual(self.r.seconds,10)

    def test_steam_native_takeover_drops_only_tdp(self):
        self.arm();self.r.pulse(dict(CONTEXT,native_tdp=True),60,True,True,False,[])
        self.assertIsNone(self.r.pending['tdp']);self.assertEqual(self.r.pending['cpu'],CPU)

    def test_steam_profile_change_with_disabled_native_also_drops_tdp(self):
        self.arm(cpu=None);self.r.pulse(dict(CONTEXT,tdp_key='false:10'),60,True,True,False,[])
        self.assertIsNone(self.r.pending)

    def test_transient_unidentified_app_waits_without_applying_to_menu(self):
        self.arm();self.r.pulse(dict(CONTEXT,game_id='0'),60,False,True,False,[])
        self.assertIsNotNone(self.r.pending);self.assertEqual(self.r.phase,'waiting')
        self.now=2;self.r.pulse(CONTEXT,60,False,True,False,[])
        self.assertEqual(self.r.seconds,10)

    def test_transient_native_defaults_during_warmup_do_not_claim_takeover(self):
        self.arm(cpu=None);self.r.pulse(dict(CONTEXT,native_tdp=True),60,False,True,False,[])
        self.assertEqual(self.r.pending['tdp'],30)
        for self.now in range(2,10,2):self.r.pulse(CONTEXT,60,False,True,False,[])
        self.now=10;self.r.pulse(CONTEXT,60,True,True,False,[])
        self.assertEqual(self.r.phase,'ready')

    def test_no_cpu_recovery_without_confirmed_pre_sleep_normalization(self):
        self.arm(tdp=None,prepared=False);self.assertIsNone(self.r.pending)

    def test_other_manager_game_or_desktop_cancels_without_retries(self):
        for context,gaming,busy,others in [(CONTEXT,False,False,[]),(CONTEXT,True,True,[]),
            (CONTEXT,True,False,['PowerTools']),(dict(CONTEXT,game_id='456'),True,False,[])]:
            self.arm();self.r.pulse(context,60,True,gaming,busy,others)
            self.assertIsNone(self.r.pending)

    def test_second_suspend_and_manual_edit_invalidate_inflight_id(self):
        self.arm();identity=self.ready();self.r.claim(identity)
        self.r.cancel('manual')
        with self.assertRaises(RuntimeError):self.r.check(identity,60)
        self.arm();self.r.pulse(CONTEXT,120,True,True,False,[])
        self.assertIsNone(self.r.pending)

    def test_deadline_consumes_no_late_retry_and_cancelled_sleep_is_not_resume(self):
        self.arm();self.now=61;self.r.pulse(CONTEXT,60,True,True,False,[])
        self.assertIsNone(self.r.pending)
        self.r.arm(CPU,20,CONTEXT,0);self.r.resume(0)
        self.assertIsNone(self.r.pending)

    def test_option_persists_but_profile_never_survives_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            r=Recovery(directory);self.assertFalse(r.enabled)
            r.set_enabled(True);r.arm(CPU,20,CONTEXT,0)
            fresh=Recovery(directory)
            self.assertTrue(fresh.enabled);self.assertIsNone(fresh.pending)
            self.assertEqual((Path(directory)/'resume.json').read_text(),'{"enabled": true}')

    def test_decky_host_owned_setting_is_loaded_by_root_plugin_after_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            r=Recovery(directory);r.set_enabled(True)
            # Temporary directory/file belong to the test host user, just as
            # Decky's mkdir_as_user/chown leaves them before starting root code.
            with patch('py_modules.recovery.os.geteuid',return_value=0):
                fresh=Recovery(directory)
            self.assertTrue(fresh.enabled);self.assertIsNone(fresh.pending)


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now=0
        self.manager=m.Manager();self.manager.recovery=Recovery(clock=lambda:self.now)
        r=self.manager.recovery;r.enabled=True;r.arm(CPU,30,CONTEXT,0);r.prepared(BASE);r.resume(60)
        for self.now in range(0,11,2):r.pulse(CONTEXT,60,True,True,False,[])
        self.identity=r.pending['id']
        self.manager.session=Mock(ready=True,preparing=False,token='lease')
        self.manager._start=AsyncMock();self.manager.sleep_guard.arm=AsyncMock();self.manager.sleep_guard.watch=AsyncMock()
        self.manager.proc=Mock(returncode=None)
        self.events=[]
        self.actual=copy.deepcopy(BASE)
        async def state():return dict(gaming=True,desktop_busy=False,competitors=[],cpu=copy.deepcopy(self.actual),
            session_ready=True,session_lease='lease',recovery=r.state())
        self.manager.get_state=AsyncMock(side_effect=state)
        async def gate(lease,identity=None):
            if not self.manager.session.ready:raise RuntimeError('lease lost')
            if identity:r.check(identity,60)
        self.manager._write_gate=AsyncMock(side_effect=gate)
        async def request(payload,events,**kwargs):
            self.events.append(copy.deepcopy(payload))
            if payload['action']=='apply_cpu':self.actual.update(smt=payload['config']['smt'],online=[0,1,2,3])
            return {'state':{'cpu':copy.deepcopy(self.actual)}}
        self.manager._request=AsyncMock(side_effect=request)
        patches=[patch.object(m,'suspend_offset',return_value=60),patch.object(hw,'cpu_state',side_effect=lambda:copy.deepcopy(self.actual)),
            patch.object(hw,'topology',return_value=[(i,i+8) for i in range(8)]),
            patch.object(hw,'power_source',return_value={'max_watts':25})]
        for p in patches:p.start();self.addCleanup(p.stop)

    async def test_full_cycle_tdp_before_cpu_and_guard_rearmed_before_cpu_write(self):
        await self.manager.recover_pending(self.identity,'lease',CONTEXT)
        self.assertEqual([e['action'] for e in self.events],['tdp_mode','apply_tdp'])
        self.assertEqual(self.events[-1]['watts'],25)
        self.manager.sleep_guard.arm.assert_not_awaited()
        await self.manager.recover_cpu(self.identity,'lease',CONTEXT)
        self.manager.sleep_guard.arm.assert_awaited_once()
        self.assertEqual(self.events[-1]['action'],'apply_cpu')
        self.assertEqual(self.manager.recovery.phase,'restored')

    async def test_cpu_only_recovery_never_reads_or_writes_tdp(self):
        self.manager.recovery.pending['tdp']=None
        with patch.object(hw,'limits') as limits,patch.object(hw,'write_limits') as writes:
            await self.manager.recover_pending(self.identity,'lease',CONTEXT)
            await self.manager.recover_cpu(self.identity,'lease',CONTEXT)
        self.assertEqual([e['action'] for e in self.events],['apply_cpu'])
        limits.assert_not_called();writes.assert_not_called();self.manager.sleep_guard.watch.assert_not_awaited()

    async def test_tdp_only_never_rearms_or_writes_cpu(self):
        self.manager.recovery.pending['cpu']=None
        await self.manager.recover_pending(self.identity,'lease',CONTEXT)
        self.manager.sleep_guard.arm.assert_not_awaited()
        self.assertNotIn('apply_cpu',[e['action'] for e in self.events])
        self.assertEqual(self.manager.recovery.phase,'restored')

    async def test_manual_edit_after_tdp_prevents_cpu_and_does_not_undo_new_manual_tdp(self):
        await self.manager.recover_pending(self.identity,'lease',CONTEXT)
        self.manager.recovery.cancel('manual')
        before=copy.deepcopy(self.events)
        await self.manager.recover_cpu(self.identity,'lease',CONTEXT)
        self.assertEqual(self.events,before)

    async def test_cancel_during_guard_acquisition_never_sends_cpu_request(self):
        await self.manager.recover_pending(self.identity,'lease',CONTEXT)
        async def arm():self.manager.recovery.cancel('user edited')
        self.manager.sleep_guard.arm.side_effect=arm
        await self.manager.recover_cpu(self.identity,'lease',CONTEXT)
        self.assertNotIn('apply_cpu',[e['action'] for e in self.events])

    async def test_external_cpu_change_is_not_overwritten(self):
        self.actual['online']=[0,1,2,3,4,5,6,7]
        await self.manager.recover_pending(self.identity,'lease',CONTEXT)
        self.assertEqual(self.events,[])

    async def test_fresh_native_takeover_after_tdp_hands_off_without_cpu_reduction(self):
        await self.manager.recover_pending(self.identity,'lease',CONTEXT)
        with patch.object(m,'session_frozen',return_value=False):
            await self.manager.recover_cpu(self.identity,'lease',dict(CONTEXT,native_tdp=True))
        self.assertNotIn('apply_cpu',[e['action'] for e in self.events])
        self.assertEqual(self.events[-1],{'action':'tdp_mode','enabled':False})

    async def test_duplicate_stage_never_repeats_cpu_or_tdp(self):
        await self.manager.recover_pending(self.identity,'lease',CONTEXT)
        await self.manager.recover_cpu(self.identity,'lease',CONTEXT)
        before=copy.deepcopy(self.events)
        await self.manager.recover_pending(self.identity,'lease',CONTEXT)
        await self.manager.recover_cpu(self.identity,'lease',CONTEXT)
        self.assertEqual(self.events,before)

    async def test_prepare_captures_targets_before_cpu_normalization_clears_state(self):
        self.manager.cpu_owned_config=dict(smt=False,online=[0,1,2,3])
        self.manager.cpu_intent=dict(CPU)
        self.manager.state={'tdp_enabled':True,'tdp_target':20}
        self.manager.front_context=dict(CONTEXT);self.manager.front_seen=m.time.monotonic()
        self.manager.sleep_guard.fd=True;self.manager._stop=AsyncMock()
        await self.manager._on_prepare()
        self.assertEqual(self.manager.recovery.pending['cpu'],CPU)
        self.assertEqual(self.manager.recovery.pending['tdp'],20)
        self.assertEqual(self.manager.recovery.pending['baseline'],BASE)
        self.manager.state=None
        with patch.object(m,'suspend_offset',return_value=120):self.manager._on_resume()
        self.assertEqual(self.manager.recovery.phase,'waiting')
        self.manager.sleep_guard.fd=None

    async def test_tdp_only_prepare_records_snapshot_without_scoped_io_or_inhibitor(self):
        self.manager.state={'tdp_enabled':True,'tdp_target':20}
        self.manager.front_context=dict(CONTEXT);self.manager.front_seen=m.time.monotonic()
        self.manager.sleep_guard.fd=None
        await self.manager._on_prepare()
        self.assertEqual(self.manager.recovery.pending['tdp'],20)
        self.assertEqual(self.events,[])

    async def test_ready_status_poll_alone_never_starts_hardware(self):
        await self.manager.frontend_ready(CONTEXT)
        self.manager._start.assert_not_awaited();self.manager._request.assert_not_awaited()

    async def test_enable_option_without_active_tdp_only_changes_own_setting(self):
        self.manager.state=None
        await self.manager.set_recovery(True)
        self.manager._start.assert_not_awaited();self.manager._request.assert_not_awaited()
        self.manager.sleep_guard.watch.assert_not_awaited()

    async def test_expected_worker_epoch_exit_does_not_cancel_snapshot_or_report_hardware_error(self):
        self.manager.proc.stdout.readline=AsyncMock(side_effect=[
            b'{"event":"session_ended","message":"old epoch"}\n',b''])
        self.manager.state={'tdp_enabled':True};self.manager.error=''
        await self.manager._read()
        self.assertIsNone(self.manager.state)
        self.assertEqual(self.manager.error,'');self.assertIsNotNone(self.manager.recovery.pending)

    async def test_slow_tdp_losing_ui_lease_finishes_without_automatic_cpu_or_retry(self):
        original=self.manager._request.side_effect
        async def slow(payload,events,**kwargs):
            result=await original(payload,events,**kwargs)
            if payload['action']=='apply_tdp':self.manager.session.ready=False
            return result
        self.manager._request.side_effect=slow
        await self.manager.recover_pending(self.identity,'lease',CONTEXT)
        self.assertEqual(self.manager.recovery.phase,'skipped')
        self.assertIsNone(self.manager.recovery.active)
        self.assertNotIn('apply_cpu',[e['action'] for e in self.events])
