# TiM240 LiDAR Perception Pipeline

An advanced edge-processing pipeline designed specifically for the SICK TiM240 2D LiDAR scanner. Built in Python, this system acquires high-frequency raw polar coordinate data via the `sick_scan_xd` driver layer (using the SICK CoLa-B protocol), maps it into Cartesian space, and applies continuous background subtraction and density-based spatial clustering (DBSCAN) to identify and measure discrete physical objects in real-time.

## System Architecture & Domain Models

At its core, this software operates as a streaming point cloud processor with several discrete stages:

*   **Acquisition (`TiM240Controller`)**: Manages the low-level socket connections and protocol exchanges with the SICK TiM240 hardware using `sick_scan_xd`. It automatically manages disconnections and watchdog timers.
*   **Calibration (`BaselineCalibration`)**: Establishes a static environment baseline (floor profile). Supports automatic geometric calibration (using percentile-based floor estimation) and manual selection ranges.
*   **Segmentation (`BackgroundSubtractor`)**: Dynamically partitions incoming point clouds into foreground and background structures by referencing the static environment baseline and analyzing range deltas.
*   **Clustering (`ObjectDetector`)**: Consolidates foreground point clouds into discrete target objects via `scikit-learn`'s DBSCAN algorithm (`eps` and `min_samples` constraints configurable in `config.yaml`).
*   **Measurement (`MeasurementEngine`)**: Evaluates geometric dimensions (bounding boxes, height, length) against thresholds mapped out in `measurement.thresholds`.
*   **Hardware Actuation (`HardwareAlertClient`)**: Bridges the software state into physical reality, capable of sending state changes to GPIO (Raspberry Pi), Serial, or HTTP Webhooks (e.g., an ESP32 client).

## Prerequisites

*   **Operating System**: Linux (Ubuntu 20.04/22.04 recommended)
*   **Python Version**: 3.8+ 
*   **Driver Layer**: [sick_scan_xd](https://github.com/SICKAG/sick_scan_xd) must be installed and compiled locally. The API bindings must be available either at `~/sick_scan_xd`, `/opt/sick_scan_xd`, or via the `SICK_SCAN_XD_PATH` environment variable.
*   **Hardware Requirements**: SICK TiM240 connected via Ethernet (default IP: `192.168.2.111`).
*   **Dependencies**: Defined in `requirements.txt`. Key libraries include `numpy`, `scikit-learn`, `PyQt5`, `matplotlib`, and `PyYAML`. 

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/Pras2005/lidar.git
    cd lidar
    ```

2.  **Install Python dependencies**:
    ```bash
    # For GUI execution
    pip install -r requirements.txt 
    
    # For headless execution (e.g., on a Raspberry Pi without a display)
    pip install -r requirements-headless.txt
    ```

3.  **Ensure `sick_scan_xd` Python API is available**:
    If your `sick_scan_xd` installation is non-standard, export the path:
    ```bash
    export SICK_SCAN_XD_PATH=/path/to/your/sick_scan_xd
    ```

## Usage

The application can be run in two modes:

### GUI Mode
The graphical interface provides real-time visualization of the point cloud, detected objects, bounding boxes, and system states using a PyQt5/Matplotlib dashboard.

```bash
python3 src/gui_main.py
```

### Headless Mode
For deployment on edge devices like the Raspberry Pi, run the core pipeline without the Qt5 overhead. It will rely purely on file logging and GPIO/HTTP alerts.

```bash
python3 src/main.py
```

## Configuration

System behavior is driven entirely by `config.yaml`. Key sections include:
*   `lidar`: Network parameters (IP, Port, Protocol).
*   `scan`: Field of view and angular resolution constraints.
*   `object_detection`: Tunables for the DBSCAN algorithm (`epsilon`, `min_samples`, `min_object_size`).
*   `measurement`: Alert thresholds and measurement methods (e.g., bounding box height and length).
*   `alerts`: Configuration for hardware triggers, including Raspberry Pi GPIO mapping.

## Project Structure

```
.
├── config.yaml               # Centralized configuration mapping
├── deploy/                   # Systemd service files for headless startup
├── logs/                     # Auto-generated CSV measurement traces
├── src/
│   ├── main.py               # Headless entry point
│   ├── gui_main.py           # PyQt5 dashboard entry point
│   ├── lidar/                # Hardware communication and point definitions
│   ├── processing/           # DBSCAN clustering and bounding box math
│   ├── alerts/               # HTTP, Serial, and GPIO actuation bindings
│   ├── app_logging/          # Asynchronous measurement persistence
│   └── ui/                   # Real-time Matplotlib rendering canvas
└── tests/                    # Pytest suite for the processing pipeline
```
