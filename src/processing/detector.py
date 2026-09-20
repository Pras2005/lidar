import numpy as np
from sklearn.cluster import DBSCAN
from typing import List, Dict

class ObjectDetector:
    """
    Groups raw points into distinct objects using clustering.
    As per implementation plan section 5B (Module 4).
    """
    def __init__(self, epsilon=0.1, min_samples=5, min_object_size=0.02, max_object_size=5.0):
        # epsilon: max distance between two points to be considered neighbors
        # min_samples: minimum points to form a cluster (object)
        self.epsilon = epsilon
        self.min_samples = min_samples
        self.min_object_size = min_object_size
        self.max_object_size = max_object_size
        self.clusterer = DBSCAN(eps=self.epsilon, min_samples=self.min_samples)

    def detect_objects(self, points: np.ndarray) -> List[np.ndarray]:
        """
        Takes a NumPy structured array of points and returns 
        a list of arrays, each containing points for one object.
        """
        if len(points) == 0:
            return []

        # Convert to 2D (x, y) for clustering
        points_2d = np.column_stack((points['x'], points['y']))
        
        # Fit clustering
        labels = self.clusterer.fit_predict(points_2d)
        
        # Extract unique objects (labels >= 0 are valid clusters)
        unique_labels = set(labels)
        if -1 in unique_labels:
            unique_labels.remove(-1) # -1 is noise
            
        objects = []
        for label in sorted(unique_labels):
            obj_points = points[labels == label]
            span_x = float(np.max(obj_points['x']) - np.min(obj_points['x']))
            span_y = float(np.max(obj_points['y']) - np.min(obj_points['y']))
            largest_span = max(span_x, span_y)

            if largest_span < self.min_object_size or largest_span > self.max_object_size:
                continue

            objects.append(obj_points)
            
        return objects

    def update_params(self, epsilon=None, min_samples=None, min_object_size=None, max_object_size=None):
        """Allows dynamic adjustment of detection sensitivity."""
        if epsilon is not None:
            self.epsilon = epsilon
        if min_samples is not None:
            self.min_samples = min_samples
        if min_object_size is not None:
            self.min_object_size = min_object_size
        if max_object_size is not None:
            self.max_object_size = max_object_size
        
        self.clusterer = DBSCAN(eps=self.epsilon, min_samples=self.min_samples)
