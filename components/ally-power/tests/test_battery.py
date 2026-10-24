"""Battery telemetry fixtures only: no real battery or power setting writes."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import app


class BatteryConsumptionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def supply(self, name='BAT0', **values):
        path = self.root / name
        path.mkdir(exist_ok=True)
        for key, value in dict(type='Battery', status='Discharging', **values).items():
            (path / key).write_text(str(value))
        return path

    def test_microwatts_and_live_changes(self):
        battery = self.supply(power_now=18750000)
        self.assertEqual(app.battery_consumption(self.root), 'Consumo global actual: 18.8 W')
        (battery / 'power_now').write_text('12300000')
        self.assertEqual(app.battery_consumption(self.root), 'Consumo global actual: 12.3 W')

    def test_current_times_voltage_fallback_and_sign(self):
        for current in (1500000, -1500000):
            self.supply(current_now=current, voltage_now=16000000)
            self.assertEqual(app.battery_consumption(self.root), 'Consumo global actual: 24.0 W')

    def test_controller_battery_never_substitutes_for_internal_battery(self):
        self.supply('ps-controller-battery-test', scope='Device', power_now=999000000)
        self.assertEqual(app.battery_consumption(self.root), 'Consumo global actual: no disponible')
        battery = self.supply(power_now=14300000)
        self.assertEqual(app.battery_consumption(self.root), 'Consumo global actual: 14.3 W')
        (battery / 'power_now').unlink()
        self.assertEqual(app.battery_consumption(self.root), 'Consumo global actual: no disponible')

    def test_internal_identity_and_scope(self):
        self.supply('BAT1', scope='System', power_now=20000000)
        self.assertEqual(app.battery_consumption(self.root), 'Consumo global actual: 20.0 W')
        battery = self.supply('BAT0', scope='Device', power_now=900000000)
        self.assertEqual(app.battery_consumption(self.root), 'Consumo global actual: 20.0 W')
        (battery / 'scope').write_text('System')
        (battery / 'power_now').write_text('10000000')
        self.assertEqual(app.battery_consumption(self.root), 'Consumo global actual: 10.0 W')

    def test_charging_and_full_are_not_reported_as_system_consumption(self):
        battery = self.supply(power_now=24000000)
        for status, expected in (('Charging', 'batería cargando'),
                                 ('Full', 'batería sin descarga'),
                                 ('Not charging', 'batería sin descarga')):
            (battery / 'status').write_text(status)
            result = app.battery_consumption(self.root)
            self.assertIn(expected, result)
            self.assertNotIn('24.0 W', result)

    def test_missing_invalid_and_zero_sensor_values(self):
        battery = self.supply()
        for value in ('', 'invalid', 'NaN', '1000000000000000000'):
            (battery / 'power_now').write_text(value)
            self.assertEqual(app.battery_consumption(self.root), 'Consumo global actual: no disponible')
        (battery / 'power_now').write_text('0')
        self.assertEqual(app.battery_consumption(self.root), 'Consumo global actual: 0.0 W')
        (battery / 'power_now').write_text('invalid')
        (battery / 'current_now').write_text('1500000')
        (battery / 'voltage_now').write_text('0')
        self.assertEqual(app.battery_consumption(self.root), 'Consumo global actual: no disponible')

    def test_state_change_during_sample_discards_reading(self):
        battery = self.supply(power_now=14000000)
        original_read = app.read
        calls = []
        def read(path):
            if path == battery / 'status':
                calls.append(1)
                return 'Discharging' if len(calls) == 1 else 'Charging'
            return original_read(path)
        with patch.object(app, 'read', side_effect=read):
            self.assertEqual(app.battery_consumption(self.root), 'Consumo global actual: no disponible')
