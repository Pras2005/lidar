import csv
import os
import time
from datetime import datetime
from typing import Dict, List

class MeasurementLogger:
    """
    Logs measurements to CSV files.
    As per implementation plan section 5B (Module 7).
    """
    def __init__(self, log_dir: str = 'logs'):
        self.log_dir = log_dir
        self.current_file = None
        self.fieldnames = [
            'timestamp', 'object_id', 'length_m', 'width_m', 'depth_m',
            'height_above_baseline_m', 'distance_m', 'centroid_x', 'centroid_y', 'point_count'
        ]
        
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def _get_new_filename(self) -> str:
        """Generates a log filename based on current date/time."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.log_dir, f"measurements_{timestamp}.csv")

    def log_measurements(self, measurements: List[Dict]):
        """
        Logs a list of measurements for a single scan.
        """
        if not measurements:
            return

        if self.current_file is None:
            self.current_file = self._get_new_filename()
            
        file_exists = os.path.isfile(self.current_file)
        
        with open(self.current_file, mode='a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            
            if not file_exists:
                writer.writeheader()
                
            timestamp = datetime.now().isoformat()
            
            for idx, m in enumerate(measurements):
                row = {
                    'timestamp': timestamp,
                    'object_id': idx,
                    'length_m': f"{m.get('length_m', 0.0):.4f}",
                    'width_m': f"{m.get('width_m', 0.0):.4f}",
                    'depth_m': f"{m.get('depth_m', 0.0):.4f}",
                    'height_above_baseline_m': f"{m.get('height_above_baseline_m', 0.0):.4f}",
                    'distance_m': f"{m.get('distance_m', 0.0):.4f}",
                    'centroid_x': f"{m.get('centroid', (0,0))[0]:.4f}",
                    'centroid_y': f"{m.get('centroid', (0,0))[1]:.4f}",
                    'point_count': m.get('point_count', 0)
                }
                writer.writerow(row)

    def rotate_log(self):
        """Forces the creation of a new log file."""
        self.current_file = self._get_new_filename()
