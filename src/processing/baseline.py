import numpy as np

class BaselineCalibration:
    """
    Refined Baseline Manager for Phase 5.
    Features a 'Calibration Wizard' logic using multi-scan averaging.
    """
    def __init__(
        self,
        mode='auto',
        fixed_height=0.0,
        floor_percentile=15.0,
        floor_axis='y',
        selection_range=None,
    ):
        self.mode = mode
        self.baseline_height = fixed_height
        self.floor_percentile = floor_percentile
        self.floor_axis = floor_axis
        self.selection_range = selection_range
        self.calibration_buffer = [] # Buffer for Phase 5 averaging
        self.is_calibrated = mode == 'manual' and fixed_height > 0.0

    def auto_calibrate_floor(self, scan_data, num_scans=10):
        """
        Phase 5.1: Baseline Calibration Wizard.
        Accumulates 'num_scans' to find a stable floor reference.
        """
        floor_pts = self._extract_floor_points(scan_data, self.selection_range)
        if len(floor_pts) == 0:
            return self.baseline_height
        
        if len(floor_pts) > 10:
            avg_y = np.mean(floor_pts['y'])
            self.calibration_buffer.append(avg_y)
            
            # Phase 5.2: Finish calibration once buffer is full
            if len(self.calibration_buffer) >= num_scans:
                self.baseline_height = np.median(self.calibration_buffer)
                self.is_calibrated = True
                print(f"✅ Baseline Calibrated: {self.baseline_height:.3f}m")
                return self.baseline_height
                
        return self.baseline_height

    def calibrate_from_scan(self, scan_data, selection_range=None):
        """Calibrates baseline from the current scan immediately."""
        floor_pts = self._extract_floor_points(scan_data, selection_range)
        if len(floor_pts) == 0:
            return None

        axis_values = floor_pts[self.floor_axis]
        self.baseline_height = float(np.median(axis_values))
        self.selection_range = selection_range
        self.calibration_buffer = [self.baseline_height]
        self.is_calibrated = True
        self.mode = 'manual'
        return self.baseline_height

    def update_floor_percentile(self, floor_percentile):
        self.floor_percentile = float(floor_percentile)

    def update_floor_axis(self, floor_axis):
        self.floor_axis = floor_axis

    def set_selection_range(self, selection_range):
        self.selection_range = selection_range

    def reset(self):
        """Resets the calibration wizard."""
        self.calibration_buffer = []
        self.is_calibrated = False
        if self.mode != 'manual':
            self.baseline_height = 0.0

    def _extract_floor_points(self, scan_data, selection_range=None):
        if scan_data is None or len(scan_data) < 20:
            if scan_data is not None:
                return scan_data[:0]
            return np.array([])

        filtered_scan = scan_data
        selection_axis = 'x' if self.floor_axis == 'y' else 'y'
        if selection_range is not None:
            min_v, max_v = sorted((float(selection_range[0]), float(selection_range[1])))
            mask = (scan_data[selection_axis] >= min_v) & (scan_data[selection_axis] <= max_v)
            filtered_scan = scan_data[mask]
            if len(filtered_scan) < 5:
                return scan_data[:0]

        axis_values = filtered_scan[self.floor_axis]
        if self.floor_axis == 'y':
            threshold = np.percentile(axis_values, 100.0 - self.floor_percentile)
            return filtered_scan[axis_values >= threshold]

        abs_threshold = np.percentile(np.abs(axis_values), 100.0 - self.floor_percentile)
        return filtered_scan[np.abs(axis_values) >= abs_threshold]
