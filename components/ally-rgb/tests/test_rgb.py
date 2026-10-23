import asyncio
import copy
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from py_modules import rgb


def config(**changes):
    legacy = copy.deepcopy(rgb.LEGACY_DEFAULT)
    legacy.update(changes)
    return rgb.validate(legacy)


class DeviceFixture:
    def __init__(self, root):
        self.path = root / 'led'
        self.path.mkdir()
        self.product = root / 'product'
        self.product.write_text('ROG Ally RC71L_RC71L')
        for name, value in dict(multi_index='rgb rgb rgb rgb', multi_intensity='0 0 0 0',
                                brightness='128', max_brightness='255', trigger='[none] disk-activity',
                                sleep_animation='0', sleep_animation_index='0 1').items():
            (self.path / name).write_text(value)
        self.hw = rgb.Hardware(self.path, self.product)


class HardwareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.device = DeviceFixture(Path(self.tmp.name))
        self.hw = self.device.hw

    def test_read_is_pure_and_four_zones_not_three_channels(self):
        with patch.object(Path, 'write_text', side_effect=AssertionError('no startup writes')):
            state = self.hw.state()
        self.assertEqual(state['colors'], [0]*4)
        self.assertEqual(state['brightness'], 128)
        self.assertFalse(state['sleep'])

    def test_packed_colors_roundtrip(self):
        cfg = config(colors=['#ff0000', '#00ff00', '#0000ff', '#010203'], brightness=100)
        colors, brightness = rgb.frame(rgb.validate(cfg), 0)
        self.assertEqual(colors, [16711680, 65280, 255, 66051])
        state = self.hw.write(colors, brightness)
        self.assertEqual(state['colors'], colors)
        self.assertEqual((self.device.path/'multi_intensity').read_text(), '16711680 65280 255 66051')
        self.assertEqual(state['brightness'], 255)

    def test_invalid_input_and_other_models_never_write(self):
        for colors, brightness in [([1,2,3], 100), ([0]*4, True), ([0]*4, 256), ([0,0,0,-1], 100)]:
            with patch.object(Path, 'write_text') as write:
                with self.assertRaises(rgb.RGBError): self.hw.write(colors, brightness)
                write.assert_not_called()
        self.device.product.write_text('ROG Ally X RC72LA_RC72LA')
        with patch.object(Path, 'write_text') as write:
            with self.assertRaisesRegex(rgb.RGBError, 'RC71L'): self.hw.write([0]*4, 0)
            write.assert_not_called()

    def test_trigger_conflict_does_not_overwrite(self):
        (self.device.path/'trigger').write_text('none [disk-activity]')
        with patch.object(Path, 'write_text') as write:
            with self.assertRaisesRegex(rgb.RGBError, 'disparador'): self.hw.write([1]*4, 50)
            write.assert_not_called()

    def test_partial_write_rolls_back_both_attributes(self):
        before = self.hw.state()
        original = Path.write_text
        failed = False
        def failing(path, text, *args, **kwargs):
            nonlocal failed
            if path == self.device.path/'brightness' and not failed:
                failed = True
                raise OSError('simulated brightness write failure')
            return original(path, text, *args, **kwargs)
        with patch.object(Path, 'write_text', failing):
            with self.assertRaises(OSError): self.hw.write([100]*4, 75)
        self.assertEqual(self.hw.state(), before)

    def test_mismatched_readback_rolls_back(self):
        original = Path.write_text
        changed = False
        def clamped(path, text, *args, **kwargs):
            nonlocal changed
            if path == self.device.path/'brightness' and not changed:
                changed = True
                return original(path, '10')
            return original(path, text, *args, **kwargs)
        with patch.object(Path, 'write_text', clamped):
            with self.assertRaisesRegex(rgb.RGBError, 'confirmó'): self.hw.write([1]*4, 50)
        self.assertEqual(self.hw.state()['brightness'], 128)
        self.assertEqual(self.hw.state()['colors'], [0]*4)

    def test_sleep_option_is_independent_of_colors_and_brightness(self):
        before = self.hw.state()
        self.hw.set_sleep(True)
        after = self.hw.state()
        self.assertTrue(after['sleep'])
        self.assertEqual(after['colors'], before['colors'])
        self.assertEqual(after['brightness'], before['brightness'])
        with self.assertRaises(rgb.RGBError): self.hw.set_sleep(1)

    def test_lock_contention_and_symlinks(self):
        a = rgb.RGBLock(Path(self.tmp.name)/'lock', os.geteuid())
        b = rgb.RGBLock(a.path, os.geteuid())
        a.acquire()
        try:
            with self.assertRaises(BlockingIOError): b.acquire()
        finally: a.release()
        b.acquire(); b.release()
        link = Path(self.tmp.name)/'link'
        link.symlink_to(a.path)
        with self.assertRaises(OSError): rgb.RGBLock(link, os.geteuid()).acquire()


class EffectTests(unittest.TestCase):
    def test_four_distinct_effects_are_composed_and_selection_never_changes_rendering(self):
        cfg = config()
        for zone, effect, speed in zip(cfg['zones'], ('breath','gradient','wave','solid'), (23,51,89,50)):
            zone.update(effect=effect,speed=speed)
        first = rgb.frame(cfg, .2, 60)[0]
        second = rgb.frame(cfg, .7, 60)[0]
        self.assertTrue(all(first[i] != second[i] for i in (0,1,2)))
        self.assertEqual(first[3], second[3])
        for editor in rgb.ZONES:
            self.assertEqual(rgb.frame(dict(cfg,zone=editor), .2, 60)[0], first)

    def test_invalid_independent_zone_configs_are_rejected(self):
        for zones in ([], [dict(rgb.ZONE_DEFAULT)]*3, ['bad']*4):
            with self.assertRaises(rgb.RGBError): rgb.validate(dict(config(),zones=zones))
        for field, value in [('speed',True),('speed',9),('effect','unknown'),('color','red'),('transition_colors',[]),('extra',1)]:
            cfg = config();cfg['zones'][2][field]=value
            with self.assertRaises(rgb.RGBError): rgb.validate(cfg)

    def test_transition_has_independent_endpoints_not_zone_colors(self):
        cfg = rgb.validate(config(effect='gradient', colors=['#000000']*4,
                                  transition_colors=['#ff0000', '#0000ff']))
        rate = .15 + cfg['zones'][0]['speed']/100*1.85
        self.assertEqual(rgb.frame(cfg, 0)[0], [0xff0000]*4)
        self.assertEqual(rgb.frame(cfg, .5/rate)[0], [0x0000ff]*4)
        middle = rgb.frame(cfg, .25/rate)[0][0]
        self.assertTrue(127 <= (middle >> 16) <= 128)
        self.assertTrue(127 <= (middle & 255) <= 128)

    def test_every_effect_respects_every_selected_zone_mask(self):
        for zone, selected in rgb.ZONES.items():
            for effect in rgb.EFFECTS:
                cfg = rgb.validate(config(zone=zone, effect=effect,
                                         colors=['#112233', '#445566', '#778899', '#aabbcc']))
                for moment in (0, .4, 1.2):
                    colors, _ = rgb.frame(cfg, moment, 65)
                    for i in range(4):
                        if i not in selected:
                            self.assertEqual(colors[i], int(cfg['zones'][i]['color'][1:], 16), (zone, effect, i))

    def test_legacy_migration_and_invalid_new_fields(self):
        legacy = {k:v for k,v in copy.deepcopy(rgb.LEGACY_DEFAULT).items() if k not in ('zone','transition_colors')}
        migrated = rgb.validate(legacy)
        self.assertEqual(migrated['zone'], 'all')
        self.assertNotEqual(*migrated['zones'][0]['transition_colors'])
        for change in (dict(zone=1), dict(zone='zone5'), dict(zone=[]),
                       dict(transition_colors=['#ff0000']), dict(transition_colors=['#ff0000','bad'])):
            with self.assertRaises(rgb.RGBError): rgb.validate(config(**change))

    def test_invalid_configs_rejected_without_clamping_or_unknown_effects(self):
        for change in [dict(speed=True), dict(brightness=-1), dict(brightness=101), dict(speed=9),
                       dict(enabled=1),dict(effect='firmware'),dict(colors=['#ff0000']*3),
                       dict(colors=['oops']*4),dict(resume='yes'),dict(path='/etc/passwd')]:
            with self.subTest(change=change), self.assertRaises(rgb.RGBError): rgb.validate(config(**change))

    def test_every_effect_stays_inside_color_and_brightness_limits(self):
        for effect in rgb.EFFECTS:
            cfg = rgb.validate(config(effect=effect,brightness=100,speed=100))
            for t in range(100):
                colors, brightness = rgb.frame(cfg,t/17,42)
                self.assertEqual(len(colors),4)
                self.assertTrue(all(0<=c<=0xffffff for c in colors))
                self.assertTrue(0<=brightness<=255)

    def test_disabled_means_dark_even_for_breathing(self):
        for effect in rgb.EFFECTS:
            self.assertEqual(rgb.frame(config(effect=effect, enabled=False), 10, 50)[1], 0)
        self.assertEqual(rgb.frame(config(effect='battery', enabled=False), 10, None)[1], 0)

    def test_battery_colors_and_unknown_level(self):
        cfg = config(effect='battery')
        self.assertEqual(rgb.frame(cfg, 0, 100)[0], [0x00ff00]*4)
        self.assertEqual(rgb.frame(cfg, 0, 50)[0], [0xffff00]*4)
        self.assertEqual(rgb.frame(cfg, 0, 0)[0], [0xff0000]*4)
        with self.assertRaises(rgb.RGBError): rgb.frame(cfg,0,None)


class BatteryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def supply(self, name, capacity='50', scope=None, present=None, kind='Battery'):
        path = self.root / name
        path.mkdir(exist_ok=True)
        for key, value in dict(type=kind, capacity=capacity, scope=scope, present=present).items():
            field = path / key
            if value is None:
                if field.exists(): field.unlink()
            else: field.write_text(str(value))
        return path

    def test_controller_discovered_first_does_not_replace_internal_without_scope(self):
        self.supply('ps-controller-battery-test', '99', scope='Device')
        self.supply('BAT0', '41')
        self.assertEqual(rgb.battery_level(self.root), 41)

    def test_internal_without_controller_including_zero_percent(self):
        self.supply('BAT0', '0')
        self.assertEqual(rgb.battery_level(self.root), 0)

    def test_only_peripherals_never_report_system_battery(self):
        self.supply('ps-controller-battery-test', '99', scope='Device')
        self.supply('hid-mouse-battery', '67')
        self.assertIsNone(rgb.battery_level(self.root))

    def test_invalid_or_missing_internal_capacity_never_falls_back_to_controller(self):
        self.supply('ps-controller-battery-test', '99', scope='Device')
        for value in ('bad', '101', '-1', None):
            self.supply('BAT0', value)
            self.assertIsNone(rgb.battery_level(self.root), value)

    def test_unreadable_internal_returns_unknown_not_controller_percentage(self):
        self.supply('ps-controller-battery-test', '99', scope='Device')
        internal = self.supply('BAT0', '41')
        original = rgb.read
        def blocked(path):
            if path == internal / 'capacity': raise PermissionError('unreadable fixture')
            return original(path)
        with patch.object(rgb, 'read', side_effect=blocked):
            self.assertIsNone(rgb.battery_level(self.root))

    def test_absent_internal_is_ignored(self):
        self.supply('BAT0', '41', present='0')
        self.supply('ps-controller-battery-test', '99', scope='Device')
        self.assertIsNone(rgb.battery_level(self.root))

    def test_explicit_device_scope_is_rejected_even_with_system_style_name(self):
        self.supply('BAT0', '99', scope='Device')
        self.assertIsNone(rgb.battery_level(self.root))

    def test_system_scope_and_primary_internal_are_preferred(self):
        self.supply('BAT1', '23', scope='System')
        self.supply('BAT0', '41', scope='System', present='1')
        self.assertEqual(rgb.battery_level(self.root), 41)

    def test_unknown_scope_nonbattery_and_missing_directory_are_not_guessed(self):
        self.supply('BAT0', '41', scope='Unknown')
        self.assertIsNone(rgb.battery_level(self.root))
        self.supply('BAT0', '41', scope='System', kind='Mains')
        self.assertIsNone(rgb.battery_level(self.root))
        self.assertIsNone(rgb.battery_level(self.root / 'missing'))

    def test_reading_battery_is_read_only(self):
        self.supply('BAT0', '41', present='1')
        with patch.object(Path, 'write_text', side_effect=AssertionError('battery read must not write')):
            self.assertEqual(rgb.battery_level(self.root), 41)


class SettingsTests(unittest.TestCase):
    def test_last_config_is_atomic_and_retains_disabled_preference(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'settings.json'
            store = rgb.Settings(path)
            self.assertFalse(path.exists())
            store.save(config(brightness=10, resume=False, zone='zone3'))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(rgb.Settings(path).config, rgb.validate(config(brightness=10, resume=False, zone='zone3')))

    def test_failed_atomic_save_preserves_file_and_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'settings.json'
            store = rgb.Settings(path); store.save(config())
            before = path.read_bytes()
            with patch.object(rgb.os, 'replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError): store.save(config(brightness=70))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(store.config['brightness'], 50)

    def test_corrupt_config_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'settings.json'; path.write_text('{broken')
            store = rgb.Settings(path)
            self.assertIsNone(store.config)
            self.assertTrue(store.warning)
            self.assertEqual(path.read_text(), '{broken')

    def test_symlink_settings_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); target = root/'foreign'; target.write_text('untouched')
            link = root/'settings.json'; link.symlink_to(target)
            with self.assertRaises(rgb.RGBError): rgb.Settings(link).save(config())
            self.assertEqual(target.read_text(), 'untouched')


class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.device=DeviceFixture(root)
        self.others=[]
        self.manager=rgb.Manager(root/'settings',self.device.hw,
            rgb.RGBLock(root/'lock',os.geteuid()),lambda:self.others,lambda:75)

    async def asyncTearDown(self):
        await self.manager.release()
        self.tmp.cleanup()

    def new_manager(self):
        root = Path(self.tmp.name)
        return rgb.Manager(root/'settings', self.device.hw,
                           rgb.RGBLock(root/'lock', os.geteuid()), lambda:self.others, lambda:75)

    async def test_editing_another_zone_preserves_animation_phase_and_single_worker(self):
        clock = [100.]
        self.manager.clock = lambda:clock[0]
        cfg = config()
        cfg['zones'][0].update(effect='breath',color='#0000ff',speed=40)
        await self.manager.apply(cfg)
        worker = self.manager.task
        first_start = self.manager.started[0]
        clock[0] = 100.4
        cfg = copy.deepcopy(self.manager.target)
        cfg['zone'] = 'zone2'
        cfg['zones'][1].update(effect='gradient',transition_colors=['#ff0000','#00ff00'],speed=75)
        state = await self.manager.apply(cfg)
        self.assertEqual(self.manager.started[0],first_start)
        self.assertEqual(self.manager.started[1],100.4)
        self.assertIs(self.manager.task,worker)
        expected = rgb.frame(cfg,[.4,0,.4,.4],75)[0]
        self.assertEqual(state['actual']['colors'],expected)
        self.assertNotEqual(expected[0],rgb.frame(cfg,0,75)[0][0])
        old_starts = list(self.manager.started)
        clock[0] = 100.7
        await self.manager.select_zone('zone3')
        cfg = copy.deepcopy(self.manager.target);cfg['zones'][2]['color']='#ff5500'
        await self.manager.apply(cfg)
        self.assertEqual(self.manager.started[:2],old_starts[:2])
        self.assertIs(self.manager.task,worker)

    async def test_multi_effect_settings_survive_restart_and_suspend(self):
        cfg = config()
        for i, effect in enumerate(('breath','gradient','rainbow','wave')):
            cfg['zones'][i].update(effect=effect,speed=20+i*20)
        cfg['zones'][1]['transition_colors']=['#ff0000','#00ff00']
        await self.manager.apply(cfg)
        await self.manager.pause();await self.manager.resume()
        self.assertEqual(self.manager.target,cfg)
        await self.manager.release()
        other = self.new_manager()
        try:
            await other.restore_startup()
            self.assertEqual(other.target,cfg)
            self.assertTrue((await other.state())['active'])
        finally: await other.release()

    async def test_selecting_zone_on_empty_startup_never_arms_default_restore(self):
        with patch.object(self.manager.hw,'write',side_effect=AssertionError('selection cannot apply defaults')):
            state = await self.manager.select_zone('zone4')
            await self.manager.restore_startup()
        self.assertEqual(state['editor_zone'],'zone4')
        self.assertIsNone(state['config'])
        self.assertFalse(self.manager.settings.path.exists())
        self.assertFalse(self.manager.lock.path.exists())

    async def test_same_lighting_metadata_updates_do_not_write_or_reset_phase(self):
        await self.manager.apply(config(effect='wave'))
        starts=list(self.manager.started);worker=self.manager.task
        updated=copy.deepcopy(self.manager.target);updated.update(zone='zone2',resume=False)
        with patch.object(self.manager.hw,'write',side_effect=AssertionError('metadata only')):
            state=await self.manager.apply(updated)
        self.assertEqual(self.manager.started,starts)
        self.assertIs(self.manager.task,worker)
        self.assertFalse(state['config']['resume'])

    async def test_saved_config_restores_after_full_manager_restart(self):
        cfg = config(effect='gradient', zone='pair34', brightness=27,
                     transition_colors=['#010203', '#aabbcc'])
        await self.manager.apply(cfg)
        await self.manager.release()
        (self.device.path/'multi_intensity').write_text('0 0 0 0')
        (self.device.path/'brightness').write_text('0')
        other = self.new_manager()
        try:
            with patch.object(other.hw, 'write', wraps=other.hw.write) as write:
                await other.restore_startup()
                self.assertEqual(write.call_count, 1)
            self.assertEqual(other.target, rgb.validate(cfg))
            self.assertEqual(other.hw.state()['brightness'], 69)
            self.assertTrue((await other.state())['active'])
        finally: await other.release()

    async def test_disabled_startup_retains_ui_settings_but_never_writes(self):
        await self.manager.apply(config(resume=True))
        await self.manager.apply(config(resume=False, brightness=17, zone='zone2'))
        await self.manager.release()
        other = self.new_manager()
        try:
            with patch.object(other.hw, 'write', side_effect=AssertionError('restore disabled')):
                await other.restore_startup()
                state = await other.state()
            self.assertFalse(state['active'])
            self.assertEqual(state['config']['zone'], 'zone2')
            self.assertFalse(state['config']['resume'])
        finally: await other.release()

    async def test_corrupt_saved_config_never_applies_at_startup(self):
        self.manager.settings.path.parent.mkdir(parents=True)
        self.manager.settings.path.write_text('{corrupt')
        other = self.new_manager()
        with patch.object(other.hw, 'write', side_effect=AssertionError('corrupt restore')):
            await other.restore_startup()
        self.assertTrue((await other.state())['warning'])
        self.assertIsNone(other.target)
        self.assertEqual(other.settings.path.read_text(), '{corrupt')

    async def test_startup_conflict_does_not_acquire_control_or_retry(self):
        self.manager.settings.save(config())
        self.others = ['HHD']
        other = self.new_manager()
        with patch.object(other.hw, 'write', side_effect=AssertionError('conflict')):
            await other.restore_startup()
        self.assertIn('otro gestor', other.error)
        self.assertIsNone(other.task)
        self.assertIsNone(other.lock.file)

    async def test_late_device_restores_and_get_state_remains_read_only(self):
        self.manager.settings.save(config(brightness=20))
        other = self.new_manager()
        state = self.device.hw.state()
        with patch.object(other.hw, 'state', side_effect=[FileNotFoundError(), state]), \
             patch.object(other, 'apply', new_callable=unittest.mock.AsyncMock) as apply:
            await other.restore_startup(attempts=2, interval=0)
            apply.assert_awaited_once_with(other.settings.config, automatic=True)
        with patch.object(other.hw, 'write', side_effect=AssertionError('status writes')):
            await other.state()

    async def test_edit_cancels_delayed_startup_so_old_config_cannot_win(self):
        self.manager.settings.save(config(brightness=5))
        original = self.device.hw.state
        with patch.object(self.device.hw, 'state', side_effect=FileNotFoundError()):
            self.manager.startup_task = asyncio.create_task(self.manager.restore_startup(interval=1))
            await asyncio.sleep(.01)
        await self.manager.apply(config(brightness=80))
        self.assertIsNone(self.manager.startup_task)
        self.assertEqual(self.manager.target['brightness'], 80)
        self.assertEqual(original()['brightness'], 204)

    async def test_saving_failure_warns_without_stopping_live_effect(self):
        with patch.object(self.manager.settings, 'save', side_effect=OSError('disk full')):
            state = await self.manager.apply(config(effect='wave'))
        self.assertTrue(state['active'])
        self.assertIn('no se pudo guardar', state['warning'].lower())
        self.assertFalse(state['error'])

    async def test_editor_change_never_writes_or_restarts_any_zone(self):
        await self.manager.apply(config(effect='wave'))
        worker = self.manager.task
        started = list(self.manager.started)
        with patch.object(self.manager.hw, 'write', side_effect=AssertionError('editor-only')):
            state = await self.manager.select_zone('zone2')
        self.assertEqual(state['config']['zone'], 'zone2')
        self.assertIs(self.manager.task, worker)
        self.assertEqual(self.manager.started, started)
        self.assertEqual([z['effect'] for z in state['config']['zones']], ['wave']*4)

    async def test_suspend_resume_retains_mask_and_transition_colors_without_saving_again(self):
        await self.manager.apply(config(effect='gradient', zone='zone4', transition_colors=['#ff0000','#0000ff']))
        await self.manager.pause()
        with patch.object(self.manager.settings, 'save', side_effect=AssertionError('unnecessary save')):
            state = await self.manager.resume()
        self.assertTrue(state['active'])
        self.assertEqual(state['config']['zone'], 'zone4')
        self.assertEqual(state['config']['zones'][3]['transition_colors'], ['#ff0000','#0000ff'])

    async def test_empty_startup_and_status_never_write(self):
        with patch.object(self.device.hw,'write',side_effect=AssertionError('status must not write')):
            state=await self.manager.state()
            self.assertTrue(state['supported'])
            self.assertFalse(state['active'])
            self.assertIsNone(self.manager.task)
            self.assertFalse((Path(self.tmp.name)/'lock').exists())
            await self.manager.resume()
            await self.manager.restore_startup()

    async def test_conflicting_manager_blocks_before_write_or_lock(self):
        self.others=['HueSync']
        with patch.object(self.device.hw,'write') as write:
            state=await self.manager.apply(config())
            self.assertIn('HueSync',state['error'])
            self.assertFalse(state['active']);write.assert_not_called()
        self.assertFalse(self.manager.lock.path.exists())

    async def test_concurrent_changes_end_at_last_config_and_one_worker(self):
        configs=[config(brightness=i,effect='wave') for i in (10,20,30,40)]
        await asyncio.gather(*(self.manager.apply(c) for c in configs))
        self.assertEqual(self.manager.target['brightness'],40)
        self.assertIsNotNone(self.manager.task)
        self.assertFalse(self.manager.task.done())
        self.assertEqual(self.device.hw.state()['brightness'],102)

    async def test_release_stops_effect_without_restoration(self):
        await self.manager.apply(config(effect='wave'))
        before=self.device.hw.state()
        with patch.object(self.device.hw,'write',side_effect=AssertionError('release cannot restore')):
            state=await self.manager.release()
        self.assertFalse(state['active'])
        self.assertEqual(self.device.hw.state(),before)
        self.assertIsNone(self.manager.task)

    async def test_new_writer_yields_without_restoring_over_it(self):
        await self.manager.apply(config(effect='wave'))
        self.others=['HHD']
        with patch.object(self.device.hw,'write',side_effect=AssertionError('no competing writes')):
            await asyncio.sleep(.12)
        self.assertIn('HHD',self.manager.error)
        self.assertIsNone(self.manager.target)
        self.assertIsNone(self.manager.lock.file)

    async def test_device_disappears_stops_animation_and_releases_lock(self):
        await self.manager.apply(config(effect='wave'))
        (self.device.path/'multi_index').unlink()
        await asyncio.sleep(.12)
        self.assertIsNone(self.manager.lock.file)
        self.assertIsNone(self.manager.target)
        self.assertTrue(self.manager.error)

    async def test_pause_resume_only_reapplies_authorized_current_profile(self):
        await self.manager.apply(config(brightness=25))
        await self.manager.pause()
        self.assertTrue(self.manager.paused)
        self.assertIsNone(self.manager.lock.file)
        (self.device.path/'brightness').write_text('0')
        result=await self.manager.resume()
        self.assertTrue(result['active'])
        self.assertEqual(self.device.hw.state()['brightness'],64)

    async def test_resume_disabled_does_not_write(self):
        await self.manager.apply(config(resume=False))
        await self.manager.pause()
        with patch.object(self.device.hw,'write',side_effect=AssertionError('resume off')):
            state=await self.manager.resume()
        self.assertFalse(state['active'])
        self.assertFalse(state['config']['resume'])

    async def test_all_writes_are_restricted_to_rgb_attributes(self):
        paths=[]; original=Path.write_text
        def traced(path,text,*args,**kwargs):
            paths.append(path)
            return original(path,text,*args,**kwargs)
        with patch.object(Path,'write_text',traced):
            await self.manager.apply(config())
            await self.manager.set_sleep(True)
            await self.manager.release()
        self.assertTrue(paths)
        self.assertTrue(all(p.parent==self.device.path and p.name in ('multi_intensity','brightness','sleep_animation') for p in paths))

    async def test_foreign_color_change_is_not_reimposed(self):
        await self.manager.apply(config())
        (self.device.path/'multi_intensity').write_text('12 34 56 78')
        await asyncio.sleep(1.08)
        self.assertIsNone(self.manager.target)
        self.assertIn('cedido',self.manager.error)
        self.assertEqual(self.device.hw.state()['colors'],[12,34,56,78])


class RuntimeTests(unittest.TestCase):
    def test_entrypoint_imports_from_outside_plugin_directory_like_decky(self):
        path = str(Path('main.py').resolve())
        script = '''
import importlib.util,sys,types
sys.modules['decky']=types.SimpleNamespace()
spec=importlib.util.spec_from_file_location('rgb_entry',sys.argv[1])
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.Plugin
'''
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,'-I','-c',script,path],cwd=directory,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_import_succeeds_with_serial_termios_and_hid_forbidden(self):
        script='''
import builtins,sys,types
original=builtins.__import__
def restricted(name,*a,**kw):
    if name.split('.')[0] in ('termios','serial','hid','lib_hid'):
        raise ModuleNotFoundError(name)
    return original(name,*a,**kw)
builtins.__import__=restricted
sys.modules['decky']=types.SimpleNamespace()
import main
print('ALLY RGB imported without termios/serial/HID')
'''
        result=subprocess.run([sys.executable,'-c',script],text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
