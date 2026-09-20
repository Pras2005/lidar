# SICK TiM240-2050300 LiDAR Control Panel

A production-ready Python application for real-time object detection, length measurement, and height monitoring using the SICK TiM240-2050300 2D LiDAR.

## 🚀 Key Features
- **Real-time Processing**: Full 14.5 Hz scan loop with background processing.
- **Object Detection**: DBSCAN clustering to isolate multiple objects in the field of view.
- **Dual-Axis Measurement**: Precise length (Bounding Box, Hull, or PCA) and height-above-baseline detection.
- **Baseline Wizard**: Intelligent multi-scan floor calibration to filter sensor noise.
- **Visual Dashboard**: High-performance PyQt5/Matplotlib interface.
- **Industrial Alerts**: Threshold-based logic with local visual cues and direct Raspberry Pi GPIO buzzer support.
- **Data Logging**: Automatic CSV recording of all measurements for audit and analysis.
- **Robustness**: Background Watchdog thread for automatic LiDAR reconnection.

## 🏗 Project Structure
```
gemlidar/
├── config.yaml              # Global application settings
├── src/
│   ├── main.py              # Logic Orchestrator
│   ├── gui_main.py          # Dashboard Entry Point
│   ├── lidar/               # Driver & Communication
│   ├── processing/          # Measurement & Clustering Brains
│   ├── ui/                  # Dashboard & Control Panel
│   ├── alerts/              # Thresholds & Physical Alert Outputs
│   └── logging/             # CSV Data Recording
└── tests/                   # Logic Validation Suite
```

## 🛠 Setup Instructions

### 1. Prerequisites
- **Ubuntu 20.04+** or **Raspberry Pi OS**
- **Python 3.8+**
- **sick_scan_xd** installed in one of these ways:
  - `lidar.sdk_path` set in `config.yaml`
  - `SICK_SCAN_XD_PATH` set in the environment
  - default install at `~/sick_scan_xd`
  - system install at `/opt/sick_scan_xd`

### 2. Install Dependencies
Full install with GUI:
```bash
pip install -r requirements.txt
```

Raspberry Pi headless install:
```bash
pip install -r requirements-headless.txt
```

### 3. LiDAR Configuration
Ensure your LiDAR is on the same network as your PC. Default IP is usually `192.168.2.111`.
Update `config.yaml` or use the **Configuration Tab** in the UI.

If `sick_scan_xd` is not in a default location, also set:
```yaml
lidar:
  sdk_path: /absolute/path/to/sick_scan_xd
  launch_file: /absolute/path/to/sick_scan_xd/launch/sick_tim_240.launch
```

Or set:
```bash
export SICK_SCAN_XD_PATH=/absolute/path/to/sick_scan_xd
```

### 4. Running the Application
**With Dashboard (Recommended):**
```bash
python3 src/gui_main.py
```

**Headless (CLI Only):**
```bash
python3 src/main.py
```

## 📐 Measurement Logic
- **Coordinate System**: Cartesian (X: Left/Right, Y: Distance from Sensor).
- **Height**: Calculated as `Baseline_Y - Object_Min_Y`.
- **Length**: Configurable in settings. 
    - `bbox`: Axis-aligned box.
    - `hull`: Longest segment across the convex hull (most accurate for irregular shapes).
    - `pca`: Principal axis projection (best for elongated objects like planks).

## 📡 Hardware Alerts
The application can trigger a physical buzzer, relay, or siren over Raspberry Pi GPIO, serial, or HTTP.
1. Enable `alerts.output` in `config.yaml`.
2. Choose `transport: gpio`, `transport: serial`, or `transport: http`.
3. For `gpio`, set the Raspberry Pi BCM pin, active polarity, and buzz duration.
4. For `serial`, set `serial_port` and `baudrate` for the Raspberry Pi UART or USB serial adapter.
5. For `http`, set the target `ip` and `port`.
6. The app sends an alert when a configured threshold with action `alert` is crossed.

Example GPIO config:
```yaml
alerts:
  output:
    enabled: true
    transport: "gpio"
    gpio_pin: 18
    gpio_active_high: true
    gpio_duration_s: 0.3
    cooldown_s: 0.5
```

Example serial config:
```yaml
alerts:
  output:
    enabled: true
    transport: "serial"
    serial_port: "/dev/serial0"
    baudrate: 115200
    cooldown_s: 0.5
```

## 🍓 Raspberry Pi Deployment
For a production Raspberry Pi install, use the headless runtime instead of the GUI after setup:
```bash
python3 src/main.py
```

Recommended workflow:
1. Run the GUI once to set floor axis, thresholds, and capture an empty scene.
2. Save the configuration.
3. Run `src/main.py` on the Raspberry Pi for headless operation.
4. Set `alerts.output.transport: gpio` and wire the buzzer to the configured BCM pin.
5. Use the headless console for the same operational actions you had in the GUI:
```text
status
capture-scene
clear-scene
auto-floor
set measurement.length.method hull
set alerts.output.transport gpio
set alerts.output.gpio_pin 18
save
```

You can also pre-apply headless overrides on startup:
```bash
python3 src/main.py \
  --set runtime.headless=true \
  --set alerts.output.transport=gpio \
  --set alerts.output.gpio_pin=18 \
  --set alerts.output.gpio_duration_s=0.4
```

Example `systemd` service:
```ini
See `deploy/gemlidar.service`.
```

## 🧪 Testing
Run the automated logic validation suite:
```bash
python3 tests/test_processing.py
```

---
**Version**: 1.0.0  
**Device**: SICK TiM240-2050300  
**License**: Proprietary / Industrial Use
