import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
import zipfile
from installer import engine, decky, rgb_decky

ROOT=Path(__file__).resolve().parents[1]
PAYLOAD=ROOT/'payloads/ALLY-RGB-1.0.0.zip'


class RGBPreflightTests(unittest.TestCase):
    def test_clamped_kernel_requires_strict_readonly_hid_discovery(self):
        def new_kernel(path):
            return '255 255 255 255' if Path(path).name == 'multi_max_intensity' else self.read(path)
        with patch.object(engine.platform,'machine',return_value='x86_64'), patch.object(engine,'read',side_effect=new_kernel):
            for ready in (True, False):
                with patch.object(engine,'rgb_hid_ready',return_value=ready), patch.object(engine.subprocess,'run') as run:
                    self.assertEqual(engine.rgb_errors() == [], ready)
                    run.assert_not_called()

    def test_unknown_kernel_limits_are_rejected(self):
        for value in ('255 255 255','oops','1024 1024 1024 1024'):
            def changed(path): return value if Path(path).name == 'multi_max_intensity' else self.read(path)
            with patch.object(engine.platform,'machine',return_value='x86_64'), patch.object(engine,'read',side_effect=changed):
                self.assertTrue(engine.rgb_errors())

    def read(self,path):
        values={'/sys/class/dmi/id/product_name':'ROG Ally RC71L_RC71L',
                'multi_index':'rgb rgb rgb rgb','multi_intensity':'0 0 0 0',
                'max_brightness':'255','brightness':'128'}
        return values.get(str(path),values.get(Path(path).name,''))

    def test_only_rc71l_and_four_packed_colors_are_eligible(self):
        with patch.object(engine.platform,'machine',return_value='x86_64'),patch.object(engine,'read',side_effect=self.read):
            self.assertEqual(engine.rgb_errors(),[])
        for product in ('ROG Ally X RC72LA_RC72LA','Other device'):
            def wrong(path):return product if str(path).endswith('product_name') else self.read(path)
            with patch.object(engine.platform,'machine',return_value='x86_64'),patch.object(engine,'read',side_effect=wrong):
                self.assertTrue(engine.rgb_errors())
        def wrong_abi(path):return 'rgb rgb rgb' if str(path).endswith('multi_index') else self.read(path)
        with patch.object(engine.platform,'machine',return_value='x86_64'),patch.object(engine,'read',side_effect=wrong_abi):
            self.assertTrue(engine.rgb_errors())

    def test_inactive_decky_disables_rgb_without_starting_any_service(self):
        with patch.object(engine,'host_errors',return_value=[]),patch.object(engine,'rgb_errors',return_value=[]), \
             patch.object(decky,'availability',return_value=(False,'Decky inactivo')),patch.object(engine.subprocess,'run') as run:
            self.assertEqual(engine.requirements('ally-rgb',ROOT),['Decky inactivo'])
            run.assert_not_called()

    def test_rgb_is_separate_from_power_hardware_checks(self):
        with patch.object(engine,'host_errors',return_value=[]),patch.object(engine,'rgb_errors',return_value=[]), \
             patch.object(decky,'availability',return_value=(True,'')),patch.object(engine,'ally_errors',side_effect=AssertionError('power domain')):
            self.assertEqual(engine.requirements('ally-rgb',ROOT),[])


class RGBPayloadTests(unittest.TestCase):
    def test_pinned_native_payload_has_exact_identity_version_and_source_manifest(self):
        digest=hashlib.sha256(PAYLOAD.read_bytes()).hexdigest()
        rgb_decky.check_payload(PAYLOAD,digest,'1.0.0')
        with self.assertRaisesRegex(RuntimeError,'SHA256'):rgb_decky.check_payload(PAYLOAD,'bad','1.0.0')
        with self.assertRaisesRegex(RuntimeError,'versión'):rgb_decky.check_payload(PAYLOAD,digest,'9.0.0')

    def test_unsafe_extra_and_changed_manifest_bytes_are_rejected(self):
        for name,content in [('ally-rgb/../escape',b'bad'),('ally-rgb/unlisted',b'bad')]:
            with tempfile.TemporaryDirectory() as d:
                path=Path(d)/'bad.zip'
                with zipfile.ZipFile(PAYLOAD) as src,zipfile.ZipFile(path,'w') as dst:
                    for item in src.infolist():dst.writestr(item,src.read(item.filename))
                    dst.writestr(name,content)
                with self.assertRaises(RuntimeError):rgb_decky.check_payload(path,hashlib.sha256(path.read_bytes()).hexdigest(),'1.0.0')

    def test_installed_file_verification_distinguishes_same_version_old_bytes(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'DECKY_PLUGIN_DIR':d}):
            with zipfile.ZipFile(PAYLOAD) as archive:archive.extractall(d)
            self.assertTrue(rgb_decky.installed_matches(PAYLOAD))
            (Path(d)/'ally-rgb/main.py').write_text('old program with same version')
            self.assertFalse(rgb_decky.installed_matches(PAYLOAD))

    def test_rgb_update_backup_is_recoverable_and_does_not_touch_settings(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'plugins/ally-rgb';folder.mkdir(parents=True)
            (folder/'plugin.json').write_text(json.dumps({'name':'ALLY RGB','author':'SteamOS Ally contributors'}))
            (folder/'package.json').write_text(json.dumps({'version':'1.0.0'}))
            (folder/'main.py').write_text('old source')
            settings=root/'settings.json';settings.write_text('private user preferences')
            with patch.dict(os.environ,{'DECKY_PLUGIN_DIR':str(root/'plugins'),'XDG_STATE_HOME':str(root/'state with spaces')}):
                target=decky.backup_previous('1.0.0',folder_name='ally-rgb',plugin_name='ALLY RGB',author='SteamOS Ally contributors',backup_name='ALLY-RGB')
            with zipfile.ZipFile(target) as archive:self.assertEqual(archive.read('ally-rgb/main.py'),b'old source')
            self.assertEqual(settings.read_text(),'private user preferences')


class RGBProtocolTests(unittest.IsolatedAsyncioTestCase):
    def client(self,previous=None,active=False,paused=False):
        client=rgb_decky.Client(None,None)
        async def call(route,*args):
            if route=='loader/get_plugins':return [previous] if previous else []
            if route=='loader/call_plugin_method':return {'version':previous['version'],'active':active,'paused':paused}
        client.call=AsyncMock(side_effect=call)
        client.prompt=AsyncMock(return_value=['ALLY RGB','1.0.0','request','digest',2 if previous else 0])
        return client

    async def test_only_requested_identity_is_prepared_and_confirmed_later(self):
        client=self.client();request,backup=await client.prepare('/tmp/payload.zip','digest','1.0.0')
        self.assertEqual(request,'request');self.assertIsNone(backup)
        self.assertNotIn('utilities/confirm_plugin_install',[c.args[0] for c in client.call.await_args_list])
        self.assertNotIn('apply_config',str(client.call.await_args_list))

    async def test_wrong_prompt_never_returns_a_confirmable_request(self):
        for index,value in [(0,'Other'),(1,'9.0.0'),(2,''),(3,'bad'),(4,2)]:
            client=self.client();client.prompt.return_value[index]=value
            with self.assertRaisesRegex(RuntimeError,'no coincide'):await client.prepare('/tmp/payload.zip','digest','1.0.0')
            self.assertNotIn('utilities/confirm_plugin_install',str(client.call.await_args_list))

    async def test_active_or_paused_existing_rgb_is_never_stopped_or_updated(self):
        for active,paused in [(True,False),(False,True)]:
            client=self.client({'name':'ALLY RGB','version':'1.2.0'},active,paused)
            with patch.object(decky,'backup_previous') as backup:
                with self.assertRaisesRegex(RuntimeError,'controla el hardware'):await client.prepare('/tmp/payload.zip','digest','1.0.0')
                backup.assert_not_called()
            self.assertNotIn('utilities/install_plugin',[c.args[0] for c in client.call.await_args_list])

    async def test_disabled_or_unknown_existing_rgb_is_not_replaced(self):
        for previous in [{'name':'ALLY RGB','version':'1.0.0','disabled':True},{'name':'ALLY RGB','version':'9.0.0'}]:
            client=self.client(previous)
            with self.assertRaises(RuntimeError):await client.prepare('/tmp/payload.zip','digest','1.0.0')
            self.assertNotIn('utilities/install_plugin',[c.args[0] for c in client.call.await_args_list])

    async def test_recognized_inactive_update_backs_up_before_request(self):
        client=self.client({'name':'ALLY RGB','version':'1.2.0'})
        with patch.object(decky,'backup_previous',return_value=Path('/tmp/copy.zip')) as backup:
            request,path=await client.prepare('/tmp/payload.zip','digest','1.0.0')
        self.assertEqual(request,'request');self.assertEqual(path,Path('/tmp/copy.zip'))
        backup.assert_called_once_with('1.2.0',folder_name='ally-rgb',plugin_name='ALLY RGB',author='SteamOS Ally contributors',backup_name='ALLY-RGB')

    async def test_ready_reconnects_read_only_and_requires_installed_bytes_not_just_version(self):
        ctx=Mock();ctx.__aenter__=AsyncMock(return_value=Mock());ctx.__aexit__=AsyncMock(return_value=False)
        session=Mock();session.ws_connect.return_value=ctx
        client=Mock();client.call=AsyncMock(side_effect=[
            [{'name':'ALLY RGB','version':'1.0.0'}],{'version':'1.0.0'},
            [{'name':'ALLY RGB','version':'1.0.0'}],{'version':'1.0.0'}])
        with patch.object(rgb_decky,'Client',return_value=client),patch.object(rgb_decky,'installed_matches',side_effect=[False,True]):
            result=await rgb_decky.inspect_ready(session,'fake-memory-only','1.0.0',PAYLOAD,attempts=2,interval=0)
        self.assertEqual(result['version'],'1.0.0')
        self.assertTrue(all(c.args[0].startswith('loader/') for c in client.call.await_args_list))

    async def test_confirmation_is_sent_once_even_if_the_frontend_reconnects(self):
        import aiohttp
        response=Mock();response.text=AsyncMock(return_value='fake-memory-only')
        get=Mock();get.__aenter__=AsyncMock(return_value=response);get.__aexit__=AsyncMock(return_value=False)
        socket=Mock();socket.__aenter__=AsyncMock(return_value=Mock());socket.__aexit__=AsyncMock(return_value=False)
        session=Mock();session.get.return_value=get;session.ws_connect.return_value=socket
        context=Mock();context.__aenter__=AsyncMock(return_value=session);context.__aexit__=AsyncMock(return_value=False)
        client=Mock();client.prepare=AsyncMock(return_value=('request',None));client.call=AsyncMock(side_effect=rgb_decky.ConnectionLost('closed'))
        with patch.object(decky,'availability',return_value=(True,'')),patch.object(aiohttp,'ClientSession',return_value=context), \
             patch.object(rgb_decky,'Client',return_value=client),patch.object(rgb_decky,'inspect_ready',new_callable=AsyncMock,return_value={'version':'1.0.0'}) as ready:
            result=await rgb_decky.install(PAYLOAD,hashlib.sha256(PAYLOAD.read_bytes()).hexdigest(),'1.0.0')
        client.call.assert_awaited_once_with('utilities/confirm_plugin_install','request')
        ready.assert_awaited_once();self.assertIn('backend comprobado',result)

    async def test_transport_error_does_not_render_authenticated_url(self):
        import aiohttp
        response=Mock();response.text=AsyncMock(return_value='fake-sensitive-marker')
        get=Mock();get.__aenter__=AsyncMock(return_value=response);get.__aexit__=AsyncMock(return_value=False)
        socket=Mock();socket.__aenter__=AsyncMock(side_effect=aiohttp.ClientConnectionError('url?auth=fake-sensitive-marker'));socket.__aexit__=AsyncMock(return_value=False)
        session=Mock();session.get.return_value=get;session.ws_connect.return_value=socket
        context=Mock();context.__aenter__=AsyncMock(return_value=session);context.__aexit__=AsyncMock(return_value=False)
        with patch.object(decky,'availability',return_value=(True,'')),patch.object(aiohttp,'ClientSession',return_value=context):
            with self.assertRaises(RuntimeError) as error:
                await rgb_decky.install(PAYLOAD,hashlib.sha256(PAYLOAD.read_bytes()).hexdigest(),'1.0.0')
        self.assertNotIn('fake-sensitive-marker',str(error.exception))
