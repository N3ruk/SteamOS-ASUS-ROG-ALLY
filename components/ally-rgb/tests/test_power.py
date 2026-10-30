import asyncio
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch
from py_modules import rgb, rgb_hid, power
from test_rgb import DeviceFixture, config

class MonitorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.callback=AsyncMock();self.offset=[0.];self.clock=[100.]
        self.monitor=power.SleepMonitor(self.callback,offset=lambda:self.offset[0],clock=lambda:self.clock[0])
    async def test_missing_signal_invalidates_without_inventing_readiness(self):
        self.offset[0]+=120
        await self.monitor.check_clock()
        self.callback.assert_awaited_once_with(False)
        self.assertFalse(self.monitor.ready)
        await self.monitor.check_clock()
        self.assertEqual(self.callback.await_count,1)
    async def test_slow_event_loop_is_not_a_wake(self):
        self.clock[0]+=1000
        await self.monitor.check_clock()
        self.callback.assert_not_awaited()
    async def test_late_duplicate_is_not_another_wake(self):
        await self.monitor.event(True,'logind');self.offset[0]+=60
        await self.monitor.check_clock();self.clock[0]+=20
        await self.monitor.event(False,'logind')
        self.assertEqual([c.args[0] for c in self.callback.await_args_list],[True,False])
        await self.monitor.event(True,'logind');self.offset[0]+=60
        await self.monitor.event(False,'logind');await self.monitor.check_clock()
        self.assertEqual(self.callback.await_count,4)
    async def test_unload_reaps_observer_boundedly(self):
        process=Mock(returncode=None);process._rgb_waiter=None
        process.wait=AsyncMock(return_value=0)
        async def blocked(): await asyncio.sleep(100)
        process.stdout.readline=AsyncMock(side_effect=blocked)
        with patch.object(asyncio,'create_subprocess_exec',AsyncMock(return_value=process)):
            self.monitor.start();await asyncio.sleep(0)
            await asyncio.wait_for(self.monitor.close(),.7)
        self.assertFalse(self.monitor.tasks);self.assertIsNone(self.monitor.process)

class WakeRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.device=DeviceFixture(root);self.others=[]
        self.manager=rgb.Manager(root/'settings',self.device.hw,rgb.RGBLock(root/'lock',os.geteuid()),
            lambda:self.others,lambda:75,recovery_delay=0,stable_time=0,off_gap=0,poll=.005,wait_limit=.15)
    async def asyncTearDown(self):
        await self.manager.shutdown();self.temp.cleanup()
    async def arm(self,**changes):
        self.manager.settings.save(config(**changes))
        return await self.manager.request_resume()
    async def test_one_off_on_cycle_preserves_saved_profile(self):
        await self.manager.apply(config(zone='zone3',brightness=62))
        saved=self.manager.settings.path.read_bytes()
        with patch.object(self.device.hw,'write',wraps=self.device.hw.write) as write:
            await self.manager.resume()
        self.assertEqual([c.args[1] for c in write.call_args_list],[0,158])
        self.assertEqual(self.manager.settings.path.read_bytes(),saved)
        self.assertEqual(self.manager.editor_zone,'zone3');self.assertEqual(self.manager.phase,'restored')
    async def test_readiness_and_countdown_precede_any_write(self):
        self.manager.require_frontend=True;self.manager.recovery_delay=.06
        with patch.object(self.device.hw,'write',wraps=self.device.hw.write) as write:
            task=await self.arm();await asyncio.sleep(.02);write.assert_not_called()
            acknowledged=time.monotonic();self.manager.frontend_ready()
            await asyncio.sleep(.025);write.assert_not_called();await task
        self.assertGreaterEqual(time.monotonic()-acknowledged,.06);self.assertEqual(write.call_count,2)
    async def test_default_delay_is_ten_seconds(self):
        root=Path(self.temp.name)
        other=rgb.Manager(root/'other',self.device.hw,rgb.RGBLock(root/'otherlock',os.geteuid()))
        self.assertEqual(other.recovery_delay,10);await other.shutdown()
    async def test_unconfirmed_session_skips_without_writing(self):
        self.manager.require_frontend=True
        with patch.object(self.device.hw,'write') as write:
            await (await self.arm())
        write.assert_not_called();self.assertEqual(self.manager.phase,'skipped');self.assertIsNone(self.manager.lock.file)
    async def test_late_device_ready_before_commands(self):
        original=self.device.hw.state;calls=[0]
        def late():
            calls[0]+=1
            if calls[0]<3: raise FileNotFoundError()
            return original()
        with patch.object(self.device.hw,'state',side_effect=late): await (await self.arm(brightness=17))
        self.assertEqual(self.manager.target['brightness'],17)
    async def test_failed_command_is_not_retried(self):
        with patch.object(self.device.hw,'write',side_effect=OSError('failed')) as write:
            await (await self.arm())
        self.assertEqual(write.call_count,1);self.assertEqual(self.manager.phase,'skipped');self.assertIsNone(self.manager.lock.file)
    async def test_competitor_blocks_before_write_or_lock(self):
        self.others[:]=['OpenRGB']
        with patch.object(self.device.hw,'write') as write: await (await self.arm())
        write.assert_not_called();self.assertFalse(self.manager.lock.path.exists());self.assertIn('otro gestor',self.manager.error)
    async def test_kernel_trigger_not_overridden(self):
        (self.device.path/'trigger').write_text('none [disk-activity]')
        with patch.object(self.device.hw,'write') as write: await (await self.arm())
        write.assert_not_called();self.assertIn('disparador',self.manager.error)
    async def test_suspend_cancels_countdown_without_hardware_queries(self):
        self.manager.recovery_delay=.2;task=await self.arm();await asyncio.sleep(.02)
        with patch.object(self.device.hw,'state',side_effect=AssertionError('presleep read')),patch.object(self.device.hw,'write',side_effect=AssertionError('presleep write')):
            await asyncio.wait_for(self.manager.power_event(True),.02);await asyncio.sleep(0)
        self.assertTrue(task.cancelled());self.assertIsNone(self.manager.recovery_task)
    async def test_suspend_between_off_and_on_never_forces_on(self):
        self.manager.off_gap=.2
        with patch.object(self.device.hw,'write',wraps=self.device.hw.write) as write:
            task=await self.arm()
            for _ in range(30):
                if write.call_count: break
                await asyncio.sleep(.005)
            self.assertEqual(write.call_count,1)
            await self.manager.power_event(True);await asyncio.sleep(.03)
            self.assertTrue(task.cancelled());self.assertEqual([c.args[1] for c in write.call_args_list],[0])
    async def test_manual_edit_during_countdown_wins(self):
        self.manager.recovery_delay=.2;task=await self.arm(brightness=5);await asyncio.sleep(.02)
        await self.manager.apply(config(brightness=80));await asyncio.sleep(.03)
        self.assertTrue(task.cancelled());self.assertEqual(self.device.hw.state()['brightness'],204)
    async def test_manual_edit_during_off_gap_wins(self):
        self.manager.off_gap=.2;task=await self.arm(brightness=5)
        for _ in range(100):
            if self.manager.phase=='applying': break
            await asyncio.sleep(.001)
        self.assertEqual(self.manager.phase,'applying')
        await self.manager.apply(config(brightness=80))
        self.assertTrue(task.cancelled());self.assertEqual(self.device.hw.state()['brightness'],204)
    async def test_duplicate_wake_shares_pending_operation(self):
        self.manager.recovery_delay=.02
        with patch.object(self.device.hw,'write',wraps=self.device.hw.write) as write:
            task=await self.arm();self.assertIs(await self.manager.request_resume(),task)
            await self.manager.power_event(False);await task
        self.assertEqual(write.call_count,2)
    async def test_changed_device_during_countdown_skips(self):
        self.manager.recovery_delay=.04;task=await self.arm();await asyncio.sleep(.01)
        original=self.device.hw.state
        with patch.object(self.device.hw,'state',side_effect=lambda:dict(original(),device='/other')),patch.object(self.device.hw,'write') as write: await task
        write.assert_not_called();self.assertEqual(self.manager.phase,'skipped')
    async def test_disabled_or_zero_profile_never_forces_on(self):
        for changes in ({'resume':False},{'enabled':False},{'brightness':0}):
            with patch.object(self.device.hw,'write') as write:
                task=await self.arm(**changes)
                if task: await task
            write.assert_not_called()
    async def test_shutdown_cancels_without_restore(self):
        self.manager.recovery_delay=10;task=await self.arm();await asyncio.sleep(.01)
        with patch.object(self.device.hw,'write') as write:
            await asyncio.wait_for(self.manager.shutdown(),.5);await asyncio.sleep(0)
        write.assert_not_called();self.assertTrue(task.cancelled())
    async def test_disabled_startup_has_no_observers(self):
        factory=Mock();self.manager.monitor_factory=factory
        self.manager.settings.save(config(resume=False));await self.manager.start();await self.manager.startup_task
        factory.assert_not_called();self.assertIsNone(self.manager.power_monitor)
    async def test_status_cannot_arm_recovery(self):
        with patch.object(self.device.hw,'write') as write: state=await self.manager.state()
        write.assert_not_called();self.assertFalse(state['recovery']['pending']);self.assertIsNone(self.manager.power_monitor)

class BrightnessCacheTests(unittest.TestCase):
    def test_close_invalidates_brightness_cache(self):
        transport=rgb_hid.RGBTransport();transport.fd,transport.identity,transport.level=41,('old',),3
        with patch.object(os,'close'): transport.close()
        self.assertIsNone(transport.level)
