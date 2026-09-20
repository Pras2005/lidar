import numpy as np

# Point cloud data structure (matches SICK format)
SICK_POINT_DTYPE = np.dtype([
    ('x', '<f4'),  # X coordinate (float32)
    ('y', '<f4'),  # Y coordinate (float32)
    ('z', '<f4'),  # Z coordinate (float32, always 0 for 2D)
    ('i', '<f4')   # Intensity (float32)
])
