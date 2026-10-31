import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from display_names import DisplayNames, manufacturer
from settings_store import SettingsStore
from video_selector import identity
from test_video import edid, node


def branded(name='24G2WG3-', code='AOC'):
    data = bytearray(edid(name))
    packed = sum((ord(c)-64) << shift for c, shift in zip(code, (10, 5, 0)))
    data[8:10] = packed.to_bytes(2, 'big')
    data[-1] = 0
    data[-1] = -sum(data) % 256
    return bytes(data)


class NameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.registry = self.root/'pnp.ids'
        self.registry.write_text('ZZZ\tExample Display Co\n')
        self.names = DisplayNames(self.root, self.registry)

    def monitor(self, key='0:DP-10', label='24G2WG3-', code='AOC'):
        n = node(key, label)
        data = branded(label, code)
        n['identity'] = identity(data)
        card, name = key.split(':')
        p = self.root/f'card{card}-{name}'
        p.mkdir(exist_ok=True)
        (p/'edid').write_bytes(data)
        return n

    def test_real_vendor_and_model_name(self):
        n = self.monitor()
        self.assertEqual(self.names.detected(n), 'AOC 24G2WG3')
        n = self.monitor('0:DP-12', 'KG251Q', 'ACR')
        self.assertEqual(self.names.detected(n), 'Acer KG251Q')

    def test_registry_tab_separated_and_unknown_vendor_fallback(self):
        for code, expected in [('ZZZ', 'Example Display Co'), ('XYZ', 'XYZ')]:
            n = self.monitor(label='Panel', code=code)
            self.assertEqual(self.names.detected(n), expected+' Panel')

    def test_internal_name_overrides_old_custom_label(self):
        n = node('0:eDP-1', 'panel', internal=True)
        result = self.names.connectors({n['key']: n}, {n['key']: {'label': 'old'}})
        self.assertEqual(result[0]['label'], 'ASUS ALLY')

    def test_custom_label_preserved_and_no_edid_read(self):
        n = self.monitor()
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('unexpected read')):
            result = self.names.connectors({n['key']:n}, {n['key']:{'label':'Mi monitor', 'hidden': True}})
        self.assertEqual(result[0]['label'], 'Mi monitor')
        self.assertTrue(result[0]['hidden'])

    def test_names_do_not_change_selection_identity_or_nodes(self):
        n = self.monitor(); nodes = {n['key']: n}; before = copy.deepcopy(nodes)
        self.names.connectors(nodes, {})
        self.assertEqual(nodes, before)

    def test_name_cache_survives_renumber_and_edid_temporarily_absent(self):
        n = self.monitor(); self.names.connectors({n['key']:n}, {})
        n['key'] = '0:DP-14'
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('cached identity')):
            self.assertEqual(self.names.connectors({n['key']:n}, {})[0]['label'], 'AOC 24G2WG3')

    def test_reused_connector_cannot_supply_another_monitors_brand(self):
        n = self.monitor(); n['identity'] = identity(branded('different', 'ACR'))
        self.assertEqual(self.names.detected(n), '24G2WG3')

    def test_no_edid_falls_back_to_connector_and_invalid_vendor_is_empty(self):
        n = node('0:DP-10', '')
        self.assertEqual(self.names.detected(n), '0:DP-10')
        self.assertEqual(manufacturer(edid('name')), '')

    def test_duplicate_external_names_disambiguated_without_changing_ids(self):
        a = self.monitor(); b = self.monitor('0:DP-12')
        result = self.names.connectors({a['key']: a, b['key']: b}, {})
        self.assertEqual([n['label'] for n in result], ['AOC 24G2WG3 (0:DP-10)', 'AOC 24G2WG3 (0:DP-12)'])


class StoreTests(unittest.TestCase):
    def test_roundtrip_preserves_legacy_audio_labels_and_unknown_fields(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'settings.json'; s = SettingsStore(p)
            data = {'connectors': {'0:DP-12': {'label': 'custom'}}, 'audio': {'usb': {'label': 'Keep'}},
                    'extra': [1, 2], 'config': {'defaultDisplayIdentity': 'edid:keep'}}
            s.save(data)
            self.assertEqual(s.load(), data)
            self.assertEqual(s.config()['defaultDisplayIdentity'], 'edid:keep')

    def test_failed_atomic_replace_leaves_old_file_intact(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'settings.json'; s = SettingsStore(p); s.save({'old': True})
            before = p.read_bytes()
            with patch('settings_store.os.replace', side_effect=OSError('disk error')):
                with self.assertRaises(OSError): s.save({'old': False})
            self.assertEqual(p.read_bytes(), before)
            self.assertEqual(list(Path(d).iterdir()), [p])

    def test_corrupt_settings_never_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'settings.json'; p.write_text('broken')
            with self.assertRaises(ValueError): SettingsStore(p).config()
            self.assertEqual(p.read_text(), 'broken')

    def test_old_connector_config_normalized_without_mutating_disk(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'settings.json'; p.write_text('{"config":{"defaultConnector":"DP-1"}}')
            before = p.read_bytes()
            self.assertIsNone(SettingsStore(p).config()['defaultConnector'])
            self.assertEqual(p.read_bytes(), before)


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        stub = types.SimpleNamespace(DECKY_PLUGIN_SETTINGS_DIR=self.tmp.name, logger=Mock())
        with patch.dict(sys.modules, {'decky_plugin':stub}):
            spec = importlib.util.spec_from_file_location('panel_test_main', Path(__file__).resolve().parents[1]/'main.py')
            self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.node = node('0:eDP-1', 'internal', enabled=True, internal=True)
        self.runtime = Mock(nodes={self.node['key']:self.node})
        self.runtime.diagnostics.return_value = {'gaming':False}
        self.runtime.select = AsyncMock(return_value={'ok':True})
        self.module.video = self.runtime

    async def test_state_queries_only_cached_video_without_audio_or_mutations(self):
        with patch('subprocess.run', side_effect=AssertionError('unexpected process')):
            result = await self.module.Plugin().get_state()
        self.assertEqual(result['connectors'][0]['label'], 'ASUS ALLY')
        self.assertEqual(result['currentConnector'], self.node['key'])
        self.assertNotIn('audio', result)
        self.runtime.observe.assert_not_called()
        self.runtime.select.assert_not_awaited()
        for name in ('switch_audio', 'use_connector_sink', 'update_output', 'forget_output'):
            self.assertFalse(hasattr(self.module.Plugin, name))

    async def test_manual_choice_delegates_exactly_once_to_unchanged_guarded_engine(self):
        result = await self.module.Plugin().switch_connector('0:eDP-1')
        self.assertTrue(result['ok'])
        self.runtime.select.assert_awaited_once_with((0, 'eDP-1'), manual=True)

    async def test_invalid_connector_rejected_before_runtime(self):
        for value in ('0:../../x', None, '', '0:Writeback-1'):
            self.assertFalse((await self.module.Plugin().switch_connector(value))['ok'])
        self.runtime.select.assert_not_awaited()
