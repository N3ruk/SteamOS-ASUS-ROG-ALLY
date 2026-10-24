import os
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from py_modules import rgb, rgb_hid as hid
from test_rgb import DeviceFixture


DESCRIPTOR = bytes.fromhex('06 31 ff 09 76 a1 01 85 5a 75 08 95 3f b1 00 c0')


class ProtocolTests(unittest.TestCase):
    def test_four_zones_are_rgb_and_dimmer_is_scaled_not_truncated(self):
        bright, report = hid.reports([0xFF0000, 0x00FF00, 0x0000FF, 0x123456], 255)
        self.assertEqual(bright[:5], bytes.fromhex('5a ba c5 c4 03'))
        self.assertEqual(report[:16], bytes.fromhex('5a d1 08 0c ff 00 00 00 ff 00 00 00 ff 12 34 56'))
        self.assertEqual(report[16:], bytes(48))
        self.assertEqual(hid.reports([0xFFFFFF]*4, 128)[1][4:16], bytes([128])*12)
        off, color = hid.reports([0xFFFFFF]*4, 0)
        self.assertEqual(off[4], 0)
        self.assertEqual(color[4:16], bytes(12))

    def test_all_other_commands_and_nonzero_padding_are_rejected(self):
        for command in range(256):
            packet = bytes([0x5A, 0xD1, command, 0x0C]) + bytes(60)
            if command == 8: hid.validate_report(packet)
            else:
                with self.assertRaises(ValueError): hid.validate_report(packet)
        for packet in [bytes(64), b'\x5a\xd1\x08\x0c'+bytes(59)+b'\x01',
                       b'\x5a\xba\xc5\xc4\x02'+bytes(59), bytes(16), bytearray(64)]:
            with self.assertRaises(ValueError): hid.validate_report(packet)

    def test_invalid_frames_never_reach_transport(self):
        for colors, brightness in [([0]*3, 1), ([True]*4, 100), ([0x1000000]*4, 0), ([0]*4, True), ([0]*4, 256)]:
            with self.assertRaises(ValueError): hid.reports(colors, brightness)

    def test_feature_descriptor_is_parsed_and_truncation_rejected(self):
        self.assertEqual(hid.feature_capacity(DESCRIPTOR), 504)
        self.assertEqual(hid.feature_capacity(bytes.fromhex('85 5d 75 08 95 3f b1 00')), 0)
        self.assertEqual(hid.feature_capacity(bytes.fromhex('26 85 5a')), 0)
        for raw in [b'\x85', b'\xfe', b'\xb4']:
            with self.assertRaises(ValueError): hid.feature_capacity(raw)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        interface = self.root/'usb-interface'
        interface.mkdir()
        (interface/'bInterfaceNumber').write_text('02')
        self.device = interface/'hid-device'
        self.device.mkdir()
        (self.device/'uevent').write_text('HID_ID=0003:00000B05:00001ABE\n')
        (self.device/'report_descriptor').write_bytes(DESCRIPTOR)
        (self.root/'asus_rog_ally').mkdir()
        (self.device/'driver').symlink_to(self.root/'asus_rog_ally')
        self.nodes = self.root/'hidraw'
        self.nodes.mkdir()
        entry = self.nodes/'hidraw17'; entry.mkdir()
        (entry/'device').symlink_to(self.device)
        (entry/'dev').write_text('244:17')
        self.dev = self.root/'dev'

    def locate(self): return hid.locate(self.device, self.nodes, self.dev)

    def test_only_same_led_device_is_discovered_without_opening(self):
        with patch.object(os, 'open', side_effect=AssertionError('read-only discovery')):
            self.assertEqual(self.locate(), (self.dev/'hidraw17', str(self.device), os.makedev(244,17)))

    def test_wrong_vendor_interface_driver_or_descriptor_rejected(self):
        for path, bad in [(self.device/'uevent', 'HID_ID=0003:0000054C:000005C4'),
                          (self.device.parent/'bInterfaceNumber', '00'),
                          (self.device/'report_descriptor', 'bad')]:
            original = path.read_bytes()
            path.write_text(bad)
            with self.assertRaises(ValueError): self.locate()
            path.write_bytes(original)
        (self.device/'driver').unlink()
        (self.device/'driver').symlink_to(self.root/'keyboard')
        with self.assertRaises(ValueError): self.locate()

    def test_ambiguous_or_other_hid_device_rejected(self):
        entry = self.nodes/'hidraw18'; entry.mkdir()
        (entry/'device').symlink_to(self.device)
        (entry/'dev').write_text('244:18')
        with self.assertRaises(ValueError): self.locate()
        (entry/'device').unlink()
        (entry/'device').symlink_to(self.root)
        self.assertEqual(self.locate()[0], self.dev/'hidraw17')


class TransportTests(unittest.TestCase):
    def test_fd_identity_and_only_two_allowed_feature_commands(self):
        identity = (Path('/dev/fake-rgb'), '/fake/device', os.makedev(244, 17))
        transport = hid.RGBTransport(Mock(return_value=identity))
        calls = []
        def ioctl(fd, cmd, data, mutate):
            if cmd == hid.GET_INFO:
                data[:] = struct.pack('=Ihh', 3, 0x0B05, 0x1ABE)
                return 0
            self.assertEqual(cmd, hid.SET_FEATURE)
            hid.validate_report(bytes(data)); calls.append(bytes(data)); return 64
        with patch.object(os, 'open', return_value=41) as opened, patch.object(os, 'close') as closed, \
             patch.object(os, 'fstat', return_value=SimpleNamespace(st_mode=stat.S_IFCHR, st_rdev=identity[2])), \
             patch.object(hid.fcntl, 'ioctl', side_effect=ioctl):
            transport.write(Path('/fake/device'), [0x123456]*4, 255)
            transport.write(Path('/fake/device'), [0x654321]*4, 128)
            self.assertEqual(len(calls), 3)  # brightness once, two colors
            self.assertTrue(opened.call_args.args[1] & os.O_NOFOLLOW)
            transport.close(); closed.assert_called_once_with(41)

    def test_bad_opened_identity_never_sends_and_closes(self):
        identity = (Path('/dev/fake-rgb'), '/fake/device', 42)
        transport = hid.RGBTransport(Mock(return_value=identity))
        with patch.object(os, 'open', return_value=41), patch.object(os, 'close') as closed, \
             patch.object(os, 'fstat', return_value=SimpleNamespace(st_mode=stat.S_IFREG, st_rdev=42)), \
             patch.object(hid.fcntl, 'ioctl') as ioctl:
            with self.assertRaises(ValueError): transport.write(Path('/fake'), [0]*4, 255)
            ioctl.assert_not_called(); closed.assert_called_once_with(41)
        self.assertIsNone(transport.fd)

    def test_short_feature_result_is_failure_not_fake_readback(self):
        transport = hid.RGBTransport()
        transport.fd = 41
        with patch.object(hid.fcntl, 'ioctl', return_value=8):
            with self.assertRaises(OSError): transport._send(hid.reports([0]*4,255)[1])

    def test_disappearance_closes_existing_descriptor_without_sending(self):
        transport = hid.RGBTransport(Mock(side_effect=FileNotFoundError('unplugged')))
        transport.fd = 41
        with patch.object(os, 'close') as closed, patch.object(hid.fcntl,'ioctl') as ioctl:
            with self.assertRaises(FileNotFoundError): transport.write(Path('/fake'), [0]*4, 255)
            closed.assert_called_once_with(41); ioctl.assert_not_called()
        self.assertIsNone(transport.fd)

    def test_wrong_usb_identity_after_open_never_sends_feature(self):
        identity = (Path('/dev/fake-rgb'), '/fake/device', 42)
        transport = hid.RGBTransport(Mock(return_value=identity))
        def ioctl(fd, command, data, mutate):
            self.assertEqual(command, hid.GET_INFO)
            data[:] = struct.pack('=Ihh', 3, 0x054C, 0x05C4)
        with patch.object(os,'open',return_value=41), patch.object(os,'close') as closed, \
             patch.object(os,'fstat',return_value=SimpleNamespace(st_mode=stat.S_IFCHR,st_rdev=42)), \
             patch.object(hid.fcntl,'ioctl',side_effect=ioctl):
            with self.assertRaisesRegex(ValueError, 'USB'): transport.write(Path('/fake'), [0]*4,255)
            closed.assert_called_once_with(41)


class HardwareFallbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.fixture = DeviceFixture(root)
        (self.fixture.path/'multi_max_intensity').write_text('255 255 255 255')
        (root/'device').mkdir()
        (self.fixture.path/'device').symlink_to(root/'device')
        self.transport = Mock()
        self.hw = rgb.Hardware(self.fixture.path, self.fixture.product, self.transport)

    def test_discovery_and_get_state_never_send_reports(self):
        state = self.hw.state()
        self.assertEqual(state['backend'], 'hid-rgb')
        self.assertEqual(state['verification'], 'kernel-cache-only')
        self.transport.write.assert_not_called()

    def test_rgb_full_color_is_sent_without_sysfs_writes_or_false_readback(self):
        with patch.object(Path, 'write_text', side_effect=AssertionError('no sysfs writes')):
            state = self.hw.write([0x123456]*4, 200)
        self.assertEqual(state['colors'], [0x123456]*4)
        self.assertEqual(state['verification'], 'transport-accepted')
        self.assertEqual((self.fixture.path/'multi_intensity').read_text(), '0 0 0 0')
        self.hw.state(); self.assertEqual(self.transport.write.call_count, 1)

    def test_external_kernel_change_is_not_hidden_and_close_discards_cache(self):
        self.hw.write([0x123456]*4, 200)
        (self.fixture.path/'brightness').write_text('7')
        with self.assertRaisesRegex(rgb.RGBError, 'cedido'): self.hw.state()
        self.hw.close(); self.transport.close.assert_called_once()
        self.assertEqual(self.hw.state()['verification'], 'kernel-cache-only')

    def test_send_failure_closes_without_rollback_over_an_unknown_device(self):
        self.transport.write.side_effect = OSError('disconnected')
        with self.assertRaises(OSError): self.hw.write([0x123456]*4, 200)
        self.transport.close.assert_called_once()
        self.assertIsNone(self.hw.hid_last)

    def test_compatible_kernel_retains_sysfs_backend(self):
        (self.fixture.path/'multi_max_intensity').write_text('16777215 '*4)
        state = self.hw.write([0x123456]*4, 200)
        self.assertEqual(state['backend'], 'sysfs')
        self.assertEqual(state['verification'], 'kernel-readback')
        self.transport.write.assert_not_called()

    def test_unknown_limits_and_missing_transport_fail_closed(self):
        (self.fixture.path/'multi_max_intensity').write_text('255 255 255')
        with self.assertRaises(rgb.RGBError): self.hw.write([0]*4, 0)
        self.transport.write.assert_not_called()
