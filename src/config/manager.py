import yaml
import os
from typing import Dict, Any

class ConfigManager:
    """
    Manages application-level settings and LiDAR configuration.
    As per implementation plan section 12.
    """
    DEFAULT_CONFIG = {
        'lidar': {
            'ip': '192.168.2.111',
            'port': 2111,
            'protocol': 'cola_b',
            'auto_reconnect': True,
            'timeout_ms': 5000,
            'sdk_path': None,
            'launch_file': None
        },
        'scan': {
            'angle_start': -120,
            'angle_end': 120,
            'angular_resolution': 1.0,
            'scan_frequency': 14.5,
            'enable_intensity': True
        },
        'baseline': {
            'mode': 'auto',
            'height_m': 0.0,
            'floor_percentile': 15.0,
            'floor_axis': 'y',
            'selection_range': None,
            'auto_recalibrate_interval': 3600
        },
        'measurement': {
            'length': {
                'method': 'bbox',
                'units': 'm',
                'thresholds': [
                    {'level': 0.20, 'name': 'Length Warning', 'color': '#FFA500', 'action': 'log'},
                    {'level': 0.40, 'name': 'Length Critical', 'color': '#FF0000', 'action': 'alert'}
                ]
            },
            'height': {
                'units': 'm',
                'thresholds': [
                    {'level': 0.10, 'name': 'Warning', 'color': '#FFA500', 'action': 'log'},
                    {'level': 0.20, 'name': 'Critical', 'color': '#FF0000', 'action': 'alert'}
                ]
            }
        },
        'object_detection': {
            'epsilon': 0.05,
            'min_samples': 5,
            'min_object_size': 0.02,
            'max_object_size': 5.0
        },
        'scene_reference': {
            'enabled': True,
            'distance_tolerance': 0.08,
            'auto_capture': False
        },
        'display': {
            'refresh_rate': 30,
            'grid_spacing': 0.5
        },
        'alerts': {
            'output': {
                'enabled': False,
                'transport': 'gpio',
                'ip': '127.0.0.1',
                'port': 80,
                'serial_port': '/dev/serial0',
                'baudrate': 115200,
                'serial_timeout': 0.5,
                'cooldown_s': 0.5,
                'gpio_pin': 18,
                'gpio_active_high': True,
                'gpio_duration_s': 0.3
            }
        },
        'runtime': {
            'headless': False
        }
    }

    def __init__(self, config_path: str = 'config.yaml'):
        self.config_path = config_path
        self.settings = self.DEFAULT_CONFIG.copy()
        
    def load(self) -> Dict:
        """Loads settings from disk, merging with defaults."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                loaded_settings = yaml.safe_load(f)
                if loaded_settings:
                    self._migrate_legacy_alert_settings(loaded_settings)
                    # Update settings recursively
                    self._update_recursive(self.settings, loaded_settings)
                    
        return self.settings

    def save(self):
        """Saves current settings to disk."""
        with open(self.config_path, 'w') as f:
            yaml.dump(self.settings, f, default_flow_style=False)

    def get(self, key_path: str, default: Any = None) -> Any:
        """Retrieves a nested setting using dot notation (e.g., 'lidar.ip')."""
        keys = key_path.split('.')
        val = self.settings
        try:
            for k in keys:
                val = val[k]
            return val
        except (KeyError, TypeError):
            return default

    def _update_recursive(self, target, source):
        """Helper to deeply merge dictionaries."""
        for k, v in source.items():
            if isinstance(v, dict) and k in target and isinstance(target[k], dict):
                self._update_recursive(target[k], v)
            else:
                target[k] = v

    def _migrate_legacy_alert_settings(self, loaded_settings):
        alerts = loaded_settings.get('alerts')
        if not isinstance(alerts, dict):
            return

        legacy = alerts.get('esp32')
        if isinstance(legacy, dict):
            output = alerts.setdefault('output', {})
            self._update_recursive(output, legacy)
