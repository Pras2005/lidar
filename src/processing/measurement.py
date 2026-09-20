import numpy as np
from scipy.spatial import ConvexHull
from typing import Dict, Tuple
from .units import UnitConverter

class MeasurementEngine:
    """
    Refined Engine for Phase 4: Length & Height Extraction.
    Optimized for precision and multi-method length detection.
    """
    def __init__(self, length_method='bbox', units='m'):
        self.length_method = length_method
        self.units = units

    def measure_object(
        self,
        object_points: np.ndarray,
        baseline_height: float = 0.0,
        baseline_axis: str = 'y',
    ) -> Dict:
        """
        Performs high-precision measurement of a detected object.
        """
        if len(object_points) == 0:
            return {}

        # 1. Advanced Length Measurement (Phase 4)
        if self.length_method == 'bbox':
            length_m, width_m, depth_m = self._measure_length_bbox(object_points)
        elif self.length_method == 'hull':
            length_m, width_m, depth_m = self._measure_length_hull(object_points)
        elif self.length_method == 'pca':
            length_m, width_m, depth_m = self._measure_length_pca(object_points)
        else:
            length_m, width_m, depth_m = self._measure_length_bbox(object_points)

        # 2. Height Measurement (Phase 5)
        # Assuming horizontal mounting where Y is distance/height reference.
        axis_values = object_points[baseline_axis]
        min_axis = float(np.min(axis_values))
        max_axis = float(np.max(axis_values))
        centroid_axis = float(np.mean(axis_values))
        baseline_side = 'positive_to_negative' if baseline_height >= centroid_axis else 'negative_to_positive'
        if baseline_height >= centroid_axis:
            height_m = max(0.0, baseline_height - min_axis)
            max_height_index = int(np.argmin(axis_values))
        else:
            height_m = max(0.0, max_axis - baseline_height)
            max_height_index = int(np.argmax(axis_values))

        # 3. Positional metadata used by logging and downstream consumers.
        centroid_x = float(np.mean(object_points['x']))
        centroid_y = float(np.mean(object_points['y']))
        centroid = (centroid_x, centroid_y)
        distance_m = float(np.linalg.norm([centroid_x, centroid_y]))

        # 4. Apply Unit Conversions (Phase 4.4)
        bounds = {
            'min_x': float(np.min(object_points['x'])),
            'max_x': float(np.max(object_points['x'])),
            'min_y': float(np.min(object_points['y'])),
            'max_y': float(np.max(object_points['y'])),
        }

        return {
            'length_m': float(length_m),
            'width_m': float(width_m),
            'depth_m': float(depth_m),
            'height_above_baseline_m': float(height_m),
            'distance_m': distance_m,
            'length': UnitConverter.convert(length_m, self.units),
            'width': UnitConverter.convert(width_m, self.units),
            'depth': UnitConverter.convert(depth_m, self.units),
            'height_above_baseline': UnitConverter.convert(height_m, self.units),
            'distance': UnitConverter.convert(distance_m, self.units),
            'units': self.units,
            'baseline_axis': baseline_axis,
            'baseline_value_m': float(baseline_height),
            'baseline_side': baseline_side,
            'centroid': centroid,
            'point_count': int(len(object_points)),
            'max_height_point': (
                float(object_points['x'][max_height_index]),
                float(object_points['y'][max_height_index]),
            ),
            'bounds': bounds,
        }

    def compare_length_methods(self, object_points: np.ndarray) -> Dict[str, float]:
        """Returns bbox/hull/pca length estimates in meters for comparison UI."""
        if len(object_points) == 0:
            return {'bbox_m': 0.0, 'hull_m': 0.0, 'pca_m': 0.0}

        bbox_length, _, _ = self._measure_length_bbox(object_points)
        hull_length, _, _ = self._measure_length_hull(object_points)
        pca_length, _, _ = self._measure_length_pca(object_points)
        return {
            'bbox_m': float(bbox_length),
            'hull_m': float(hull_length),
            'pca_m': float(pca_length),
        }

    def convert_length_comparison(self, comparison_m: Dict[str, float]) -> Dict[str, float]:
        return {
            'bbox': UnitConverter.convert(comparison_m.get('bbox_m', 0.0), self.units),
            'hull': UnitConverter.convert(comparison_m.get('hull_m', 0.0), self.units),
            'pca': UnitConverter.convert(comparison_m.get('pca_m', 0.0), self.units),
        }

    def _measure_length_bbox(self, points: np.ndarray) -> Tuple[float, float, float]:
        """Phase 4.1: Axis-aligned bounding box."""
        min_x, max_x = np.min(points['x']), np.max(points['x'])
        min_y, max_y = np.min(points['y']), np.max(points['y'])
        w, d = max_x - min_x, max_y - min_y
        return max(w, d), w, d

    def _measure_length_hull(self, points: np.ndarray) -> Tuple[float, float, float]:
        """Phase 4.2: Convex Hull diameter (Longest possible segment)."""
        if len(points) < 3: return self._measure_length_bbox(points)
        pts = np.column_stack((points['x'], points['y']))
        hull = ConvexHull(pts)
        h_pts = pts[hull.vertices]
        # Calculate all-pairs distance in hull (O(H^2) where H is small)
        dist_matrix = np.sqrt(np.sum((h_pts[:, None, :] - h_pts[None, :, :])**2, axis=-1))
        max_d = np.max(dist_matrix)
        return max_d, 0.0, 0.0

    def _measure_length_pca(self, points: np.ndarray) -> Tuple[float, float, float]:
        """Phase 4.3: PCA-based Oriented Bounding Box Length."""
        pts = np.column_stack((points['x'], points['y']))
        ca = pts - np.mean(pts, axis=0)
        cov = np.cov(ca.T)
        vals, vecs = np.linalg.eig(cov)
        order = np.argsort(vals)[::-1]
        # Project onto primary axis
        p1 = np.dot(ca, vecs[:, order[0]])
        length = np.max(p1) - np.min(p1)
        # Project onto secondary axis
        p2 = np.dot(ca, vecs[:, order[1]])
        width = np.max(p2) - np.min(p2)
        return length, width, 0.0
