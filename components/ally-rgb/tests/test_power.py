import asyncio
import copy
import errno
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from py_modules import rgb, rgb_hid, power
from test_rgb import DeviceFixture, config


def signal(value):
    return dict(type='signal', path='/org/freedesktop/login1',
                interface='org.freedesktop.login1.Manager', member='PrepareForSleep',
                payload=dict(type='b', data=[value]))


class MonitorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.callback = AsyncMock()
        self.offset, self.clock = [0.], [100.]
        self.monitor = power.SleepMonitor(self.callback, offset=lambda:self.offset[0], clock=lambda:self.clock[0])

    def test_only_correct_boolean_sleep_signals_are_accepted(self):
        for value in (True, False):
            self.assertIs(power.sleep_signal(json.dumps(signal(value))), value)
        bad = [signal(1), signal('false'), dict(signal(True), member='Unrelated'),
               dict(signal(True), type='method_call'), dict(signal(True), path='/other'),
               dict(signal(True), payload=[]), [], None]
        for event in bad:
            self.assertIsNone(power.sleep_signal(json.dumps(event)))
        self.assertIsNone(power.sleep_signal('not json'))

    async def test_missed_logind_signals_are_covered_by_suspend_clock(self):
        self.offset[0] += 120
        await self.monitor.check_clock()
        self.callback.assert_awaited_once_with(False)
        await self.monitor.check_clock()
        self.assertEqual(self.callback.await_count, 1)

    async def test_slow_event_loop_or_wall_clock_is_not_a_wake(self):
        self.clock[0] += 1000
        await self.monitor.check_clock()
        self.callback.assert_not_awaited()

    async def test_logind_and_clock_deduplicate_both_orders(self):
        await self.monitor.event(True, 'logind')
        self.offset[0] += 60
        await self.monitor.check_clock()
        await self.monitor.event(False, 'logind')
        self.assertEqual([call.args[0] for call in self.callback.await_args_list], [True, False])
        await self.monitor.event(True, 'logind')
        self.offset[0] += 60
        await self.monitor.event(False, 'logind')
        await self.monitor.check_clock()
        self.assertEqual(self.callback.await_count, 4)

    async def test_unload_cancels_readers_and_reaps_monitor(self):
        process = Mock(returncode=None, wait=AsyncMock(return_value=0))
        async def blocked_read():
            await asyncio.sleep(100)
        process.stdout.readline = AsyncMock(side_effect=blocked_read)
        with patch.object(asyncio, 'create_subprocess_exec', AsyncMock(return_value=process)):
            self.monitor.start()
            await asyncio.sleep(0)
            await self.monitor.close()
        process.terminate.assert_called_once()
        self.assertFalse(self.monitor.tasks)
        self.assertIsNone(self.monitor.process)


class WakeRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.device = DeviceFixture(root)
        self.others = []
        self.manager = rgb.Manager(root/'settings', self.device.hw,
            rgb.RGBLock(root/'lock', os.geteuid()), lambda:self.others, lambda:75)

    async def asyncTearDown(self):
        await self.manager.shutdown()
        self.temp.cleanup()

    async def recover(self, **kwargs):
        cfg = copy.deepcopy(self.manager.target)
        await self.manager.pause()
        self.manager.recovery_task = asyncio.create_task(self.manager.recover_wake(cfg, interval=0, settle=0, **kwargs))
        await self.manager.recovery_task

    async def test_wake_without_pause_resends_unchanged_solid_frame_and_closes_cache(self):
        await self.manager.apply(config(effect='solid',brightness=100))
        before = self.manager.settings.path.read_bytes()
        with patch.object(self.device.hw, 'write', wraps=self.device.hw.write) as write, \
             patch.object(self.device.hw, 'close', wraps=self.device.hw.close) as close:
            await self.manager.resume()
            self.assertGreaterEqual(close.call_count, 1)
            write.assert_called_once()
        self.assertEqual(self.manager.settings.path.read_bytes(), before)

    async def test_missing_device_and_transient_io_retry_then_restore_exact_settings(self):
        await self.manager.apply(config(effect='solid', zone='zone3'))
        saved = self.manager.settings.path.read_bytes()
        original = self.device.hw.write
        calls = [FileNotFoundError(errno.ENOENT, 'late'), OSError(errno.EIO, 'reset')]
        def late_device(*args):
            if calls:
                raise calls.pop(0)
            return original(*args)
        with patch.object(self.device.hw, 'write', side_effect=late_device) as write:
            await self.recover()
        self.assertEqual(write.call_count, 3)
        self.assertIsNotNone(self.manager.task)
        self.assertEqual(self.manager.settings.path.read_bytes(), saved)
        self.assertEqual(self.manager.editor_zone, 'zone3')
        self.assertFalse(self.manager.error)

    async def test_persistent_device_failure_is_bounded(self):
        await self.manager.apply(config())
        with patch.object(self.device.hw,'write',side_effect=OSError(errno.ENODEV,'gone')) as write:
            await self.recover(attempts=3)
        self.assertEqual(write.call_count, 3)
        self.assertIsNone(self.manager.lock.file)
        self.assertIsNone(self.manager.recovery_task)

    async def test_conflict_stops_without_writing_or_retrying(self):
        await self.manager.apply(config())
        self.others[:] = ['OpenRGB']
        with patch.object(self.device.hw,'write') as write:
            await self.recover()
        write.assert_not_called()
        self.assertIn('OpenRGB',self.manager.error)

    async def test_invalid_identity_or_kernel_trigger_is_not_retried(self):
        for error in (rgb.RGBError('identity changed'), rgb.RGBError('kernel trigger'), BlockingIOError(errno.EAGAIN,'lock')):
            await self.manager.apply(config())
            with patch.object(self.device.hw,'write',side_effect=error) as write:
                await self.recover()
            self.assertEqual(write.call_count,1)

    async def test_manual_edit_cancels_pending_recovery_and_wins(self):
        await self.manager.apply(config())
        pending = await self.manager.request_resume()
        changed = config(brightness=17, effect='wave')
        await self.manager.apply(changed)
        self.assertTrue(pending.cancelled())
        self.assertEqual(self.manager.target,rgb.validate(changed))
        self.assertIsNone(self.manager.recovery_task)

    async def test_release_cancels_pending_restore_and_future_wake_does_not_reacquire(self):
        await self.manager.apply(config())
        task = await self.manager.request_resume()
        await self.manager.release()
        self.assertTrue(task.cancelled())
        with patch.object(self.device.hw,'write') as write:
            await self.manager.resume()
        write.assert_not_called()

    async def test_disabled_recovery_and_empty_settings_never_write(self):
        with patch.object(self.device.hw,'write') as write:
            await self.manager.resume()
        write.assert_not_called()
        await self.manager.apply(config(resume=False))
        with patch.object(self.device.hw,'write') as write:
            await self.manager.resume()
        write.assert_not_called()

    async def test_second_sleep_cancels_first_recovery_and_keeps_target(self):
        await self.manager.apply(config())
        expected = copy.deepcopy(self.manager.target)
        first = await self.manager.request_resume()
        await self.manager.power_event(True)
        self.assertTrue(first.cancelled())
        self.assertEqual(self.manager.target,expected)
        await self.manager.resume()
        self.assertEqual(self.manager.target,expected)

    async def test_status_never_starts_monitor_or_recovery(self):
        with patch.object(self.device.hw,'write') as write:
            state = await self.manager.state()
        write.assert_not_called()
        self.assertFalse(state['recovery']['pending'])
        self.assertIsNone(self.manager.power_monitor)


class BrightnessCacheTests(unittest.TestCase):
    def test_closing_after_suspend_forces_brightness_before_same_color(self):
        transport = rgb_hid.RGBTransport()
        transport.fd, transport.identity, transport.level = 41, ('old',), 3
        with patch.object(os, 'close'):
            transport.close()
        self.assertIsNone(transport.level)
        # TransportTests exercise the reopened fd and brightness-before-color.
