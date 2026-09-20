import sys
import os
import numpy as np
import time
import threading
from .datatypes import SICK_POINT_DTYPE

# Add sick_scan_xd to Python path using environment or standard locations.
DEFAULT_REPO_CANDIDATES = [
    os.environ.get("SICK_SCAN_XD_PATH"),
    os.path.expanduser("~/sick_scan_xd"),
    "/opt/sick_scan_xd",
]


def _resolve_repo_base(explicit_repo_base=None):
    candidates = []
    if explicit_repo_base:
        candidates.append(explicit_repo_base)
    candidates.extend(DEFAULT_REPO_CANDIDATES)

    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        normalized = os.path.abspath(os.path.expanduser(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.exists(os.path.join(normalized, "python", "api")):
            return normalized
    return os.path.abspath(os.path.expanduser(explicit_repo_base)) if explicit_repo_base else os.path.abspath(os.path.expanduser("~/sick_scan_xd"))


REPO_BASE = _resolve_repo_base()
sys.path.insert(0, os.path.join(REPO_BASE, "python/api"))

try:
    from sick_scan_api import *
except ImportError:
    print("Warning: sick_scan_api not found. Set SICK_SCAN_XD_PATH or install sick_scan_xd in a standard location.")

class TiM240Controller:
    """
    Encapsulates low-level communication with the TiM240 LiDAR using sick_scan_xd.
    Features a robust Reconnection Watchdog.
    """
    def __init__(self, lidar_ip="192.168.2.111", callback=None, repo_base=None, launch_file=None):
        self.lidar_ip = lidar_ip
        self.user_callback = callback
        self.library = None
        self.handle = None
        self.callback_wrapper = None
        self.callback_registered = False

        self.repo_base = _resolve_repo_base(repo_base)
        self.lib_path = os.path.join(self.repo_base, "build")
        self.launch_file = (
            os.path.abspath(os.path.expanduser(launch_file))
            if launch_file
            else os.path.join(self.repo_base, "launch", "sick_tim_240.launch")
        )

        # State
        self.last_data_time = 0
        self.is_connected = False
        self.is_scanning = False
        self.watchdog_active = False
        self._lock = threading.RLock()

    def connect(self):
        """Initializes connection to the LiDAR sensor."""
        with self._lock:
            if self.is_connected:
                return True

            if not os.path.exists(self.lib_path):
                raise RuntimeError(
                    f"LiDAR SDK library path not found: {self.lib_path}. "
                    "Set lidar.sdk_path in config.yaml or SICK_SCAN_XD_PATH in the environment."
                )
            if not os.path.exists(self.launch_file):
                raise RuntimeError(
                    f"LiDAR launch file not found: {self.launch_file}. "
                    "Set lidar.launch_file in config.yaml if your install uses a different path."
                )

            # 1. Load library and create handle if needed
            if self.library is None:
                self.library = SickScanApiLoadLibrary([self.lib_path + "/"], "libsick_scan_xd_shared_lib.so")
            
            if self.handle is None:
                self.handle = SickScanApiCreate(self.library)
            
            # 2. Initialize with launch file
            cli_args = f"{self.launch_file} hostname:={self.lidar_ip}"
            result = SickScanApiInitByLaunchfile(self.library, self.handle, cli_args)
            
            if result != 0:
                print(f"❌ Failed to initialize LiDAR: error code {result}")
                return False
            
            self.is_connected = True
            self.last_data_time = time.time()
            print(f"✓ Connected to TiM240 at {self.lidar_ip}")
            return True

    def _internal_callback(self, api_handle, msg):
        """Parses raw point cloud and forwards to the user callback."""
        self.last_data_time = time.time() # Update watchdog
        try:
            num_points = msg.contents.width * msg.contents.height
            if num_points == 0 or self.user_callback is None:
                return
            
            raw_ptr = msg.contents.data.buffer
            data_size = msg.contents.data.size
            raw_bytes = bytes(raw_ptr[:data_size])
            
            points = np.frombuffer(raw_bytes, dtype=SICK_POINT_DTYPE, count=num_points)
            mask = (np.abs(points['x']) > 0.01) | (np.abs(points['y']) > 0.01)
            valid_points = points[mask]
            
            self.user_callback(valid_points)
            
        except Exception as e:
            print(f"LiDAR Callback error: {e}")

    def send_cola_command(self, command: str) -> str:
        """
        Sends a raw CoLa command (e.g., 'sRN DeviceIdent') to the sensor.
        Returns the sensor's response.
        """
        with self._lock:
            if not self.handle or not self.library:
                return "ERROR: Not connected"
            
            # Use the sick_scan_xd API to send the command
            # The library handles the TCP framing and STX/ETX wrapping
            try:
                response = SickScanApiSendColaByHandle(self.library, self.handle, command)
                return response
            except Exception as e:
                return f"ERROR: {str(e)}"

    def start_scanning(self):
        """Registers callback and starts the watchdog thread."""
        with self._lock:
            if self.is_scanning:
                return

            if not self.is_connected:
                if not self.connect(): return
                
            if self.callback_wrapper is None:
                self.callback_wrapper = SickScanPointCloudMsgCallback(self._internal_callback)
                
            SickScanApiRegisterCartesianPointCloudMsg(self.library, self.handle, self.callback_wrapper)
            self.callback_registered = True
            self.is_scanning = True
            self.last_data_time = time.time()
        
        # Start Watchdog
        if not self.watchdog_active:
            self.watchdog_active = True
            threading.Thread(target=self._watchdog_loop, daemon=True).start()
            
        print("✓ Scanning started & Watchdog active")

    def _watchdog_loop(self):
        """Background thread to monitor connection health."""
        while self.watchdog_active:
            time.sleep(1.0)
            if time.time() - self.last_data_time > 3.0:
                print(f"⚠️  WATCHDOG: Connection timeout. Attempting reconnect...")
                self._reconnect_procedure()

    def _reconnect_procedure(self):
        """Executes a clean reset and reconnect."""
        with self._lock:
            print("DEBUG: Watchdog triggered reconnect.")
            self.is_connected = False
            self.is_scanning = False
            if self.library and self.handle:
                if self.callback_registered and self.callback_wrapper is not None:
                    try:
                        SickScanApiDeregisterCartesianPointCloudMsg(self.library, self.handle, self.callback_wrapper)
                    except: pass
                SickScanApiClose(self.library, self.handle)
                time.sleep(0.5) # Give it time to close
            
            if self.connect():
                if self.callback_wrapper is None:
                    self.callback_wrapper = SickScanPointCloudMsgCallback(self._internal_callback)
                SickScanApiRegisterCartesianPointCloudMsg(self.library, self.handle, self.callback_wrapper)
                self.callback_registered = True
                self.is_scanning = True
                print("✅ Reconnection Successful")

    def stop(self):
        """Releases resources and stops watchdog."""
        self.watchdog_active = False
        with self._lock:
            if self.library and self.handle:
                if self.callback_registered and self.callback_wrapper is not None:
                    try:
                        SickScanApiDeregisterCartesianPointCloudMsg(self.library, self.handle, self.callback_wrapper)
                    except Exception as e:
                        print(f"Warning: callback deregistration failed: {e}")
                try:
                    SickScanApiClose(self.library, self.handle)
                finally:
                    try:
                        SickScanApiRelease(self.library, self.handle)
                    finally:
                        try:
                            SickScanApiUnloadLibrary(self.library)
                        except Exception as e:
                            print(f"Warning: library unload failed: {e}")
            self.is_connected = False
            self.is_scanning = False
            self.callback_registered = False
            self.library = None
            self.handle = None
            self.callback_wrapper = None
            print("✓ Disconnected & Watchdog stopped")
