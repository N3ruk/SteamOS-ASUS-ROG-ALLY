"""Presentation only: cached EDID names, without probing or changing outputs."""
from collections import Counter
from pathlib import Path

from video_selector import DRM, identity, model, parts

BRANDS = {'AOC': 'AOC', 'ACR': 'Acer', 'ACI': 'ASUS', 'AUS': 'ASUS',
          'DEL': 'Dell', 'SAM': 'Samsung', 'GSM': 'LG', 'HWP': 'HP',
          'BNQ': 'BenQ', 'MSI': 'MSI', 'LEN': 'Lenovo', 'PHL': 'Philips'}


def clean(value):
    return ' '.join(''.join(c for c in str(value or '') if c.isprintable()).split())[:100]


def manufacturer(data):
    if len(data) < 10:
        return ''
    code = int.from_bytes(data[8:10], 'big')
    letters = [(code >> shift) & 31 for shift in (10, 5, 0)]
    return ''.join(chr(64 + n) for n in letters) if all(1 <= n <= 26 for n in letters) else ''


class DisplayNames:
    def __init__(self, drm=DRM, pnp=Path('/usr/share/hwdata/pnp.ids')):
        self.drm = Path(drm)
        self.cache = {}
        self.vendors = {}
        try:
            for line in Path(pnp).read_text().splitlines():
                entry = line.split(None, 1)
                if len(entry) == 2 and len(entry[0]) == 3:
                    self.vendors[entry[0]] = clean(entry[1])
        except OSError:
            pass

    def detected(self, node):
        ident = node.get('identity')
        if ident and ident in self.cache:
            return self.cache[ident]
        fallback = clean(node.get('model')).rstrip(' -')
        try:
            card, connector = parts(node['key'])
            data = (self.drm / f'card{card}-{connector}' / 'edid').read_bytes()
        except (OSError, ValueError):
            return fallback or node['key']
        if not ident or identity(data) != ident:
            return fallback or node['key']
        code = manufacturer(data)
        vendor = BRANDS.get(code, self.vendors.get(code, code))
        display_model = clean(model(data)).rstrip(' -')
        # Some monitors already include their brand in the model descriptor.
        name = display_model if vendor and display_model.casefold().startswith(vendor.casefold()) else clean(f'{vendor} {display_model}')
        name = name or fallback or node['key']
        self.cache[ident] = name
        return name

    def connectors(self, nodes, saved):
        present = {n.get('identity') for n in nodes.values()}
        self.cache = {k: v for k, v in self.cache.items() if k in present}
        result = []
        for key in sorted(set(nodes) | set(saved)):
            node = nodes.get(key, {})
            config = saved.get(key, {})
            config = config if isinstance(config, dict) else {}
            label = ('ASUS ALLY' if node.get('internal') else
                     clean(config.get('label')) or (self.detected(node) if node else key))
            result.append({'id': key, 'label': label, 'hidden': bool(config.get('hidden', False)),
                           'connected': bool(node.get('connected')), 'enabled': bool(node.get('enabled')),
                           'verified': bool(node.get('identity'))})
        counts = Counter(n['label'] for n in result if n['connected'])
        for node in result:
            if node['connected'] and counts[node['label']] > 1 and node['label'] != 'ASUS ALLY':
                node['label'] += f" ({node['id']})"
        return result
