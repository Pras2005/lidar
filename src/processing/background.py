import numpy as np
from scipy.spatial import cKDTree


class BackgroundSubtractor:
    """
    Removes static scene structure using a captured empty-scene reference scan.
    """
    def __init__(self, enabled=True, distance_tolerance=0.08):
        self.enabled = enabled
        self.distance_tolerance = distance_tolerance
        self.reference_points = None
        self._tree = None

    def capture(self, points):
        if points is None or len(points) == 0:
            return False

        self.reference_points = np.array(points, copy=True)
        xy = np.column_stack((self.reference_points['x'], self.reference_points['y']))
        self._tree = cKDTree(xy)
        return True

    def clear(self):
        self.reference_points = None
        self._tree = None

    def has_reference(self):
        return self.reference_points is not None and self._tree is not None

    def filter_foreground(self, points):
        foreground_points, _ = self.split_points(points)
        return foreground_points

    def split_points(self, points):
        if not self.enabled or not self.has_reference() or points is None or len(points) == 0:
            empty = points[:0] if points is not None else np.array([])
            return points, empty

        xy = np.column_stack((points['x'], points['y']))
        distances, _ = self._tree.query(xy, k=1)
        foreground_mask = distances > self.distance_tolerance
        return points[foreground_mask], points[~foreground_mask]
