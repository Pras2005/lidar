from typing import List, Dict, Optional

class ThresholdMonitor:
    """
    Monitors measurements against thresholds and triggers alerts.
    As per implementation plan section 6.4 and 7.2.
    """
    def __init__(self, height_thresholds: List[Dict] = None, length_thresholds: List[Dict] = None):
        # Sort thresholds by level so highest triggers last/overrides
        self.height_thresholds = sorted(height_thresholds or [], key=lambda x: x['level'])
        self.length_thresholds = sorted(length_thresholds or [], key=lambda x: x['level'])
        self.active_alerts = []

    def check_measurements(self, measurements: Dict) -> List[Dict]:
        """
        Checks a single object measurement against configured thresholds.
        Returns a list of triggered alerts.
        """
        triggered = []
        height = measurements.get('height_above_baseline_m', 0.0)
        length = measurements.get('length_m', 0.0)
        
        for threshold in self.height_thresholds:
            if height >= threshold['level']:
                alert = {
                    'name': threshold.get('name', 'Height'),
                    'level': threshold['level'],
                    'color': threshold['color'],
                    'action': threshold['action'],
                    'metric': 'height',
                    'measured': height,
                    'exceeded_by': height - threshold['level']
                }
                triggered.append(alert)

        for threshold in self.length_thresholds:
            if length >= threshold['level']:
                alert = {
                    'name': threshold.get('name', 'Length'),
                    'level': threshold['level'],
                    'color': threshold['color'],
                    'action': threshold['action'],
                    'metric': 'length',
                    'measured': length,
                    'exceeded_by': length - threshold['level']
                }
                triggered.append(alert)
                
        self.active_alerts = triggered
        return triggered

    def update_thresholds(self, height_thresholds: List[Dict], length_thresholds: List[Dict] = None):
        """Dynamically updates the monitoring thresholds."""
        self.height_thresholds = sorted(height_thresholds, key=lambda x: x['level'])
        self.length_thresholds = sorted(length_thresholds or [], key=lambda x: x['level'])

    def get_status_summary(self) -> str:
        """Returns a string summary of current alert status."""
        if not self.active_alerts:
            return "OK"
        
        # Return the highest triggered alert name
        return self.active_alerts[-1]['name']

    def summarize_alerts(self, alerts: List[Dict]) -> str:
        """Stores frame-wide alerts and returns the highest active status."""
        self.active_alerts = sorted(alerts, key=lambda x: x['level'])
        return self.get_status_summary()
