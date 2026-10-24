"""RC71L RGB-only hidraw transport. No generic HID command API or dependencies.

Wire format: hid-asus-ally's LED commands (Luke Jones); see THIRD-PARTY.md.
Only SET_FEATURE 0x5a:d1:08:0c (four RGB zones) and 0x5a:ba:c5:c4 (LED
brightness) are permitted. No input reads, driver detach or persistent settings.
"""
import fcntl
import os
from pathlib import Path
import re
import stat
import struct

REPORT_SIZE = 64
SET_FEATURE = 0xC0404806  # HIDIOCSFEATURE(64), Linux x86_64
GET_INFO = 0x80084803    # HIDIOCGRAWINFO, struct hidraw_devinfo
RGB_PREFIX = bytes.fromhex('5a d1 08 0c')
BRIGHTNESS_PREFIX = bytes.fromhex('5a ba c5 c4')


def feature_capacity(descriptor):
    """Parse HID items, not byte substrings that could occur inside other items."""
    report_id = size = count = 0
    stack, totals = [], {}
    i = 0
    while i < len(descriptor):
        tag = descriptor[i]
        i += 1
        if tag == 0xFE:
            raise ValueError('Descriptor HID largo no admitido.')
        length = (0, 1, 2, 4)[tag & 3]
        if i + length > len(descriptor):
            raise ValueError('Descriptor HID truncado.')
        value = int.from_bytes(descriptor[i:i+length], 'little')
        i += length
        item = tag & 0xFC
        if item == 0x84: report_id = value
        elif item == 0x74: size = value
        elif item == 0x94: count = value
        elif item == 0xA4: stack.append((report_id, size, count))
        elif item == 0xB4:
            if not stack: raise ValueError('Descriptor HID no válido.')
            report_id, size, count = stack.pop()
        elif item == 0xB0:
            totals[report_id] = totals.get(report_id, 0) + size * count
    return totals.get(0x5A, 0)


def locate(device, root=Path('/sys/class/hidraw'), devroot=Path('/dev')):
    """Select the *same* LED's USB interface 02, never a keyboard or another Ally."""
    device = device.resolve(strict=True)
    identity = dict(line.split('=', 1) for line in (device/'uevent').read_text().splitlines() if '=' in line)
    if identity.get('HID_ID') != '0003:00000B05:00001ABE':
        raise ValueError('Identidad RGB ASUS no admitida.')
    if (device.parent/'bInterfaceNumber').read_text().strip() != '02':
        raise ValueError('No es la interfaz RGB 02 de la Ally.')
    if (device/'driver').resolve().name != 'asus_rog_ally':
        raise ValueError('El dispositivo RGB no usa el controlador esperado.')
    if feature_capacity((device/'report_descriptor').read_bytes()) != 63 * 8:
        raise ValueError('El dispositivo no anuncia el informe RGB esperado.')
    candidates = []
    for entry in root.glob('hidraw*'):
        if re.fullmatch(r'hidraw[0-9]+', entry.name) and (entry/'device').resolve() == device:
            number = (entry/'dev').read_text().strip().split(':')
            if len(number) != 2: raise ValueError('Identidad hidraw no válida.')
            candidates.append((devroot/entry.name, str(device), os.makedev(*map(int, number))))
    if len(candidates) != 1:
        raise ValueError('No se encontró una interfaz hidraw RGB única para esta Ally.')
    return candidates[0]


def reports(colors, brightness):
    if (not isinstance(colors, list) or len(colors) != 4 or
            any(type(c) is not int or not 0 <= c <= 0xFFFFFF for c in colors) or
            type(brightness) is not int or not 0 <= brightness <= 255):
        raise ValueError('Frame RGB no válido.')
    # Firmware has four brightness levels. Use maximum enabled level and scale
    # RGB channels in software to retain the user's continuous global dimmer.
    level = 3 if brightness else 0
    bright = BRIGHTNESS_PREFIX + bytes([level]) + bytes(REPORT_SIZE-5)
    channels = bytes(((c >> shift & 255) * brightness + 127)//255
                     for c in colors for shift in (16, 8, 0))
    color = RGB_PREFIX + channels + bytes(REPORT_SIZE-16)
    return bright, color


def validate_report(report):
    if type(report) is not bytes or len(report) != REPORT_SIZE:
        raise ValueError('Informe RGB no válido.')
    if report[:4] == RGB_PREFIX and not any(report[16:]):
        return
    if report[:4] == BRIGHTNESS_PREFIX and report[4] in (0, 3) and not any(report[5:]):
        return
    raise ValueError('Orden HID ajena a iluminación rechazada.')


class RGBTransport:
    def __init__(self, locator=locate):
        self.locator = locator
        self.fd = None
        self.identity = None
        self.level = None

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
        self.fd = self.identity = self.level = None

    def write(self, device, colors, brightness):
        bright, color = reports(colors, brightness)
        for report in (bright, color): validate_report(report)
        try:
            identity = self.locator(device)
            if self.identity != identity:
                self.close()
                fd = os.open(identity[0], os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
                self.fd = fd
                actual = os.fstat(fd)
                if not stat.S_ISCHR(actual.st_mode) or actual.st_rdev != identity[2]:
                    raise ValueError('El nodo hidraw cambió de identidad.')
                info = bytearray(8)
                fcntl.ioctl(fd, GET_INFO, info, True)
                if struct.unpack('=Ihh', info) != (3, 0x0B05, 0x1ABE):
                    raise ValueError('La identidad USB del descriptor abierto no coincide.')
                self.identity = identity
            # Recheck before sending; never reuse an fd across a rebind/replug.
            if self.locator(device) != self.identity:
                raise ValueError('El dispositivo RGB cambió durante la operación.')
            if self.level != bright[4]:
                self._send(bright)
                self.level = bright[4]
            self._send(color)
        except BaseException:
            self.close()
            raise

    def _send(self, report):
        validate_report(report)
        result = fcntl.ioctl(self.fd, SET_FEATURE, bytearray(report), True)
        if result != REPORT_SIZE:
            raise OSError('El transporte no aceptó el informe RGB completo.')
