import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
import zipfile
from installer import engine, video_decky as v

ROOT=Path(__file__).resolve().parents[1]
PAYLOAD=ROOT/'payloads'/engine.PAYLOADS['video-output-ally']
VERSION='1.0'


class PayloadTests(unittest.TestCase):
    def test_full_native_identity_manifest_and_hash(self):
        digest=hashlib.sha256(PAYLOAD.read_bytes()).hexdigest()
        v.check_payload(PAYLOAD,digest,VERSION)
        with self.assertRaises(RuntimeError):v.check_payload(PAYLOAD,'bad',VERSION)
        with self.assertRaises(RuntimeError):v.check_payload(PAYLOAD,digest,'wrong')

    def test_extra_unsafe_or_modified_files_rejected(self):
        for name in ('output-manager/../escape','output-manager/extra','output-manager/main.py'):
            with tempfile.TemporaryDirectory() as d:
                target=Path(d)/'bad.zip'
                with zipfile.ZipFile(PAYLOAD) as source,zipfile.ZipFile(target,'w') as out:
                    for info in source.infolist():
                        if info.filename!=name:out.writestr(info,source.read(info.filename))
                    out.writestr(name,b'changed')
                with self.assertRaises(RuntimeError):v.check_payload(target,hashlib.sha256(target.read_bytes()).hexdigest(),VERSION)

    def test_installed_bytes_must_match_not_only_version(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'DECKY_PLUGIN_DIR':d}):
            with zipfile.ZipFile(PAYLOAD) as z:z.extractall(d)
            self.assertTrue(v.installed_matches(PAYLOAD))
            (Path(d)/'output-manager/main.py').write_text('old')
            self.assertFalse(v.installed_matches(PAYLOAD))

    def test_component_preflight_is_separate_and_decky_must_be_active(self):
        with patch.object(engine,'host_errors',return_value=[]),patch.object(engine,'video_errors',return_value=[]),patch.object(engine.decky,'availability',return_value=(False,'Decky inactivo')),patch.object(engine,'ally_errors',side_effect=AssertionError('POWER')):
            self.assertEqual(engine.requirements('video-output-ally',ROOT),['Decky inactivo'])

    def test_backups_preserve_name_folder_and_settings(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'DECKY_PLUGIN_DIR':d,'XDG_STATE_HOME':d+'/state with spaces'}):
            with zipfile.ZipFile(PAYLOAD) as z:z.extractall(d)
            settings=Path(d)/'settings.json';settings.write_text('unchanged')
            target=v.decky.backup_previous(VERSION,folder_name=v.FOLDER,plugin_name=v.NAME,author='N3ruk',backup_name='Video')
            with zipfile.ZipFile(target) as z:self.assertEqual(json.loads(z.read('output-manager/package.json'))['version'],VERSION)
            self.assertEqual(settings.read_text(),'unchanged')

    def test_installation_lock_rejects_concurrent_operation_then_releases(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_STATE_HOME':d}):
            with v.installation_lock():
                with self.assertRaisesRegex(RuntimeError,'en curso'):
                    with v.installation_lock():pass
            with v.installation_lock():pass


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    def client(self,previous=None,video=None):
        client=v.Client(None,None)
        async def call(route,*args):
            if route=='loader/get_plugins':return [previous] if previous else []
            if route=='loader/call_plugin_method':return {'version':previous['version'],'video':video or {'architecture':'edid-mst-nudge-v1','gaming':False,'owned':[],'busy':False}}
        client.call=AsyncMock(side_effect=call)
        client.prompt=AsyncMock(return_value=[v.NAME,VERSION,'request','digest',2 if previous else 0])
        return client

    async def test_fresh_install_prepares_exact_request_no_hardware_call(self):
        c=self.client()
        with patch.object(v,'plugin_folder',return_value=Path('/nonexistent-video-fixture')):
            self.assertEqual(await c.prepare('/tmp/payload.zip','digest',VERSION),('request',None))
        self.assertNotIn('switch_connector',str(c.call.await_args_list))
        self.assertNotIn('confirm_plugin_install',str(c.call.await_args_list))

    async def test_legacy_output_manager_rejected_before_any_prompt(self):
        c=self.client({'name':'Output Manager','version':'1.4.0'})
        with self.assertRaisesRegex(RuntimeError,'Retira primero'):await c.prepare('/tmp/payload.zip','digest',VERSION)
        self.assertEqual(c.call.await_count,1)

    async def test_unknown_existing_folder_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d,patch.object(v,'plugin_folder',return_value=Path(d)):
            c=self.client()
            with self.assertRaisesRegex(RuntimeError,'ya existe'):await c.prepare('/tmp/payload.zip','digest',VERSION)
        self.assertEqual(c.call.await_count,1)

    async def test_gaming_ownership_or_busy_reject_before_backup_install(self):
        for key,value in [('gaming',True),('owned',['0:DP-12']),('busy',True)]:
            c=self.client({'name':v.NAME,'version':VERSION}, {'architecture':'edid-mst-nudge-v1',key:value})
            with patch.object(v.decky,'backup_previous') as backup:
                with self.assertRaisesRegex(RuntimeError,'controla salidas'):await c.prepare('/tmp/payload.zip','digest',VERSION)
                backup.assert_not_called()
            self.assertNotIn('utilities/install_plugin',str(c.call.await_args_list))

    async def test_disabled_or_unknown_version_rejected(self):
        for previous in ({'name':v.NAME,'version':VERSION,'disabled':True},{'name':v.NAME,'version':'9.0'}):
            c=self.client(previous)
            with self.assertRaises(RuntimeError):await c.prepare('/tmp/payload.zip','digest',VERSION)
            self.assertEqual(c.call.await_count,1)

    async def test_local_140_and_distribution_10_migrate_with_backup(self):
        for version in ('1.4.0','1.0'):
            c=self.client({'name':v.NAME,'version':version})
            with patch.object(v.decky,'backup_previous',return_value=Path('/tmp/backup.zip')) as backup:
                self.assertEqual(await c.prepare('/tmp/payload.zip','digest',VERSION),('request',Path('/tmp/backup.zip')))
                self.assertEqual(backup.call_args.args[0],version)
                self.assertEqual(backup.call_args.kwargs['folder_name'],'output-manager')

    async def test_wrong_prompt_never_confirmable(self):
        for index,value in [(0,'Other'),(1,'9.0'),(2,''),(3,'bad'),(4,2)]:
            c=self.client();c.prompt.return_value[index]=value
            with patch.object(v,'plugin_folder',return_value=Path('/nonexistent-video-fixture')):
                with self.assertRaisesRegex(RuntimeError,'no coincide'):await c.prepare('/tmp/payload.zip','digest',VERSION)
            self.assertNotIn('confirm_plugin_install',str(c.call.await_args_list))

    async def test_inspection_requires_file_match_and_only_reads_loader(self):
        ctx=Mock();ctx.__aenter__=AsyncMock(return_value=Mock());ctx.__aexit__=AsyncMock(return_value=False)
        session=Mock();session.ws_connect.return_value=ctx
        c=Mock();c.call=AsyncMock(side_effect=[[{'name':v.NAME,'version':VERSION}],{'version':VERSION,'video':{'architecture':'edid-mst-nudge-v1'}}]*2)
        with patch.object(v,'Client',return_value=c),patch.object(v,'installed_matches',side_effect=[False,True]):
            result=await v.inspect_ready(session,'fixture',VERSION,PAYLOAD,attempts=2,interval=0)
        self.assertEqual(result['version'],VERSION)
        self.assertTrue(all(call.args[0].startswith('loader/') for call in c.call.await_args_list))

    async def test_confirmation_not_replayed_after_disconnect(self):
        import aiohttp
        response=Mock();response.text=AsyncMock(return_value='fixture')
        get=Mock();get.__aenter__=AsyncMock(return_value=response);get.__aexit__=AsyncMock(return_value=False)
        socket=Mock();socket.__aenter__=AsyncMock(return_value=Mock());socket.__aexit__=AsyncMock(return_value=False)
        session=Mock();session.get.return_value=get;session.ws_connect.return_value=socket
        ctx=Mock();ctx.__aenter__=AsyncMock(return_value=session);ctx.__aexit__=AsyncMock(return_value=False)
        c=Mock();c.prepare=AsyncMock(return_value=('request',None));c.call=AsyncMock(side_effect=v.ConnectionLost('closed'))
        with patch.object(v.decky,'availability',return_value=(True,'')),patch.object(aiohttp,'ClientSession',return_value=ctx),patch.object(v,'Client',return_value=c),patch.object(v,'inspect_ready',new_callable=AsyncMock,return_value={'version':VERSION}):
            await v._install(PAYLOAD,hashlib.sha256(PAYLOAD.read_bytes()).hexdigest(),VERSION)
        c.call.assert_awaited_once_with('utilities/confirm_plugin_install','request')

    async def test_token_not_rendered_on_transport_error(self):
        import aiohttp
        ctx=Mock();ctx.__aenter__=AsyncMock(side_effect=aiohttp.ClientError('auth=fake-private-marker'));ctx.__aexit__=AsyncMock(return_value=False)
        with patch.object(v.decky,'availability',return_value=(True,'')),patch.object(aiohttp,'ClientSession',return_value=ctx):
            with self.assertRaises(RuntimeError) as error:
                await v._install(PAYLOAD,hashlib.sha256(PAYLOAD.read_bytes()).hexdigest(),VERSION)
        self.assertNotIn('fake-private-marker',str(error.exception))
