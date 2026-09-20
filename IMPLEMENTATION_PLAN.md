# TiM240-2050300 Complete Feature Implementation Plan

## Document Version: 1.0
## Date: 2026-03-20
## Device: SICK TiM240-2050300 2D LiDAR Sensor

---

## 1. DEVICE SPECIFICATIONS

### 1.1 Core Hardware Specifications
| Parameter | Specification | Notes |
|-----------|--------------|-------|
| **Part Number** | TiM240-2050300 (1104981) | |
| **Measurement Range** | 0.05m to 10m | Working range |
| **Field of View** | 240° (±120°) | Horizontal scan |
| **Angular Resolution** | 1° (0.0175 rad) | 241 measurement points |
| **Scanning Frequency** | 14.5 Hz | ~69ms per scan |
| **Response Time** | Typ. 70ms | Latency |
| **Measurement Technology** | HDDM+ (High Definition Distance Measurement Plus) | |
| **Light Source** | Infrared 850nm | |
| **Laser Class** | Class 1 (Eye-safe) | IEC 60825-1:2014 |

### 1.2 Accuracy & Performance
| Parameter | Value |
|-----------|-------|
| **Systematic Error** | ±40mm (typical) |
| **Statistical Error** | 30mm (typical) |
| **Remission Range** | 4% to 1,000% (reflectors) |
| **Scan Range at 10% Remission** | 2.8m to 3m (angle-dependent) |

### 1.3 Physical Characteristics
| Parameter | Value |
|-----------|-------|
| **Dimensions (H×D×W)** | 75.8mm × 79.7mm × 60mm |
| **Weight** | 150g |
| **Enclosure Rating** | IP65 (indoor use) |
| **Housing Color** | Light blue (RAL 5012) |
| **Mounting** | M3 threaded holes, max torque 0.7 Nm |

### 1.4 Electrical & Environmental
| Parameter | Value |
|-----------|-------|
| **Supply Voltage** | 10V DC to 28V DC |
| **Power Consumption** | 2.9W |
| **Output Current** | ≤100mA |
| **Operating Temperature** | -10°C to +50°C |
| **EMC** | IEC 61000-6-3:2006+AMD1:2010 / IEC 61000-6-2:2005 |
| **Vibration Resistance** | 10Hz-500Hz, 5g |
| **Shock Resistance** | 50g, 3ms |

### 1.5 Connectivity
| Interface | Details |
|-----------|---------|
| **Ethernet** | TCP/IP, 4-pin M12 female connector |
| **Power** | 5-pin M12 male connector |
| **Communication Protocols** | CoLa A (ASCII, Port 2112), CoLa B (Binary, Port 2111) |
| **Digital Outputs** | 1 Push-pull ("Device Ready") |
| **Digital Inputs** | 0 |
| **LEDs** | 2 (Green: Ready, Red: Error) |

---

## 2. DATA OUTPUT CAPABILITIES

### 2.1 Scan Data Structure
```
LMDscandata Telegram Format (CoLa B):
├── Header (STX markers)
├── Command (sRA LMDscandata)
├── Version number
├── Device number
├── Serial number
├── Device status
├── Telegram counter (increments per scan)
├── Scan counter
├── Time since startup (µs)
├── Time of transmission (µs)
├── Status of digital inputs
├── Status of digital outputs
├── Scan frequency (Hz × 100)
├── Measurement frequency (Hz × 100)
├── Number of encoders
├── Number of channels (typically 1)
├── Content (DIST1, DIST2, RSSI1, etc.)
├── Scale factor
├── Scale factor offset
├── Start angle (1/10000 degree)
├── Angular step width (1/10000 degree)
├── Number of data points (241 for TiM240)
├── Distance data array (16-bit values)
├── [Optional] Remission/Intensity data array (16-bit values)
├── Position data
├── Device name
├── Comment
└── Checksum/CRC
```

### 2.2 Available Data Fields
1. **Distance Measurements**: 241 points per scan (0-240° in 1° steps)
2. **Intensity/Remission Values**: 16-bit resolution (configurable)
3. **Timestamps**: Microsecond precision
4. **Scan Counter**: Unique ID per scan
5. **Device Status**: Operational state
6. **Digital I/O Status**: Input/output states

### 2.3 Point Cloud Format
Each measurement point contains:
- **X coordinate** (meters, float32)
- **Y coordinate** (meters, float32)  
- **Z coordinate** (always 0 for 2D, float32)
- **Intensity** (remission value, float32)

Conversion formulas:
```
angle = start_angle + (point_index × angular_step)
distance = distance_value × scale_factor + offset
x = distance × sin(angle)
y = distance × cos(angle)
z = 0.0 (2D sensor)
```

---

## 3. CoLa COMMAND SET

### 3.1 Device Information Commands
| Command | Function | Response Format |
|---------|----------|-----------------|
| `sRN DeviceIdent` | Get device identification | "sRA DeviceIdent {type} {version}" |
| `sRN SerialNumber` | Get serial number | "sRA SerialNumber {number}" |
| `sRN FirmwareVersion` | Get firmware version | "sRA FirmwareVersion {version}" |
| `sRN SCdevicestate` | Get device state | "sRA SCdevicestate {state}" |
| `sRN LocationName` | Get location name | "sRA LocationName {name}" |

### 3.2 Measurement Control Commands
| Command | Function | Response |
|---------|----------|----------|
| `sMN LMCstartmeas` | Start measurement | "sAN LMCstartmeas {status}" |
| `sMN LMCstopmeas` | Stop measurement | "sAN LMCstopmeas {status}" |
| `sMN Run` | Start device operation | "sAN Run {status}" |
| `sEN LMDscandata {mode}` | Enable/disable scan data stream (0=off, 1=on) | "sEA LMDscandata {mode}" |
| `sRN LMDscandata` | Request single scan | Returns full scan telegram |

### 3.3 Configuration Commands
| Command | Function | Parameters |
|---------|----------|------------|
| `sWN LMPoutputRange` | Set output angle range | {unit} {scan_freq} {angle_res} {start_angle} {stop_angle} |
| `sRN LMPoutputRange` | Read output range | Returns configured range |
| `sWN LMDscandatacfg` | Configure scan data content | {output_channel} {remission} {resolution} {unit} {encoder} {position} {device_name} {comment} {time} {output_rate} |
| `sRN LMDscandatacfg` | Read scan data config | Returns configuration |
| `sMN SetAccessMode` | Set access level | {level} {password} (Level 3, Password: F4724744) |
| `sWN EIHstCola` | Set protocol (0=CoLa-A, 1=CoLa-B) | {protocol} |

### 3.4 Diagnostic Commands
| Command | Function |
|---------|----------|
| `sRN ODoprh` | Operating hours counter |
| `sRN ODpwrc` | Power-on counter |
| `sRN STlms` | Device status |

---

## 4. ADVANCED FEATURES AVAILABLE

### 4.1 Data Filtering
- **Median Filter**: Smooths distance values over multiple scans
- **Mean Filter**: Averages measurements
- **Edge Filter**: Removes erroneous edge measurements
- **Distance Filter**: Min/max range filtering

### 4.2 Output Configuration
- **Selectable Output Channels**: Distance, remission, or both
- **Intensity Resolution**: 8-bit or 16-bit
- **Output Rate**: Can be reduced from 14.5 Hz
- **Angular Range Restriction**: Limit scan sector

### 4.3 Real-Time Processing
- **Field Evaluation**: On-device processing
- **Multi-Echo Support**: Detect multiple returns per beam
- **Timestamp Synchronization**: Precise timing

---

## 5. IMPLEMENTATION ARCHITECTURE

### 5.1 System Components

```
┌─────────────────────────────────────────────────────────────┐
│              YOUR CONTROL PANEL APPLICATION                 │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Live      │  │  Settings &  │  │   Data Export    │  │
│  │ Visualization│  │Configuration │  │   & Logging      │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │ (Data Flow)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         YOUR DATA PROCESSING LAYER (TO IMPLEMENT)           │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │    Object    │  │  Measurement │  │   Baseline &    │  │
│  │  Detection   │  │   Analysis   │  │   Threshold     │  │
│  └──────────────┘  └──────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │ Point Cloud Callback
                           │ (X, Y, Z, Intensity)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│   sick_scan_xd API (ALREADY IMPLEMENTED - NO WORK NEEDED)  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  SickScanApiRegisterCartesianPointCloudMsg()         │  │
│  │  - Point cloud generation (polar → Cartesian)        │  │
│  │  - CoLa A/B protocol handling                         │  │
│  │  - Telegram parsing & decoding                        │  │
│  │  - TCP/IP connection management                       │  │
│  │  - Auto-reconnect & error recovery                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │ (Ethernet TCP/IP)
                           ▼
                  ┌──────────────────┐
                  │   TiM240-2050300 │
                  │   LiDAR Sensor   │
                  └──────────────────┘
```

### 5.2 Core Modules TO IMPLEMENT

**Note**: Modules 1-3 are handled by `sick_scan_xd` library. You only need to implement Modules 4-8.

#### ~~Module 1: Connection Manager~~ ✅ PROVIDED BY sick_scan_xd
**Status**: Already implemented in sick_scan_xd library
**What it does**:
- TCP/IP connection to LiDAR
- Auto-reconnection on timeout
- Protocol detection (CoLa A/B)
- Connection health monitoring

#### ~~Module 2: Telegram Parser~~ ✅ PROVIDED BY sick_scan_xd
**Status**: Already implemented in sick_scan_xd library
**What it does**:
- Parse binary (CoLa B) and ASCII (CoLa A) formats
- Extract distance, intensity, timestamp data
- Validate checksums/CRC
- Handle variable telegram structures

#### ~~Module 3: Point Cloud Generator~~ ✅ PROVIDED BY sick_scan_xd
**Status**: Already implemented in sick_scan_xd library
**What it does**:
- Polar to Cartesian conversion
- Apply calibration offsets
- Filter invalid points
- Generate structured point cloud
- Delivers clean X, Y, Z, Intensity data via callback

---

## 5A. INTEGRATION WITH sick_scan_xd

### 5A.1 Why Use sick_scan_xd?

The `sick_scan_xd` library is a **production-ready, tested driver** for SICK LiDAR sensors that handles all the complex low-level communication. **You don't need to reinvent the wheel.**

**What sick_scan_xd provides:**
- ✅ Robust TCP/IP connection management with auto-reconnect
- ✅ Full CoLa A/B protocol implementation
- ✅ Telegram parsing with error checking
- ✅ Point cloud generation (polar → Cartesian)
- ✅ Multi-platform support (Linux, Windows)
- ✅ Extensive testing and debugging
- ✅ Regular updates and bug fixes

**What you focus on:**
- 🎯 Your application logic (object detection, measurement)
- 🎯 User interface design
- 🎯 Domain-specific features (baseline calibration, thresholds)

### 5A.2 How to Use sick_scan_xd API

**Basic Integration Pattern:**

```python
import sys
import os
import numpy as np
from collections import deque

# Add sick_scan_xd to Python path
REPO_BASE = os.path.expanduser("~/sick_scan_xd")
sys.path.insert(0, os.path.join(REPO_BASE, "python/api"))

from sick_scan_api import *

# Point cloud data structure (matches SICK format)
SICK_POINT_DTYPE = np.dtype([
    ('x', '<f4'),  # X coordinate (float32)
    ('y', '<f4'),  # Y coordinate (float32)
    ('z', '<f4'),  # Z coordinate (float32, always 0 for 2D)
    ('i', '<f4')   # Intensity (float32)
])

class TiM240Controller:
    def __init__(self, lidar_ip="192.168.2.111"):
        # 1. Load the library
        lib_path = os.path.join(REPO_BASE, "build")
        self.library = SickScanApiLoadLibrary(
            [lib_path], 
            "libsick_scan_xd_shared_lib.so"
        )
        
        # 2. Create API handle
        self.handle = SickScanApiCreate(self.library)
        
        # 3. Initialize with launch file
        launch_file = os.path.join(REPO_BASE, "launch/sick_tim_240.launch")
        cli_args = f"{launch_file} hostname:={lidar_ip}"
        result = SickScanApiInitByLaunchfile(self.library, self.handle, cli_args)
        
        if result != 0:
            raise RuntimeError(f"Failed to initialize: {result}")
        
        print(f"✓ Connected to TiM240 at {lidar_ip}")
    
    def cartesian_callback(self, api_handle, msg):
        """
        This callback is called by sick_scan_xd for every scan.
        You receive clean point cloud data here.
        """
        try:
            # Get number of points
            num_points = msg.contents.width * msg.contents.height
            if num_points == 0:
                return
            
            # Extract raw bytes (zero-copy method)
            raw_ptr = msg.contents.data.buffer
            data_size = msg.contents.data.size
            raw_bytes = bytes(raw_ptr[:data_size])
            
            # Parse into structured NumPy array
            points = np.frombuffer(raw_bytes, dtype=SICK_POINT_DTYPE, count=num_points)
            
            # Filter valid points
            mask = (np.abs(points['x']) > 0.01) | (np.abs(points['y']) > 0.01)
            valid_points = points[mask]
            
            # Now YOU process this data:
            # - Cluster into objects
            # - Measure length/height
            # - Check thresholds
            # - Update UI
            
            self.process_point_cloud(valid_points)
            
        except Exception as e:
            print(f"Callback error: {e}")
    
    def process_point_cloud(self, points):
        """
        YOUR APPLICATION LOGIC GOES HERE
        
        You receive:
        - points['x']: X coordinates (numpy array)
        - points['y']: Y coordinates (numpy array)
        - points['z']: Z coordinates (always 0 for TiM240)
        - points['i']: Intensity values
        """
        x = points['x']
        y = points['y']
        intensity = points['i']
        
        # YOUR CODE:
        # 1. Detect objects
        # 2. Measure dimensions
        # 3. Check against baseline/thresholds
        # 4. Update UI
        pass
    
    def start(self):
        """Start receiving scan data"""
        # Register your callback
        self.callback_wrapper = SickScanPointCloudMsgCallback(self.cartesian_callback)
        SickScanApiRegisterCartesianPointCloudMsg(
            self.library,
            self.handle,
            self.callback_wrapper
        )
        print("✓ Scanning started - receiving point clouds")
    
    def stop(self):
        """Clean shutdown"""
        SickScanApiClose(self.library, self.handle)
        SickScanApiRelease(self.library, self.handle)
        print("✓ Disconnected")

# Usage:
if __name__ == "__main__":
    controller = TiM240Controller("192.168.2.111")
    controller.start()
    
    # Your main loop (UI event loop, etc.)
    # The callback will be called automatically for each scan
    
    # When done:
    # controller.stop()
```

### 5A.3 Key API Functions You'll Use

| Function | Purpose | When to Call |
|----------|---------|-------------|
| `SickScanApiLoadLibrary()` | Load the sick_scan_xd library | Once at startup |
| `SickScanApiCreate()` | Create API handle | Once at startup |
| `SickScanApiInitByLaunchfile()` | Connect to LiDAR | Once at startup |
| `SickScanApiRegisterCartesianPointCloudMsg()` | Register your callback | Once after init |
| `SickScanApiClose()` | Stop scanning | At shutdown |
| `SickScanApiRelease()` | Release resources | At shutdown |

### 5A.4 Data You Receive in Callback

Every ~70ms (14.5 Hz), your callback receives:

```python
points = numpy array with shape (N, 4)
         where N ≈ 200-241 (valid points)

points['x']  # X coordinates in meters (float32)
points['y']  # Y coordinates in meters (float32)
points['z']  # Z coordinates (always 0.0 for 2D)
points['i']  # Intensity/remission (float32, 0-1 or 0-65535 depending on config)
```

**Coordinate System:**
```
      Y (distance from sensor)
      ↑
      │
      │     ● ● ● (detected points)
      │   ● ● ● ●
      │ ● ● ● ● ●
      │
      └──────────────→ X (left/right)
    (0,0)
  Sensor position
```

---

## 5B. MODULES YOU NEED TO IMPLEMENT


**Purpose**: Detect and classify objects from point cloud
**Features**:
- Clustering algorithms (DBSCAN, etc.)
- Object size/shape analysis
- Object tracking over time
- Classification (person, forklift, etc.)

#### Module 5: Measurement Analysis
**Purpose**: Extract measurements and statistics
**Features**:
- **Object length detection** (YOUR PRIMARY REQUIREMENT)
- **Height detection above baseline** (YOUR PRIMARY REQUIREMENT)
- Distance calculations
- Area/volume estimation
- Statistical analysis

#### Module 6: Configuration Manager
**Purpose**: Application configuration and parameter management
**Features**:
- ~~Send CoLa commands~~ (sick_scan_xd handles this via launch files)
- Store/restore application configurations
- Threshold management
- Calibration data storage
- User preferences

**Note**: Device-level configuration (scan range, frequency, etc.) is handled by sick_scan_xd through launch files. You only need to manage application-level settings.

#### Module 7: Data Logger
**Purpose**: Record and export data
**Features**:
- CSV export
- Real-time logging
- Timestamp synchronization
- Event recording

#### Module 8: Alert System
**Purpose**: Threshold-based alerts
**Features**:
- Configurable thresholds
- Multi-level alerts
- External device integration (ESP32, etc.)
- Visual/audio notifications

---

## 6. PANEL FEATURES SPECIFICATION

### 6.1 Main Dashboard

**Live Visualization Panel**
- Real-time 2D point cloud display
- Object highlighting with bounding boxes
- Measurement overlays
- Distance grid
- Scan rate indicator
- Connection status

**Measurement Display**
- Object length (configurable units: mm, cm, m)
- Height above baseline (with threshold indicator)
- Distance to object
- Object count
- Scan statistics

**Status Indicators**
- LiDAR connection (green/red)
- Scan rate (Hz)
- Point count
- Error messages
- Temperature (if available)

### 6.2 Configuration Panel

**Connection Settings**
- IP address configuration
- Port selection (2111/2112)
- Protocol (CoLa A/B)
- Auto-reconnect toggle
- Timeout settings

**Scan Parameters**
- Angular range (start/stop angle)
- Angular resolution
- Scan frequency
- Output rate
- Data content (distance/intensity/both)

**Baseline Configuration** (YOUR KEY REQUIREMENT)
- **Baseline height setting** (reference ground level)
- **Height threshold** (trigger level above baseline)
- **Length measurement mode**:
  - Single object
  - Multi-object
  - Continuous monitoring
- **Measurement units** (mm, cm, m, inch, ft)

**Filters**
- Distance range (min/max)
- Intensity threshold
- Median/mean filter settings
- Edge filter parameters
- Object size filter (min/max)

### 6.3 Object Detection Panel

**Detection Settings**
- Clustering algorithm selection
- Clustering radius (epsilon)
- Minimum points per object
- Object classification rules
- Tracking parameters

**Length Measurement Configuration**
- Measurement method:
  - Bounding box (max dimension)
  - Convex hull (perimeter)
  - End-to-end distance
  - Fitted line/curve
- Multi-object handling
- Noise filtering

**Height Detection Configuration** (YOUR KEY REQUIREMENT)
- Baseline reference mode:
  - Fixed height
  - Auto-calibrate from floor
  - Manual calibration
- Height threshold levels:
  - Warning threshold
  - Critical threshold
  - Custom thresholds (multiple)
- Measurement zone definition

### 6.4 Alert Configuration Panel

**Threshold Settings**
- Length thresholds (min/max)
- Height thresholds (above baseline)
- Distance thresholds
- Count thresholds

**Alert Actions**
- Visual alerts (color codes, flashing)
- Audio alerts (beep patterns)
- External device triggers (ESP32, relay)
- Log events
- Email/SMS notifications (if configured)

**Alert Zones**
- Define multiple zones
- Per-zone thresholds
- Zone-specific actions

### 6.5 Data Logging Panel

**Recording Options**
- Start/stop recording
- Auto-record on trigger
- Recording duration
- File format (CSV, JSON, binary)
- Compression

**Export Options**
- Export scan data
- Export measurements
- Export point clouds
- Export statistics
- Time range selection

**Playback**
- Load recorded data
- Timeline scrubber
- Frame-by-frame analysis
- Measurement replay

### 6.6 Calibration Panel

**Baseline Calibration**
- Auto-detect floor level
- Manual baseline entry
- Multi-point calibration
- Tilt compensation
- Calibration wizard

**Distance Calibration**
- Known distance reference
- Multi-point calibration
- Scale factor adjustment
- Offset correction

**Angle Calibration**
- Zero-angle reference
- Angular offset
- Mounting angle compensation

### 6.7 Diagnostics Panel

**Device Information**
- Model number
- Serial number
- Firmware version
- Operating hours
- Power cycles

**Performance Metrics**
- Scan rate (actual vs configured)
- Point rate
- Data throughput
- Latency measurements
- Dropped scans

**Error Log**
- Connection errors
- Timeout events
- Invalid data
- Calibration warnings
- System messages

---

## 7. CORE FUNCTIONALITY: LENGTH & HEIGHT DETECTION

### 7.1 Object Length Detection

**Method 1: Bounding Box**
```python
def measure_length_bbox(object_points):
    # Find min/max X and Y
    min_x, max_x = np.min(object_points[:, 0]), np.max(object_points[:, 0])
    min_y, max_y = np.min(object_points[:, 1]), np.max(object_points[:, 1])
    
    # Calculate dimensions
    width = max_x - min_x
    depth = max_y - min_y
    
    # Length is maximum dimension
    length = max(width, depth)
    
    return length, width, depth
```

**Method 2: Convex Hull Perimeter**
```python
from scipy.spatial import ConvexHull

def measure_length_hull(object_points):
    hull = ConvexHull(object_points)
    perimeter = hull.area  # 2D perimeter
    
    # Find longest edge
    max_edge = 0
    vertices = object_points[hull.vertices]
    for i in range(len(vertices)):
        j = (i + 1) % len(vertices)
        edge_length = np.linalg.norm(vertices[i] - vertices[j])
        max_edge = max(max_edge, edge_length)
    
    return max_edge, perimeter
```

**Method 3: Principal Component Analysis**
```python
def measure_length_pca(object_points):
    # Center points
    centered = object_points - np.mean(object_points, axis=0)
    
    # PCA to find principal axis
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eig(cov)
    
    # Project onto principal axis
    principal_axis = eigenvectors[:, np.argmax(eigenvalues)]
    projections = np.dot(centered, principal_axis)
    
    # Length is range of projections
    length = np.max(projections) - np.min(projections)
    
    return length, principal_axis
```

### 7.2 Height Detection Above Baseline

**Baseline Establishment**
```python
class BaselineCalibration:
    def __init__(self):
        self.baseline_height = 0.0
        self.baseline_points = []
    
    def auto_calibrate_floor(self, scan_data):
        # Find lowest points (floor detection)
        # Assume floor is the densest low cluster
        
        # Filter points in bottom 20% of scan
        y_values = scan_data[:, 1]
        threshold = np.percentile(y_values, 20)
        floor_candidates = scan_data[y_values <= threshold]
        
        # Cluster floor points
        clusterer = DBSCAN(eps=0.05, min_samples=10)
        labels = clusterer.fit_predict(floor_candidates)
        
        # Find largest cluster (floor)
        unique, counts = np.unique(labels[labels >= 0], return_counts=True)
        floor_label = unique[np.argmax(counts)]
        
        floor_points = floor_candidates[labels == floor_label]
        self.baseline_height = np.mean(floor_points[:, 1])
        self.baseline_points = floor_points
        
        return self.baseline_height
    
    def set_manual_baseline(self, height_meters):
        self.baseline_height = height_meters
```

**Height Measurement**
```python
def measure_height_above_baseline(object_points, baseline_height):
    # Get minimum Y (closest to sensor)
    min_y = np.min(object_points[:, 1])
    
    # Height above baseline
    height = baseline_height - min_y
    
    # Get maximum height point
    max_height_point = object_points[np.argmin(object_points[:, 1])]
    
    return height, max_height_point
```

**Threshold Checking**
```python
class HeightThresholdMonitor:
    def __init__(self, baseline, thresholds):
        self.baseline = baseline
        self.thresholds = thresholds  # List of (level, action) tuples
    
    def check_thresholds(self, measured_height):
        triggered = []
        
        for threshold_level, action in self.thresholds:
            if measured_height > threshold_level:
                triggered.append({
                    'level': threshold_level,
                    'action': action,
                    'exceeded_by': measured_height - threshold_level
                })
        
        return triggered
```

### 7.3 Combined Length & Height Detection Pipeline

```python
class ObjectMeasurement:
    def __init__(self, baseline_calibration, length_method='bbox'):
        self.baseline = baseline_calibration
        self.length_method = length_method
    
    def measure_object(self, object_points):
        # Length measurement
        if self.length_method == 'bbox':
            length, width, depth = measure_length_bbox(object_points)
        elif self.length_method == 'hull':
            length, perimeter = measure_length_hull(object_points)
            width, depth = None, None
        elif self.length_method == 'pca':
            length, principal_axis = measure_length_pca(object_points)
            width, depth = None, None
        
        # Height measurement
        height, max_point = measure_height_above_baseline(
            object_points, 
            self.baseline.baseline_height
        )
        
        # Centroid
        centroid = np.mean(object_points, axis=0)
        
        # Distance from sensor
        distance = np.linalg.norm(centroid)
        
        return {
            'length': length,
            'width': width,
            'depth': depth,
            'height_above_baseline': height,
            'centroid': centroid,
            'distance': distance,
            'point_count': len(object_points),
            'max_height_point': max_point
        }
```

---

## 8. USER INTERFACE MOCKUP

```
╔═══════════════════════════════════════════════════════════════════════════╗
║  TiM240-2050300 CONTROL PANEL                     [≡] Settings [●] LIVE  ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  ┌──────────────────────────────────┐  ┌──────────────────────────────┐  ║
║  │      LIVE POINT CLOUD            │  │   MEASUREMENTS               │  ║
║  │                                  │  │                              │  ║
║  │         Y▲                       │  │  Object #1                   │  ║
║  │          │    ● ● ●             │  │  ├─ Length: 1.25 m           │  ║
║  │  ← ─────●─●─●─●─●──────→ X      │  │  ├─ Width:  0.65 m           │  ║
║  │          ●   ● ●                 │  │  ├─ Height: 0.12 m ⚠️        │  ║
║  │          │                       │  │  ├─ Distance: 2.3 m          │  ║
║  │                                  │  │  └─ Points: 45               │  ║
║  │  [━━━━━━━━━━━━━━━━━━━━━━]       │  │                              │  ║
║  │   0m    1m    2m    3m    4m     │  │  BASELINE: 0.00 m            │  ║
║  │                                  │  │  THRESHOLD: 0.10 m           │  ║
║  └──────────────────────────────────┘  └──────────────────────────────┘  ║
║                                                                            ║
║  ┌──────────────────────────────────────────────────────────────────────┐ ║
║  │  STATUS BAR                                                          │ ║
║  │  ● Connected | IP: 192.168.2.111:2111 | Scan: 14.5 Hz | Points: 241│ ║
║  └──────────────────────────────────────────────────────────────────────┘ ║
║                                                                            ║
║  [Baseline Calibration] [Length Settings] [Height Thresholds] [Export]   ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

---

## 9. IMPLEMENTATION PHASES

### Phase 1: sick_scan_xd Integration (Week 1)
**Focus**: Get the existing library working and understand the data callback
- [x] Install and compile sick_scan_xd library
- [x] Establish TCP/IP connection to LiDAR (using sick_scan_xd API)
- [x] Register point cloud callback
- [ ] Test data reception and parsing
- [ ] Verify point cloud coordinate system
- [ ] Document callback data structure
- [ ] Create wrapper class for sick_scan_xd API

**Deliverable**: Working connection that receives point cloud data in callback

### Phase 2: Basic Visualization (Week 2)
- [ ] 2D point cloud display
- [ ] Real-time updates
- [ ] Zoom/pan controls
- [ ] Grid overlay
- [ ] Status indicators

### Phase 3: Object Detection (Week 3)
- [ ] DBSCAN clustering
- [ ] Bounding box calculation
- [ ] Object labeling
- [ ] Multi-object tracking
- [ ] Noise filtering

### Phase 4: Length Measurement (Week 4) - YOUR PRIORITY
- [ ] Bounding box length
- [ ] Convex hull length
- [ ] PCA-based length
- [ ] Unit conversion
- [ ] Measurement display

### Phase 5: Height & Baseline (Week 5) - YOUR PRIORITY
- [ ] Baseline calibration wizard
- [ ] Auto floor detection
- [ ] Height measurement
- [ ] Threshold configuration
- [ ] Alert system

### Phase 6: UI Polish (Week 6)
- [ ] Settings panels
- [ ] Configuration save/load
- [ ] Data export
- [ ] Help system
- [ ] User preferences

### Phase 7: Advanced Features (Week 7-8)
- [ ] Data logging
- [ ] Playback mode
- [ ] Multiple threshold zones
- [ ] ESP32 integration
- [ ] Statistics dashboard

### Phase 8: Testing & Documentation (Week 9-10)
- [ ] Accuracy testing
- [ ] Performance optimization
- [ ] User manual
- [ ] API documentation
- [ ] Deployment package

---

## 10. TECHNICAL REQUIREMENTS

### 10.1 Software Dependencies

**Core Dependency (REQUIRED)**:
```
sick_scan_xd
└── Handles all LiDAR communication
    ├── CoLa A/B protocol
    ├── TCP/IP connection
    ├── Telegram parsing
    └── Point cloud generation
```

**Your Application Dependencies**:
```
Python 3.8+
├── numpy (point cloud processing, clustering)
├── matplotlib (visualization)
├── scipy (convex hull, spatial analysis)
├── scikit-learn (DBSCAN clustering)
├── PyQt5 or tkinter (GUI framework)
└── requests (optional: HTTP for ESP32 integration)
```

**Installation**:
```bash
# Install sick_scan_xd (already done)
cd ~/sick_scan_xd/build
cmake -DROS_VERSION=0 ..
make -j$(nproc)

# Install Python dependencies
pip install numpy matplotlib scipy scikit-learn PyQt5 requests --break-system-packages
```

### 10.2 Hardware Requirements
- CPU: Multi-core recommended (real-time processing)
- RAM: 4GB minimum, 8GB recommended
- Network: Gigabit Ethernet adapter
- Display: 1920×1080 minimum resolution

### 10.3 Operating Systems
- Linux (Ubuntu 22.04+, Fedora 38+)
- Windows 10/11
- macOS 12+ (limited testing)

---

## 11. DATA FLOW DIAGRAM

```
┌──────────────┐
│  TiM240-2050300 │
│    LiDAR Sensor │
└────────┬─────────┘
         │ Ethernet (TCP/IP Port 2111/2112)
         │ Raw CoLa telegrams @ 14.5 Hz
         ▼
╔═════════════════════════════════════════════════════════════╗
║          sick_scan_xd Library (ALREADY IMPLEMENTED)         ║
║  ┌────────────────────────────────────────────────────┐    ║
║  │ TCP Connection + CoLa Protocol + Telegram Parser   │    ║
║  │ - Handles all low-level communication              │    ║
║  │ - Converts polar to Cartesian coordinates          │    ║
║  │ - Filters invalid measurements                     │    ║
║  └────────────────────────────────────────────────────┘    ║
╚═════════════════════════════════════════════════════════════╝
         │ Clean Point Cloud Data via Callback
         │ cartesian_callback(X, Y, Z, Intensity)
         │ 241 points × (x, y, z, intensity)
         ▼
┌─────────────────────────────────────────────────────────────┐
│   YOUR APPLICATION - Data Processing Pipeline               │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Data Reception Layer (YOUR CODE)                   │  │
│   │  - Receive point cloud from callback                │  │
│   │  - Queue management                                 │  │
│   │  - Filter noise/outliers                            │  │
│   └────────┬────────────────────────────────────────────┘  │
│            │ Filtered Point Cloud                           │
│            ▼                                                 │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Object Detection Engine (YOUR CODE)                │  │
│   │  - DBSCAN clustering                                │  │
│   │  - Identify distinct objects                        │  │
│   │  - Track objects over time                          │  │
│   └────────┬────────────────────────────────────────────┘  │
│            │ Detected Objects (grouped point clouds)        │
│            ├────────────────┬────────────────┐              │
│            ▼                ▼                ▼              │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│   │  Baseline    │  │  Measurement │  │ Visualization│    │
│   │ Calibration  │  │   Engine     │  │   Display    │    │
│   │              │  │              │  │              │    │
│   │ - Auto floor │  │ - Length calc│  │ - Live view  │    │
│   │   detection  │  │ - Height calc│  │ - Overlays   │    │
│   │ - Manual set │  │ - Statistics │  │ - Graphs     │    │
│   └──────┬───────┘  └──────┬───────┘  └──────────────┘    │
│          │                  │                               │
│          └──────────┬───────┘                               │
│                     │ Measurements + Baseline               │
│                     ▼                                        │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  Threshold Monitor & Alert System (YOUR CODE)       │  │
│   │  - Compare against thresholds                       │  │
│   │  - Generate alerts                                  │  │
│   │  - Trigger actions (ESP32, logging, etc.)           │  │
│   └────────┬────────────────────────────────────────────┘  │
│            │ Alerts & Actions                               │
│            ├────────────────┬────────────────┐              │
│            ▼                ▼                ▼              │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│   │  Data Logger │  │  UI Updates  │  │  ESP32/GPIO  │    │
│   │  (CSV/JSON)  │  │  (Qt/Tk)     │  │  (Alerts)    │    │
│   └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

**Key Points**:
- **sick_scan_xd handles**: TCP/IP, CoLa protocol, telegram parsing, point cloud generation
- **Your code handles**: Object detection, measurement, baseline calibration, UI, alerts
- **Data flow**: Raw telegrams → sick_scan_xd → Clean point cloud → Your processing → UI/Alerts

---

## 12. CONFIGURATION FILE STRUCTURE

```yaml
# config.yaml
lidar:
  ip: "192.168.2.111"
  port: 2111
  protocol: "cola_b"  # cola_a or cola_b
  auto_reconnect: true
  timeout_ms: 5000

scan:
  angle_start: -120  # degrees
  angle_end: 120
  angular_resolution: 1.0
  scan_frequency: 14.5
  enable_intensity: true

baseline:
  mode: "auto"  # auto, manual, multi_point
  height_m: 0.0
  calibration_points: []
  auto_recalibrate_interval: 3600  # seconds

measurement:
  length:
    method: "bbox"  # bbox, hull, pca
    units: "m"  # m, cm, mm, inch, ft
    filter_min: 0.02
    filter_max: 10.0
  
  height:
    units: "m"
    thresholds:
      - level: 0.10
        name: "Warning"
        color: "#FFA500"
        action: "log"
      - level: 0.20
        name: "Critical"
        color: "#FF0000"
        action: "alert_esp32"

object_detection:
  algorithm: "dbscan"
  epsilon: 0.05
  min_samples: 5
  min_object_size: 0.02
  max_object_size: 5.0
  tracking_enabled: true

filters:
  distance_min: 0.05
  distance_max: 10.0
  intensity_min: 0
  median_filter_window: 3
  edge_filter_enabled: true

display:
  refresh_rate: 30  # Hz
  point_size: 2
  grid_spacing: 0.5
  show_baseline: true
  show_thresholds: true
  color_scheme: "viridis"

logging:
  enabled: true
  path: "./logs/"
  format: "csv"
  max_file_size_mb: 100
  auto_rotate: true

alerts:
  esp32:
    enabled: false
    ip: "192.168.1.100"
    port: 80
  
  audio:
    enabled: true
    volume: 0.5
  
  visual:
    flash_on_alert: true
    status_bar: true

export:
  default_format: "csv"
  include_intensity: true
  include_timestamps: true
  compression: false
```

---

## 13. API STRUCTURE

```python
# Main API Interface

class TiM240Controller:
    """Main controller for TiM240-2050300 LiDAR"""
    
    def __init__(self, config_file=None):
        """Initialize controller with optional config file"""
        pass
    
    def connect(self, ip, port=2111) -> bool:
        """Connect to LiDAR"""
        pass
    
    def disconnect(self):
        """Disconnect from LiDAR"""
        pass
    
    def start_scanning(self) -> bool:
        """Start continuous scanning"""
        pass
    
    def stop_scanning(self) -> bool:
        """Stop scanning"""
        pass
    
    def get_single_scan(self) -> ScanData:
        """Request single scan"""
        pass
    
    def get_point_cloud(self) -> np.ndarray:
        """Get latest point cloud (N×3 array: X, Y, Intensity)"""
        pass
    
    def get_device_info(self) -> dict:
        """Get device information"""
        pass


class BaselineCalibration:
    """Baseline/floor calibration manager"""
    
    def auto_calibrate(self, scan_data) -> float:
        """Auto-detect floor and set baseline"""
        pass
    
    def set_manual_baseline(self, height_m):
        """Manually set baseline height"""
        pass
    
    def get_baseline(self) -> float:
        """Get current baseline height"""
        pass


class ObjectDetector:
    """Object detection and clustering"""
    
    def detect_objects(self, point_cloud) -> List[Object]:
        """Detect objects in point cloud"""
        pass
    
    def configure(self, epsilon, min_samples, min_size, max_size):
        """Configure detection parameters"""
        pass


class MeasurementEngine:
    """Length and height measurement"""
    
    def measure_length(self, object_points, method='bbox') -> float:
        """Measure object length"""
        pass
    
    def measure_height(self, object_points, baseline) -> float:
        """Measure height above baseline"""
        pass
    
    def get_full_measurement(self, object_points, baseline) -> dict:
        """Get complete measurement data"""
        pass


class ThresholdMonitor:
    """Threshold monitoring and alerts"""
    
    def add_threshold(self, level, name, action):
        """Add new threshold"""
        pass
    
    def check_measurements(self, measurements) -> List[Alert]:
        """Check measurements against thresholds"""
        pass
    
    def trigger_alert(self, alert):
        """Execute alert action"""
        pass


class DataLogger:
    """Data logging and export"""
    
    def start_logging(self, filename):
        """Start logging to file"""
        pass
    
    def stop_logging(self):
        """Stop logging"""
        pass
    
    def export_data(self, start_time, end_time, format='csv'):
        """Export data range"""
        pass
```

---

## 14. NEXT STEPS

1. **Review this implementation plan** with stakeholders
2. **Prioritize features** based on your immediate needs
3. **Set up development environment**
4. **Begin Phase 1** (Core Communication)
5. **Schedule weekly reviews** to track progress

---

## NOTES & RECOMMENDATIONS

### Summary: What sick_scan_xd Does vs What You Build

**✅ sick_scan_xd Library (Already Done - Don't Touch):**
- TCP/IP connection management
- CoLa A/B protocol handling  
- Telegram parsing and decoding
- Point cloud generation (polar → Cartesian)
- Error recovery and reconnection
- Device initialization

**🔨 Your Application Code (What You Build):**
- Object detection (DBSCAN clustering)
- Length measurement (bounding box/convex hull/PCA)
- Height above baseline calculation
- Baseline calibration (auto floor detection)
- Threshold monitoring and alerts
- User interface (Qt/Tkinter)
- Data logging and export
- Configuration management
- ESP32/external device integration

### For Your Specific Use Case (Object Length & Height Detection):

**✓ Recommended Development Path:**
1. **Week 1**: Get sick_scan_xd integration working, verify point cloud data reception
2. **Week 2**: Implement basic visualization (matplotlib 2D scatter plot)
3. **Week 3**: Add DBSCAN clustering for object detection
4. **Week 4**: Implement length measurement (start with bounding box method)
5. **Week 5**: Implement baseline calibration and height measurement
6. **Week 6**: Add threshold monitoring and alert system
7. **Week 7-8**: Build proper UI with Qt/Tkinter
8. **Week 9-10**: Polish, testing, documentation

**⚠ Important Considerations:**
- **2D Limitation**: TiM240 only sees a single horizontal plane. For true height measurement, you need to mount at a known height and measure objects passing through the scan plane.
- **Baseline Calibration**: Critical for accurate height measurement. Auto-calibration on startup is recommended.
- **Object Orientation**: Length measurement accuracy depends on object orientation relative to sensor.
- **Coordinate System**: sick_scan_xd delivers points in Cartesian coordinates with origin at sensor position.

**💡 Quick Start Code Template:**

```python
# Minimal working example combining sick_scan_xd + your processing

from sick_scan_api import *
import numpy as np
from sklearn.cluster import DBSCAN

class MeasurementSystem:
    def __init__(self):
        # Initialize sick_scan_xd
        self.library = SickScanApiLoadLibrary([lib_path], "libsick_scan_xd_shared_lib.so")
        self.handle = SickScanApiCreate(self.library)
        SickScanApiInitByLaunchfile(self.library, self.handle, cli_args)
        
        # Your processing components
        self.clusterer = DBSCAN(eps=0.1, min_samples=5)
        self.baseline_height = 0.0
        
    def callback(self, api_handle, msg):
        # Extract point cloud
        points = self.extract_points(msg)  # sick_scan_xd gives you this
        
        # YOUR CODE STARTS HERE:
        # 1. Cluster objects
        objects = self.detect_objects(points)
        
        # 2. Measure each object
        for obj in objects:
            length = self.measure_length(obj)
            height = self.measure_height(obj, self.baseline_height)
            
            # 3. Check thresholds
            if height > threshold:
                self.trigger_alert()
        
    def start(self):
        # Register callback and start
        cb = SickScanPointCloudMsgCallback(self.callback)
        SickScanApiRegisterCartesianPointCloudMsg(self.library, self.handle, cb)
```

### Suggested Libraries & Tools:

**Core Processing:**
- `numpy`: Point cloud manipulation
- `scikit-learn`: DBSCAN clustering
- `scipy`: Convex hull, spatial calculations

**Visualization:**
- `matplotlib`: Quick prototyping, real-time plots
- `PyQt5` or `PySide6`: Production UI (recommended)
- `tkinter`: Lightweight alternative

**Data Management:**
- `pandas`: Data logging, CSV export
- `PyYAML`: Configuration files
- `h5py`: High-performance binary storage (optional)

**Testing:**
- `pytest`: Unit tests
- `numpy.testing`: Numerical accuracy tests

### File Doesn't Require LD_LIBRARY_PATH Fix:

Add to your shell startup file to avoid typing it every time:
```bash
echo 'export LD_LIBRARY_PATH=~/sick_scan_xd/build:$LD_LIBRARY_PATH' >> ~/.zshrc
source ~/.zshrc
```

---

**END OF IMPLEMENTATION PLAN**
