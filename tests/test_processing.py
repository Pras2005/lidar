import unittest
import numpy as np
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from processing.detector import ObjectDetector
from processing.measurement import MeasurementEngine
from processing.baseline import BaselineCalibration
from processing.background import BackgroundSubtractor
from alerts.monitor import ThresholdMonitor
from alerts.esp32_client import ESP32AlertClient
from lidar.datatypes import SICK_POINT_DTYPE

class TestProcessingLogic(unittest.TestCase):
    def setUp(self):
        # We use slightly larger epsilon and smaller min_samples for basic unit testing
        self.detector = ObjectDetector(epsilon=0.2, min_samples=2)
        self.measurer = MeasurementEngine(length_method='bbox', units='m')
        self.baseline = BaselineCalibration(mode='manual', fixed_height=2.0)

    def create_points(self, x_coords, y_coords):
        """Helper to create a structured numpy array for testing."""
        n = len(x_coords)
        points = np.zeros(n, dtype=SICK_POINT_DTYPE)
        points['x'] = x_coords
        points['y'] = y_coords
        points['z'] = 0
        points['i'] = 100
        return points

    def test_object_detection(self):
        """Verify that DBSCAN correctly clusters two distinct groups with robust data."""
        # Two clusters with 3 points each, points are very close (0.05m apart)
        # Cluster 1 around (1,1)
        x1 = [1.0, 1.05, 1.0]
        y1 = [1.0, 1.0, 1.05]
        # Cluster 2 around (5,5)
        x2 = [5.0, 5.05, 5.0]
        y2 = [5.0, 5.0, 5.05]
        
        points = self.create_points(x1 + x2, y1 + y2)
        
        objects = self.detector.detect_objects(points)
        self.assertEqual(len(objects), 2, f"Should have detected exactly 2 objects, found {len(objects)}")

    def test_length_measurement_bbox(self):
        """Verify bounding box length calculation (1m wide object)."""
        x = [0.0, 1.0, 0.5] # 1 meter wide
        y = [2.0, 2.0, 2.0]
        points = self.create_points(x, y)
        
        m = self.measurer.measure_object(points, baseline_height=2.0)
        self.assertAlmostEqual(m['length'], 1.0, places=2)
        self.assertAlmostEqual(m['width'], 1.0, places=2)
        self.assertAlmostEqual(m['depth'], 0.0, places=2)
        self.assertAlmostEqual(m['length_m'], 1.0, places=2)
        self.assertAlmostEqual(m['distance_m'], np.hypot(0.5, 2.0), places=2)
        self.assertEqual(m['centroid'], (0.5, 2.0))
        self.assertAlmostEqual(m['distance'], np.hypot(0.5, 2.0), places=2)
        self.assertEqual(m['max_height_point'], (0.0, 2.0))
        self.assertEqual(m['bounds']['min_x'], 0.0)
        self.assertEqual(m['bounds']['max_x'], 1.0)

    def test_height_measurement(self):
        """Verify height above baseline calculation."""
        # Baseline is 2.0m (distance from sensor)
        # Object is at 1.5m (distance from sensor)
        # Resulting height = 2.0 - 1.5 = 0.5m
        x = [0.0]
        y = [1.5]
        points = self.create_points(x, y)
        
        m = self.measurer.measure_object(points, baseline_height=2.0)
        self.assertAlmostEqual(m['height_above_baseline'], 0.5, places=2)
        self.assertAlmostEqual(m['height_above_baseline_m'], 0.5, places=2)

    def test_display_units_do_not_overwrite_metric_fields(self):
        """Converted UI units should not affect raw metric values used for alerts/logging."""
        measurer = MeasurementEngine(length_method='bbox', units='cm')
        points = self.create_points([0.0, 0.15, 0.15], [0.55, 0.55, 0.70])

        m = measurer.measure_object(points, baseline_height=0.70)

        self.assertAlmostEqual(m['length'], 15.0, places=2)
        self.assertAlmostEqual(m['length_m'], 0.15, places=2)
        self.assertAlmostEqual(m['height_above_baseline'], 15.0, places=2)
        self.assertAlmostEqual(m['height_above_baseline_m'], 0.15, places=2)

    def test_baseline_calibration_wizard(self):
        """Verify that the baseline wizard averages scans correctly using dense data."""
        self.baseline.mode = 'auto'
        self.baseline.reset()
        
        # Create a dense scan (100 points) to satisfy the >20 points guard
        # All points represent a flat floor at 2.0m distance
        x_vals = np.linspace(-2, 2, 100)
        y_vals = np.full(100, 2.0)
        points = self.create_points(x_vals, y_vals)
        
        # Simulate 10 scans to fill the calibration buffer
        for _ in range(10):
            self.baseline.auto_calibrate_floor(points, num_scans=10)
            
        self.assertTrue(self.baseline.is_calibrated, "Wizard should be calibrated after 10 dense scans")
        self.assertAlmostEqual(self.baseline.baseline_height, 2.0, places=2)

    def test_manual_floor_calibration_uses_current_scan(self):
        """Manual calibration should lock baseline to the floor points from the visible scan."""
        x_vals = np.linspace(-1, 1, 80)
        floor_y = np.full(40, 0.70)
        box_top_y = np.full(40, 0.55)
        points = self.create_points(x_vals, np.concatenate([floor_y, box_top_y]))

        baseline = BaselineCalibration(mode='auto', fixed_height=0.0, floor_percentile=20.0)
        calibrated_height = baseline.calibrate_from_scan(points)

        self.assertAlmostEqual(calibrated_height, 0.70, places=3)
        self.assertTrue(baseline.is_calibrated)
        self.assertEqual(baseline.mode, 'manual')

    def test_manual_floor_calibration_can_use_selected_x_range(self):
        """Selected view strip should define which wall segment becomes the baseline."""
        left_x = np.linspace(-2.0, -1.0, 40)
        mid_x = np.linspace(-0.2, 0.2, 40)
        y_vals = np.concatenate([np.full(40, 0.90), np.full(40, 0.70)])
        points = self.create_points(np.concatenate([left_x, mid_x]), y_vals)

        baseline = BaselineCalibration(mode='auto', floor_percentile=20.0)
        calibrated_height = baseline.calibrate_from_scan(points, selection_range=(-0.3, 0.3))

        self.assertAlmostEqual(calibrated_height, 0.70, places=3)
        self.assertEqual(baseline.selection_range, (-0.3, 0.3))

    def test_height_measurement_can_use_x_axis_reference(self):
        """A wall reference on X should measure object extent from that wall."""
        points = self.create_points([-0.90, -0.70, -0.75], [1.0, 1.0, 1.1])

        m = self.measurer.measure_object(points, baseline_height=-1.0, baseline_axis='x')

        self.assertAlmostEqual(m['height_above_baseline_m'], 0.30, places=2)
        self.assertEqual(m['baseline_axis'], 'x')

    def test_monitor_checks_height_and_length_thresholds(self):
        """Alerting should evaluate both baseline height and measured length."""
        monitor = ThresholdMonitor(
            height_thresholds=[{'level': 0.10, 'name': 'Height Warning', 'color': '#FFA500', 'action': 'log'}],
            length_thresholds=[{'level': 0.20, 'name': 'Length Critical', 'color': '#FF0000', 'action': 'alert'}],
        )
        measurement = {
            'height_above_baseline_m': 0.15,
            'length_m': 0.25,
        }

        alerts = monitor.check_measurements(measurement)

        self.assertEqual(len(alerts), 2)
        self.assertEqual({alert['metric'] for alert in alerts}, {'height', 'length'})

    def test_background_subtraction_removes_static_room_shell(self):
        """Reference scan should suppress static wall points and keep only new object points."""
        background = BackgroundSubtractor(enabled=True, distance_tolerance=0.05)
        reference = self.create_points([0.0, 1.0, -1.0], [4.0, 4.0, 4.0])
        current = self.create_points([0.0, 1.0, -1.0, 0.2, 0.3], [4.0, 4.0, 4.0, 2.0, 2.0])

        background.capture(reference)
        foreground = background.filter_foreground(current)

        self.assertEqual(len(foreground), 2)

    def test_detector_filters_tiny_clusters(self):
        """Clusters below the configured size threshold should be ignored."""
        detector = ObjectDetector(epsilon=0.25, min_samples=2, min_object_size=0.1)
        points = self.create_points([1.0, 1.03, 3.0, 3.2], [1.0, 1.02, 3.0, 3.0])

        objects = detector.detect_objects(points)

        self.assertEqual(len(objects), 1)

    def test_alert_client_can_switch_to_serial_transport(self):
        """Alert client should keep serial transport settings in config."""
        client = ESP32AlertClient(ip='192.168.1.10', enabled=True)

        client.configure(
            transport='serial',
            serial_port='/dev/ttyUSB1',
            baudrate=57600,
            cooldown_s=1.5,
        )

        payload = client._build_payload('Critical', 0.42)
        self.assertEqual(client.transport, 'serial')
        self.assertEqual(client.serial_port, '/dev/ttyUSB1')
        self.assertEqual(client.baudrate, 57600)
        self.assertEqual(client.cooldown_s, 1.5)
        self.assertEqual(payload['level'], 'Critical')

    def test_alert_client_can_switch_to_gpio_transport(self):
        """GPIO transport should keep Raspberry Pi buzzer settings in config."""
        client = ESP32AlertClient(ip='192.168.1.10', enabled=True)

        client.configure(
            transport='gpio',
            gpio_pin=23,
            gpio_active_high=False,
            gpio_duration_s=0.75,
        )

        self.assertEqual(client.transport, 'gpio')
        self.assertEqual(client.gpio_pin, 23)
        self.assertFalse(client.gpio_active_high)
        self.assertEqual(client.gpio_duration_s, 0.75)

    def test_forklift_vs_human_alert_logic(self):
        """Verify that only objects exceeding the 0.9m threshold trigger an alert."""
        monitor = ThresholdMonitor(
            length_thresholds=[{'level': 0.9, 'name': 'Forklift Alert', 'color': '#FF0000', 'action': 'alert'}],
        )
        
        # 1. Simulate a Human (0.4m wide)
        human_meas = {'length_m': 0.4, 'height_above_baseline_m': 0.0}
        human_alerts = monitor.check_measurements(human_meas)
        self.assertEqual(len(human_alerts), 0, "Human should not trigger an alert")
        
        # 2. Simulate a Forklift (1.5m wide)
        forklift_meas = {'length_m': 1.5, 'height_above_baseline_m': 0.0}
        forklift_alerts = monitor.check_measurements(forklift_meas)
        self.assertEqual(len(forklift_alerts), 1, "Forklift MUST trigger an alert")
        self.assertEqual(forklift_alerts[0]['name'], 'Forklift Alert')

if __name__ == '__main__':
    unittest.main()
