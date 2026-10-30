"""Pulsed session recovery: fake clocks, temporary LEDs, no host PM actions."""
import asyncio
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
from py_modules import rgb, rgb_hid
from test_rgb import DeviceFixture, config

class WakeRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.device=DeviceFixture(root);self.others=[]
        self.clock=[100.];self.offset=[0.];self.frozen=[False]
        self.manager=rgb.Manager(root/'settings',self.device.hw,rgb.RGBLock(root/'lock',os.geteuid()),
            lambda:self.others,lambda:75,clock=lambda:self.clock[0],offset=lambda:self.offset[0],
            frozen=lambda:self.frozen[0],recovery_delay=10,wait_limit=60)
    async def asyncTearDown(self):
        await self.manager.shutdown();self.temp.cleanup()
    async def arm(self,**changes):
        self.manager.settings.save(config(**changes))
        self.manager.editor_zone=self.manager.settings.config['zone']
        await self.manager.start()
    async def pulses(self,seconds=12):
        for _ in range(seconds//2):
            self.clock[0]+=2;await self.manager.frontend_ready()
    async def test_single_direct_restore_preserves_saved_profile(self):
        await self.arm(zone='zone3',brightness=62)
        saved=self.manager.settings.path.read_bytes()
        with patch.object(self.device.hw,'write',wraps=self.device.hw.write) as write:
            await self.manager.frontend_ready();await self.pulses(12)
        self.assertEqual([c.args[1] for c in write.call_args_list],[158])
        self.assertEqual(self.manager.settings.path.read_bytes(),saved)
        self.assertEqual(self.manager.editor_zone,'zone3');self.assertEqual(self.manager.phase,'restored')
        self.assertIsNone(self.manager.task);self.assertIsNone(self.manager.lock.file)
    async def test_no_timers_observers_or_rgb_reads_before_pulses(self):
        with patch.object(self.device.hw,'state',side_effect=AssertionError('RGB read')),patch.object(self.device.hw,'write') as write:
            await self.arm();await asyncio.sleep(.02);await self.manager.state()
            self.clock[0]+=30
        write.assert_not_called();self.assertIsNone(self.manager.task)
        self.assertIsNone(self.manager.startup_task);self.assertIsNone(self.manager.power_monitor)
    async def test_continuous_pulses_and_ten_seconds_precede_any_write(self):
        await self.arm()
        with patch.object(self.device.hw,'write',wraps=self.device.hw.write) as write:
            await self.manager.frontend_ready();await self.pulses(8);write.assert_not_called()
            await self.pulses(2);self.assertEqual(write.call_count,1)
    async def test_gap_restarts_countdown(self):
        await self.arm();await self.manager.frontend_ready();await self.pulses(6)
        self.clock[0]+=5
        with patch.object(self.device.hw,'write',wraps=self.device.hw.write) as write:
            await self.manager.frontend_ready();await self.pulses(8);write.assert_not_called()
            await self.pulses(2);self.assertEqual(write.call_count,1)
    async def test_monotonic_stall_alone_is_not_resume(self):
        await self.arm();await self.manager.frontend_ready();await self.pulses(10)
        self.clock[0]+=1000
        with patch.object(self.device.hw,'write') as write: await self.manager.frontend_ready()
        write.assert_not_called();self.assertIsNone(self.manager.pending)
    async def test_suspended_clock_arms_once_only_on_fresh_session_pulses(self):
        await self.arm();await self.manager.frontend_ready();await self.pulses(10)
        self.offset[0]+=120
        with patch.object(self.device.hw,'write',wraps=self.device.hw.write) as write:
            await self.manager.frontend_ready();await self.pulses(12)
            await asyncio.gather(*(self.manager.frontend_ready() for _ in range(5)))
        self.assertEqual(write.call_count,1)
    async def test_frozen_queued_pulse_neither_reaps_nor_advances(self):
        await self.arm();await self.manager.frontend_ready();await self.pulses(8)
        self.offset[0]+=60;self.frozen[0]=True;self.clock[0]+=2
        with patch.object(self.manager.io,'close',AsyncMock()) as close,patch.object(self.device.hw,'write') as write:
            await self.manager.frontend_ready();close.assert_not_awaited();write.assert_not_called()
        self.assertEqual(self.manager.baseline,0)
        self.frozen[0]=False;await self.manager.frontend_ready();await self.pulses(8)
        self.assertEqual(self.manager.phase,'countdown')
    async def test_manual_edit_during_countdown_wins(self):
        await self.arm(brightness=5);await self.manager.frontend_ready();await self.pulses(6)
        await self.manager.apply(config(brightness=80));await self.pulses(12)
        self.assertEqual(self.device.hw.state()['brightness'],204);self.assertIsNone(self.manager.pending)
    async def test_manual_edit_while_preflight_awaits_cancels_auto_before_write(self):
        await self.arm(brightness=5);self.manager.recovery_delay=0
        entered=asyncio.Event();proceed=asyncio.Event()
        async def awake(): entered.set();await proceed.wait();return True
        self.manager.awake=awake
        with patch.object(self.device.hw,'write',wraps=self.device.hw.write) as write:
            automatic=asyncio.create_task(self.manager.frontend_ready());await entered.wait()
            manual=asyncio.create_task(self.manager.apply(config(brightness=80)))
            await asyncio.sleep(0);proceed.set();await asyncio.gather(automatic,manual)
        self.assertEqual([c.args[1] for c in write.call_args_list],[204])
    async def test_failed_command_is_not_retried(self):
        await self.arm();await self.manager.frontend_ready()
        with patch.object(self.device.hw,'write',side_effect=OSError('failed')) as write: await self.pulses(20)
        self.assertEqual(write.call_count,1);self.assertEqual(self.manager.phase,'skipped');self.assertIsNone(self.manager.lock.file)
    async def test_competitor_blocks_before_write_or_lock(self):
        await self.arm();self.others[:]=['OpenRGB'];await self.manager.frontend_ready()
        with patch.object(self.device.hw,'write') as write: await self.pulses(10)
        write.assert_not_called();self.assertFalse(self.manager.lock.path.exists());self.assertIn('otro gestor',self.manager.error)
    async def test_kernel_trigger_not_overridden(self):
        await self.arm();(self.device.path/'trigger').write_text('none [disk-activity]')
        await self.manager.frontend_ready()
        with patch.object(self.device.hw,'write',wraps=self.device.hw.write) as write: await self.pulses(10)
        self.assertEqual(self.manager.phase,'skipped');self.assertIn('disparador',self.manager.error)
        self.assertEqual((self.device.path/'trigger').read_text(),'none [disk-activity]')
    async def test_disabled_zero_or_off_profile_never_forces_on(self):
        for changes in ({'resume':False},{'enabled':False},{'brightness':0}):
            self.manager.cancel_pending();await self.arm(**changes)
            with patch.object(self.device.hw,'write') as write:
                await self.manager.frontend_ready();await self.pulses(12)
            write.assert_not_called()
    async def test_shutdown_cancels_without_restore(self):
        await self.arm();await self.manager.frontend_ready()
        with patch.object(self.device.hw,'write') as write:
            await self.manager.shutdown();await self.pulses(12)
        write.assert_not_called();self.assertIsNone(self.manager.pending)
    async def test_no_continuity_skips_without_retry(self):
        await self.arm();self.clock[0]+=61
        with patch.object(self.device.hw,'write') as write:
            await self.manager.frontend_ready();await self.pulses(12)
        write.assert_not_called();self.assertEqual(self.manager.phase,'skipped')
    async def test_disable_during_countdown_is_metadata_only(self):
        await self.arm();await self.manager.frontend_ready()
        with patch.object(self.device.hw,'state',side_effect=AssertionError('read')),patch.object(self.device.hw,'write') as write:
            await self.manager.apply(config(resume=False));await self.pulses(12)
        write.assert_not_called();self.assertIsNone(self.manager.pending)
    async def test_status_cannot_arm_recovery_or_read_hardware(self):
        with patch.object(self.device.hw,'state',side_effect=AssertionError('read')),patch.object(self.device.hw,'write') as write:
            state=await self.manager.state()
        write.assert_not_called();self.assertFalse(state['recovery']['pending'])
    async def test_static_profile_has_no_background_io_or_ownership(self):
        await self.manager.apply(config())
        with patch.object(self.device.hw,'state',side_effect=AssertionError('read')),patch.object(self.device.hw,'write') as write:
            await asyncio.sleep(.02);await self.manager.state();await self.manager.frontend_ready()
        write.assert_not_called();self.assertIsNone(self.manager.task);self.assertIsNone(self.manager.lock.file)
    async def test_animations_stop_at_freezer_without_closing_helper(self):
        await self.manager.apply(config(effect='wave'));self.frozen[0]=True
        with patch.object(self.manager.io,'close',AsyncMock()) as close,patch.object(self.device.hw,'write') as write:
            await asyncio.sleep(.08)
        close.assert_not_awaited();write.assert_not_called();self.assertTrue(self.manager.paused)
    async def test_default_delay_is_ten_seconds(self):
        self.assertEqual(self.manager.recovery_delay,10)

class BrightnessCacheTests(unittest.TestCase):
    def test_close_invalidates_brightness_cache(self):
        transport=rgb_hid.RGBTransport();transport.fd,transport.identity,transport.level=41,('old',),3
        with patch.object(os,'close'): transport.close()
        self.assertIsNone(transport.level)
