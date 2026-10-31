import asyncio
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import types
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import video_selector as v
from video_startup import preferred_outputs
from video_runtime import VideoRuntime


def edid(name):
    data = bytearray(128)
    data[:8] = b'\x00\xff\xff\xff\xff\xff\xff\x00'
    data[54:59] = b'\x00\x00\x00\xfc\x00'
    data[59:72] = name.encode().ljust(13, b' ')
    data[127] = (-sum(data)) % 256
    return bytes(data)


def node(key, label, enabled=False, internal=False, force='unspecified', ident=1):
    return {'key': key, 'identity': v.identity(edid(label)), 'id': ident, 'model': label,
            'enabled': enabled, 'internal': internal, 'force': force, 'connected': True}


class FakeAccess:
    def __init__(self):
        self.data = {'0:DP-10': node('0:DP-10', 'AOC', ident=10),
            '0:DP-12': node('0:DP-12', 'Acer', True, ident=12),
            '0:eDP-1': node('0:eDP-1', 'internal', internal=True, ident=1)}
        self.owned, self.writes = {}, []
        self.guard = Mock()
        self.current = 'DP-12'
        self.confirm, self.fail_context, self.fail_write, self.external = True, False, None, False

    def nodes(self): return copy.deepcopy(self.data)
    def context(self):
        if self.fail_context: raise RuntimeError('no native readback')
        return self.current
    def active(self): return self.current
    def progress(self, owned): pass
    remember = v.Access.remember
    def set_force(self, n, value, session=True):
        self.guard.check(session=session)
        if self.fail_write == n['key']: raise OSError('write rejected')
        self.writes.append((n['key'], value))
        self.data[n['key']]['force'] = value
        if value == 'off': self.data[n['key']]['enabled'] = False
    def nudge(self):
        self.guard.check()
        if self.confirm:
            selected = next(n for n in self.data.values() if n['force'] != 'off' and not n['internal'])
            selected['enabled'] = True
            self.current = v.parts(selected['key'])[1]
    def desktop_notify(self, cards): self.writes.append(('notify', tuple(cards)))


class IdentityTests(unittest.TestCase):
    def test_edid_requires_header_size_and_checksum(self):
        self.assertIsNotNone(v.identity(edid('AOC')))
        for data in (b'', b'bad'*128, edid('AOC')[:-1], edid('AOC')[:-1]+b'\x00'):
            self.assertIsNone(v.identity(data))

    def test_identity_not_connector_number(self):
        a = node('0:DP-9', 'AOC'); b = node('0:DP-10', 'AOC')
        self.assertEqual(a['identity'], b['identity'])
        self.assertEqual(v.resolve({b['key']: b}, a['identity']), b)

    def test_duplicate_identity_never_chosen_arbitrarily(self):
        a = node('0:DP-9', 'AOC'); b = node('0:DP-10', 'AOC')
        self.assertIsNone(v.resolve({a['key']: a, b['key']: b}, a['identity']))

    def test_connector_path_rejects_traversal_and_other_interfaces(self):
        for key in ('0:../../x', '0:Writeback-1', '-1:DP-2', 'x:DP-2', '0:DP-1/x'):
            with self.assertRaises(ValueError): v.parts(key)

    def test_metadata_scan_never_writes_and_retains_owned_off_display(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); base = root/'drm'; debug = root/'debug'; p=base/'card0-DP-9'; p.mkdir(parents=True)
            q=debug/'0/DP-9'; q.mkdir(parents=True)
            for name, text in [('connector_id','23'),('status','connected'),('enabled','enabled')]: (p/name).write_text(text)
            (p/'edid').write_bytes(edid('AOC')); (q/'force').write_text('unspecified')
            first=v.scan(base,debug)
            (p/'status').write_text('disconnected'); (p/'edid').write_bytes(b''); (q/'force').write_text('off')
            before={x:x.read_bytes() for x in root.rglob('*') if x.is_file()}
            second=v.scan(base,debug,first)
            self.assertEqual(second['0:DP-9']['identity'],first['0:DP-9']['identity'])
            self.assertTrue(second['0:DP-9']['connected'])
            self.assertTrue(all(x.read_bytes()==data for x,data in before.items()))
            (p/'connector_id').write_text('24')
            self.assertIsNone(v.scan(base,debug,first)['0:DP-9']['identity'])

    def test_startup_without_preference_never_waits(self):
        self.assertEqual(preferred_outputs({}, read=Mock(side_effect=AssertionError)), '*,eDP-1')

    def test_startup_resolves_renumbered_monitor(self):
        n=node('0:DP-14','AOC')
        self.assertEqual(preferred_outputs({'config':{'defaultDisplayIdentity':n['identity']}},read=lambda:{n['key']:n}), 'DP-14,*,eDP-1')

    def test_startup_missing_monitor_has_bounded_wait(self):
        tick=[0.0]
        def sleep(n): tick[0]+=n
        result=preferred_outputs({'config':{'defaultDisplayIdentity':'missing'}},read=lambda:{},clock=lambda:tick[0],sleep=sleep)
        self.assertEqual(result,'*,eDP-1');self.assertLess(tick[0],1.1)


class TransactionTests(unittest.TestCase):
    def test_switch_confirms_native_output_and_never_disables_internal(self):
        a=FakeAccess(); result=v.switch(a,a.data['0:DP-10'])
        self.assertTrue(result['ok']); self.assertEqual(result['active'],'DP-10')
        self.assertEqual(a.writes,[('0:DP-12','off')])
        self.assertEqual(a.owned['0:DP-12']['before'],'unspecified')

    def test_no_native_readback_means_no_write(self):
        a=FakeAccess();a.fail_context=True
        self.assertFalse(v.switch(a,a.data['0:DP-10'])['ok']);self.assertEqual(a.writes,[])

    def test_absent_or_changed_target_never_disables_current(self):
        for change in ('identity','id','connected'):
            a=FakeAccess();target=copy.deepcopy(a.data['0:DP-10']);a.data['0:DP-10'][change]=None
            self.assertFalse(v.switch(a,target)['ok']);self.assertEqual(a.writes,[])

    def test_unconfirmed_switch_rolls_back_without_claiming_success(self):
        a=FakeAccess();a.confirm=False;result=v.switch(a,a.data['0:DP-10'],timeout=0)
        self.assertFalse(result['ok']);self.assertEqual(a.data['0:DP-12']['force'],'unspecified');self.assertEqual(a.owned,{})

    def test_write_failure_does_not_return_success(self):
        a=FakeAccess();a.fail_write='0:DP-12'
        self.assertFalse(v.switch(a,a.data['0:DP-10'])['ok'])

    def test_suspension_cancels_without_cleanup_writes_over_boundary(self):
        a=FakeAccess(); count=[0]
        def guard(*args,**kwargs):
            count[0]+=1
            if count[0]>=3: raise v.Boundary('sleep')
        a.guard.check.side_effect=guard
        result=v.switch(a,a.data['0:DP-10']);self.assertFalse(result['ok'])
        self.assertEqual(a.writes,[('0:DP-12','off')]);self.assertIn('0:DP-12',result['owned'])

    def test_already_active_still_excludes_competing_external(self):
        a=FakeAccess();a.current='DP-10';a.data['0:DP-10']['enabled']=True
        self.assertTrue(v.switch(a,a.data['0:DP-10'])['ok']);self.assertIn(('0:DP-12','off'),a.writes)

    def test_no_change_when_only_target_is_available(self):
        a=FakeAccess();a.current='DP-10';a.data['0:DP-10']['enabled']=True;a.data['0:DP-12']['connected']=False
        self.assertTrue(v.switch(a,a.data['0:DP-10'])['unchanged']);self.assertEqual(a.writes,[])

    def test_release_restores_only_owned_flags_and_notifies_desktop(self):
        a=FakeAccess();v.switch(a,a.data['0:DP-10']);a.writes=[]
        result=v.release(a);self.assertTrue(result['ok'])
        self.assertEqual(a.writes,[('0:DP-12','unspecified'),('notify',(0,))]);self.assertEqual(a.owned,{})

    def test_release_does_not_overwrite_another_owner(self):
        a=FakeAccess();v.switch(a,a.data['0:DP-10']);a.data['0:DP-12']['force']='on';a.writes=[]
        self.assertTrue(v.release(a)['ok']);self.assertEqual(a.writes,[])

    def test_release_never_restores_removed_or_reused_connector(self):
        for removed in (True,False):
            a=FakeAccess();v.switch(a,a.data['0:DP-10']);a.writes=[]
            if removed:del a.data['0:DP-12']
            else:a.data['0:DP-12']['id']=99
            self.assertTrue(v.release(a)['ok']);self.assertEqual(a.writes,[])

    def test_multi_gpu_rejected_and_no_competitor_disabled(self):
        a=FakeAccess();a.data['1:DP-1']=node('1:DP-1','other',True,ident=99)
        result=v.switch(a,a.data['0:DP-10']);self.assertFalse(result['ok'])
        self.assertNotIn(('1:DP-1','off'),a.writes)


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def runtime(self):
        n=node('0:DP-10','AOC')
        r=VideoRuntime(lambda:{'defaultDisplayIdentity':n['identity'],'targetUid':1000},Mock())
        r.context={'pid':42,'start':'100'};r.nodes={n['key']:n}
        r.run=AsyncMock(return_value={'ok':True,'active':'DP-10','owned':{}})
        return r,n

    async def test_manual_choice_holds_off_automatic_selection(self):
        r,n=self.runtime()
        with patch.object(r,'observe',return_value=r.context):
            self.assertTrue((await r.select((0,'DP-10')))['ok'])
        self.assertTrue(r.manual_hold);r.run.assert_awaited_once()

    async def test_no_write_in_desktop(self):
        r,n=self.runtime();r.context=None
        with patch.object(r,'observe',return_value=None):
            self.assertFalse((await r.select((0,'DP-10')))['ok'])
        r.run.assert_not_awaited()

    async def test_get_diagnostics_does_not_start_helper(self):
        r,n=self.runtime();r.diagnostics();r.run.assert_not_awaited()

    async def test_monitor_waits_ten_seconds_and_consumes_failed_attempt(self):
        r,n=self.runtime();r.session_since=0;r.changed_since=0;r.signature=v.topology(r.nodes)
        r.select=AsyncMock(return_value={'ok':False,'error':'no change'})
        now=[9]
        async def sleep(_):
            now[0]+=1
            if now[0]>12:r.closed=True
        with patch.object(r,'observe',return_value=r.context),patch('video_runtime.time.monotonic',side_effect=lambda:now[0]),patch('video_runtime.asyncio.sleep',side_effect=sleep):
            await r.monitor()
        r.select.assert_awaited_once()

    def test_suspend_or_session_change_cancels_and_resets_manual_hold(self):
        r,n=self.runtime();r.manual_hold=True;old=r.revision
        with patch('video_runtime.scan',return_value=r.nodes),patch('video_runtime.gaming_context',return_value=r.context),patch('video_runtime.epoch',return_value=r.offset+2):
            r.observe()
        self.assertFalse(r.manual_hold);self.assertGreater(r.revision,old);self.assertIsNone(r.attempt)

    async def test_missing_preferred_monitor_releases_owned_outputs_once(self):
        r,n=self.runtime();r.nodes={};r.owned={'0:DP-12':{'id':12}};r.session_since=r.changed_since=0
        r.release=AsyncMock(return_value={'ok':True});count=[0]
        async def sleep(_):
            count[0]+=1
            if count[0]>2:r.closed=True
        with patch.object(r,'observe',return_value=r.context),patch('video_runtime.time.monotonic',return_value=20),patch('video_runtime.asyncio.sleep',side_effect=sleep):
            await r.monitor()
        r.release.assert_awaited_once()

    async def test_manual_hold_prevents_reclaim_after_a_topology_change(self):
        r,n=self.runtime();r.manual_hold=True;r.session_since=r.changed_since=0;r.select=AsyncMock()
        async def sleep(_):r.closed=True
        with patch.object(r,'observe',return_value=r.context),patch('video_runtime.time.monotonic',return_value=20),patch('video_runtime.asyncio.sleep',side_effect=sleep):
            await r.monitor()
        r.select.assert_not_awaited()


class GuardTests(unittest.TestCase):
    def check(self, *, pending=None, offset=10, frozen='0', sleep=False, shutdown=False, scope=True):
        guard=v.Guard({'epoch':10})
        def read(path, *args, **kwargs):
            if str(path)=='/proc/self/cgroup':return '0::/user.slice/output-video-1-test.scope\n' if scope else '0::/system.slice/plugin_loader.service\n'
            if str(path).endswith('cgroup.freeze'):return frozen
            raise AssertionError(path)
        output=('b true\n' if sleep else 'b false\n')+('b true\n' if shutdown else 'b false\n')
        with patch.object(v.os,'read',side_effect=BlockingIOError if pending is None else None,return_value=pending),patch.object(v.Path,'read_text',read),patch.object(v,'epoch',return_value=offset),patch.object(v.subprocess,'run',return_value=Mock(returncode=0,stdout=output)):
            guard.check(session=False)

    def test_scoped_awake_helper_is_allowed(self):self.check()
    def test_unscoped_helper_cannot_write(self):
        with self.assertRaises(v.Boundary):self.check(scope=False)
    def test_freezing_cancels(self):
        with self.assertRaises(v.Boundary):self.check(frozen='1')
    def test_changed_suspend_epoch_cancels(self):
        with self.assertRaises(v.Boundary):self.check(offset=11)
    def test_preparing_for_sleep_cancels(self):
        with self.assertRaises(v.Boundary):self.check(sleep=True)
    def test_preparing_for_shutdown_cancels(self):
        with self.assertRaises(v.Boundary):self.check(shutdown=True)
    def test_parent_eof_cancels(self):
        with self.assertRaises(v.Boundary):self.check(pending=b'')
    def test_manual_cancel_cancels(self):
        with self.assertRaises(v.Boundary):self.check(pending=b'{"cancel":true}\n')


class PluginIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_selection_tracks_identity_and_preserves_audio_settings(self):
        with tempfile.TemporaryDirectory() as d:
            stub=types.SimpleNamespace(DECKY_PLUGIN_SETTINGS_DIR=d,logger=Mock())
            with patch.dict(sys.modules,{'decky_plugin':stub}):
                import importlib.util
                spec=importlib.util.spec_from_file_location('output_test_main',Path(__file__).resolve().parents[1]/'main.py')
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            n=node('0:DP-10','AOC');module.video=Mock(nodes={n['key']:n})
            p=Path(d)/'settings.json';p.write_text(json.dumps({'audio':{'usb':{'label':'Keep'}},'config':{'targetUid':1000}}))
            result=await module.Plugin().set_config({'defaultConnector':'0:DP-10'})
            self.assertTrue(result['ok']); data=json.loads(p.read_text())
            self.assertEqual(data['config']['defaultDisplayIdentity'],n['identity'])
            self.assertEqual(data['audio'],{'usb':{'label':'Keep'}})
            await module.Plugin().set_config({'defaultConnector':None})
            self.assertIsNone(json.loads(p.read_text())['config']['defaultDisplayIdentity'])

    def test_automatic_path_never_calls_audio_switching(self):
        source=(Path(__file__).resolve().parents[1]/'video_runtime.py').read_text()
        for word in ('pactl','set_default_sink','_switch_connector_to','trigger_hotplug'):
            self.assertNotIn(word,source)


if __name__ == '__main__': unittest.main()
