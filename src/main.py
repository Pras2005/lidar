import argparse
import os
import signal
import sys
import threading
import time
from typing import Any

import yaml

from alerts.esp32_client import HardwareAlertClient
from alerts.monitor import ThresholdMonitor
from app_logging.logger import MeasurementLogger
from config.manager import ConfigManager
from lidar.controller import TiM240Controller
from lidar.embedded import TiM240EmbeddedManager
from processing.background import BackgroundSubtractor
from processing.baseline import BaselineCalibration
from processing.detector import ObjectDetector
from processing.measurement import MeasurementEngine


class TiM240Application:
    """
    Centralized processing runtime shared by GUI and headless execution.
    """

    def __init__(self, config_path: str = "config.yaml", processed_callback=None):
        self.config = ConfigManager(config_path)
        self.settings = self.config.load()
        self.on_processed_data = processed_callback
        self.pipeline_lock = threading.Lock()
        self.is_running = False
        self.latest_points = None
        self.latest_foreground_points = None
        self.latest_shadow_points = None
        self.latest_measurements = []
        self.latest_alert_status = "OK"
        self.latest_foreground_count = 0

        self.lidar = TiM240Controller(
            lidar_ip=self.config.get("lidar.ip", "192.168.2.111"),
            callback=self._process_pipeline,
            repo_base=self.config.get("lidar.sdk_path", None),
            launch_file=self.config.get("lidar.launch_file", None),
        )

        self._init_modules()

    def _init_modules(self):
        self.detector = ObjectDetector(
            epsilon=self.config.get("object_detection.epsilon", 0.05),
            min_samples=self.config.get("object_detection.min_samples", 5),
            min_object_size=self.config.get("object_detection.min_object_size", 0.02),
            max_object_size=self.config.get("object_detection.max_object_size", 5.0),
        )
        self.measurer = MeasurementEngine(
            length_method=self.config.get("measurement.length.method", "bbox"),
            units=self.config.get("measurement.length.units", "m"),
        )
        self.baseline = BaselineCalibration(
            mode=self.config.get("baseline.mode", "auto"),
            fixed_height=self.config.get("baseline.height_m", 0.0),
            floor_percentile=self.config.get("baseline.floor_percentile", 15.0),
            floor_axis=self.config.get("baseline.floor_axis", "y"),
            selection_range=self.config.get(
                "baseline.selection_range",
                self.config.get("baseline.selection_x_range", None),
            ),
        )
        self.monitor = ThresholdMonitor(
            height_thresholds=self.config.get("measurement.height.thresholds", []),
            length_thresholds=self.config.get("measurement.length.thresholds", []),
        )
        self.background = BackgroundSubtractor(
            enabled=self.config.get("scene_reference.enabled", True),
            distance_tolerance=self.config.get("scene_reference.distance_tolerance", 0.08),
        )
        self.auto_capture_scene_reference = self.config.get("scene_reference.auto_capture", False)
        self.alert_client = HardwareAlertClient(
            ip=self.config.get("alerts.output.ip", "127.0.0.1"),
            port=self.config.get("alerts.output.port", 80),
            enabled=self.config.get("alerts.output.enabled", False),
            transport=self.config.get("alerts.output.transport", "gpio"),
            serial_port=self.config.get("alerts.output.serial_port", "/dev/serial0"),
            baudrate=self.config.get("alerts.output.baudrate", 115200),
            serial_timeout=self.config.get("alerts.output.serial_timeout", 0.5),
            cooldown_s=self.config.get("alerts.output.cooldown_s", 0.5),
            gpio_pin=self.config.get("alerts.output.gpio_pin", 18),
            gpio_active_high=self.config.get("alerts.output.gpio_active_high", True),
            gpio_duration_s=self.config.get("alerts.output.gpio_duration_s", 0.3),
        )
        self.embedded = TiM240EmbeddedManager(self.lidar)
        self.logger = MeasurementLogger()

    def _process_pipeline(self, points):
        if not self.pipeline_lock.acquire(blocking=False):
            return

        try:
            self.latest_points = points
            if self.baseline.mode == "auto" and not self.baseline.is_calibrated:
                self.baseline.auto_calibrate_floor(points)
            if self.auto_capture_scene_reference and not self.background.has_reference():
                self.background.capture(points)

            foreground_points, shadow_points = self.background.split_points(points)
            self.latest_foreground_points = foreground_points
            self.latest_shadow_points = shadow_points
            objects = self.detector.detect_objects(foreground_points)

            measurements = []
            frame_alerts = []
            for obj_pts in objects:
                measurement = self.measurer.measure_object(
                    obj_pts,
                    self.baseline.baseline_height,
                    baseline_axis=self.baseline.floor_axis,
                )
                comparison_m = self.measurer.compare_length_methods(obj_pts)
                measurement["length_comparison_m"] = comparison_m
                measurement["length_comparison"] = self.measurer.convert_length_comparison(comparison_m)
                measurement["length_method"] = self.measurer.length_method
                alerts = self.monitor.check_measurements(measurement)
                if alerts:
                    measurement["alerts"] = alerts
                    frame_alerts.extend(alerts)
                    if alerts[-1]["action"] == "alert":
                        trigger_metric = alerts[-1]["metric"]
                        trigger_value = (
                            measurement["height_above_baseline_m"]
                            if trigger_metric == "height"
                            else measurement["length_m"]
                        )
                        self.alert_client.trigger_alert(alerts[-1]["name"], trigger_value)
                measurements.append(measurement)

            if measurements:
                self.logger.log_measurements(measurements)

            alert_status = self.monitor.summarize_alerts(frame_alerts)
            self.latest_measurements = measurements
            self.latest_alert_status = alert_status
            self.latest_foreground_count = len(foreground_points)

            if self.on_processed_data:
                self.on_processed_data(
                    measurements,
                    points,
                    foreground_points,
                    shadow_points,
                    self.latest_foreground_count,
                    alert_status,
                )

        except Exception as exc:
            print(f"Pipeline Error: {exc}")
        finally:
            self.pipeline_lock.release()

    def apply_live_settings(self):
        self.measurer.length_method = self.config.get("measurement.length.method", "bbox")
        self.measurer.units = self.config.get("measurement.length.units", "m")
        self.detector.update_params(
            epsilon=self.config.get("object_detection.epsilon", 0.05),
            min_samples=self.config.get("object_detection.min_samples", 5),
            min_object_size=self.config.get("object_detection.min_object_size", 0.02),
            max_object_size=self.config.get("object_detection.max_object_size", 5.0),
        )
        self.baseline.mode = self.config.get("baseline.mode", "auto")
        self.baseline.baseline_height = self.config.get("baseline.height_m", 0.0)
        self.baseline.update_floor_percentile(self.config.get("baseline.floor_percentile", 15.0))
        self.baseline.update_floor_axis(self.config.get("baseline.floor_axis", "y"))
        selection_range = self.config.get("baseline.selection_range", None)
        self.baseline.set_selection_range(tuple(selection_range) if selection_range else None)
        self.background.enabled = self.config.get("scene_reference.enabled", True)
        self.background.distance_tolerance = self.config.get("scene_reference.distance_tolerance", 0.08)
        self.auto_capture_scene_reference = self.config.get("scene_reference.auto_capture", False)
        self.monitor.update_thresholds(
            self.config.get("measurement.height.thresholds", []),
            self.config.get("measurement.length.thresholds", []),
        )
        self.alert_client.configure(
            enabled=self.config.get("alerts.output.enabled", False),
            transport=self.config.get("alerts.output.transport", "gpio"),
            ip=self.config.get("alerts.output.ip", "127.0.0.1"),
            port=self.config.get("alerts.output.port", 80),
            serial_port=self.config.get("alerts.output.serial_port", "/dev/serial0"),
            baudrate=self.config.get("alerts.output.baudrate", 115200),
            serial_timeout=self.config.get("alerts.output.serial_timeout", 0.5),
            cooldown_s=self.config.get("alerts.output.cooldown_s", 0.5),
            gpio_pin=self.config.get("alerts.output.gpio_pin", 18),
            gpio_active_high=self.config.get("alerts.output.gpio_active_high", True),
            gpio_duration_s=self.config.get("alerts.output.gpio_duration_s", 0.3),
        )
        lidar_ip = self.config.get("lidar.ip", "192.168.2.111")
        self.lidar.lidar_ip = lidar_ip
        self.lidar.repo_base = self.config.get("lidar.sdk_path", None) or self.lidar.repo_base
        self.lidar.lib_path = os.path.join(self.lidar.repo_base, "build")
        launch_file = self.config.get("lidar.launch_file", None)
        self.lidar.launch_file = (
            os.path.abspath(os.path.expanduser(launch_file))
            if launch_file
            else os.path.join(self.lidar.repo_base, "launch", "sick_tim_240.launch")
        )

    def _set_nested_value(self, key_path: str, value: Any):
        keys = key_path.split(".")
        target = self.config.settings
        for key in keys[:-1]:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
            target = target[key]
        target[keys[-1]] = value

    def update_setting(self, key_path: str, value: Any, persist: bool = False):
        with self.pipeline_lock:
            previous_axis = self.config.get("baseline.floor_axis", "y")
            self._set_nested_value(key_path, value)

            if key_path == "baseline.floor_axis" and value != previous_axis:
                self._set_nested_value("baseline.mode", "auto")
                self._set_nested_value("baseline.height_m", 0.0)
                self._set_nested_value("baseline.selection_range", None)
                self.baseline.reset()

            self.apply_live_settings()

            if persist:
                self.config.save()

    def save_config(self):
        with self.pipeline_lock:
            self.config.save()

    def enable_auto_floor(self):
        with self.pipeline_lock:
            self.baseline.mode = "auto"
            self.baseline.set_selection_range(None)
            self.baseline.reset()
            self._set_nested_value("baseline.mode", "auto")
            self._set_nested_value("baseline.height_m", self.baseline.baseline_height)
            self._set_nested_value("baseline.selection_range", None)

    def calibrate_floor_from_selection(self, selection_range):
        with self.pipeline_lock:
            calibrated_height = self.baseline.calibrate_from_scan(
                self.latest_points,
                selection_range=selection_range,
            )
            if calibrated_height is None:
                return None

            self._set_nested_value("baseline.mode", "manual")
            self._set_nested_value("baseline.height_m", calibrated_height)
            self._set_nested_value(
                "baseline.selection_range",
                [float(selection_range[0]), float(selection_range[1])],
            )
            return calibrated_height

    def capture_scene_reference(self):
        with self.pipeline_lock:
            if not self.background.capture(self.latest_points):
                return False
            self._set_nested_value("scene_reference.enabled", True)
            self.background.enabled = True
            return True

    def clear_scene_reference(self):
        with self.pipeline_lock:
            self.background.clear()

    def sync_to_embedded(self):
        """
        Synchronizes current threshold and zone settings to the sensor's EEPROM.
        """
        with self.pipeline_lock:
            # Corrected logic: Specifically look for the 'alert' threshold level
            length_thresholds = self.config.get("measurement.length.thresholds", [])
            forklift_threshold = 0.9 # Default
            
            for t in length_thresholds:
                if t.get("action") == "alert":
                    forklift_threshold = t.get("level", 0.9)
                    break
            
            # Use current baseline data or defaults
            depth = self.baseline.baseline_height if self.baseline.baseline_height > 0 else 5.0
            width = 4.0 # Default alley width
            
            return self.embedded.setup_standalone_forklift_mode(
                width_m=width,
                depth_m=depth,
                forklift_min_m=forklift_threshold
            )

    def get_status_snapshot(self):
        with self.pipeline_lock:
            return {
                "running": self.is_running,
                "lidar_connected": self.lidar.is_connected,
                "lidar_scanning": self.lidar.is_scanning,
                "baseline_mode": self.baseline.mode,
                "baseline_axis": self.baseline.floor_axis,
                "baseline_height_m": self.baseline.baseline_height,
                "scene_reference": self.background.has_reference(),
                "foreground_points": self.latest_foreground_count,
                "objects": len(self.latest_measurements),
                "alert": self.latest_alert_status,
                "alert_transport": self.alert_client.transport,
            }

    def run(self):
        try:
            self.lidar.connect()
            self.lidar.start_scanning()
            self.is_running = True

            print("TiM240 application is running. Press Ctrl+C to stop.")
            while self.is_running:
                time.sleep(0.1)

        except KeyboardInterrupt:
            self.stop()
        except Exception as exc:
            print(f"Fatal Error: {exc}")
            self.stop()

    def stop(self):
        if not self.is_running and not self.lidar.is_scanning and not self.lidar.is_connected:
            return
        print("\nShutting down...")
        self.is_running = False
        try:
            self.lidar.stop()
        finally:
            self.alert_client.close()
            self.config.save()


class HeadlessRuntime:
    def __init__(self, app: TiM240Application, status_interval: float = 5.0, enable_console: bool = True):
        self.app = app
        self.status_interval = max(0.5, status_interval)
        self.enable_console = enable_console
        self._last_status_at = 0.0
        self._last_alert_status = "OK"

    def handle_data(self, measurements, points, foreground_points, shadow_points, count, alert_status):
        _ = (points, foreground_points, shadow_points)
        now = time.time()
        if alert_status != self._last_alert_status:
            print(f"[alert] {alert_status}")
            self._last_alert_status = alert_status
        if now - self._last_status_at >= self.status_interval:
            self.print_status()
            self._last_status_at = now

    def print_status(self):
        status = self.app.get_status_snapshot()
        print(
            "[status] "
            f"scan={'on' if status['lidar_scanning'] else 'off'} "
            f"connected={'yes' if status['lidar_connected'] else 'no'} "
            f"objects={status['objects']} "
            f"foreground_points={status['foreground_points']} "
            f"baseline={status['baseline_mode']}:{status['baseline_axis']}={status['baseline_height_m']:.3f}m "
            f"scene_ref={'yes' if status['scene_reference'] else 'no'} "
            f"alert={status['alert']} "
            f"transport={status['alert_transport']}"
        )

    def maybe_start_console(self):
        if not self.enable_console or not sys.stdin.isatty():
            return
        thread = threading.Thread(target=self._console_loop, daemon=True)
        thread.start()

    def _console_loop(self):
        print("Headless console ready. Type 'help' for commands.")
        while True:
            if not self.app.is_running and not self.app.lidar.is_connected and not self.app.lidar.is_scanning:
                return
            try:
                line = input("> ").strip()
            except EOFError:
                return
            except Exception as exc:
                print(f"Console input error: {exc}")
                return

            if not line:
                continue
            if not self._handle_command(line):
                return

    def _handle_command(self, line: str) -> bool:
        parts = line.split()
        command = parts[0].lower()

        if command in {"quit", "exit"}:
            self.app.stop()
            return False
        if command == "help":
            self._print_help()
            return True
        if command == "status":
            self.print_status()
            return True
        if command == "save":
            self.app.save_config()
            print("Configuration saved.")
            return True
        if command == "capture-scene":
            ok = self.app.capture_scene_reference()
            print("Scene reference captured." if ok else "Scene reference capture failed.")
            return True
        if command == "clear-scene":
            self.app.clear_scene_reference()
            print("Scene reference cleared.")
            return True
        if command == "auto-floor":
            self.app.enable_auto_floor()
            print("Automatic floor calibration enabled.")
            return True
        if command == "sync-embedded":
            print("Initiating Standalone Mode Synchronization...")
            ok = self.app.sync_to_embedded()
            if ok:
                print("SUCCESS: Sensor is now autonomous.")
            else:
                print("FAILED: Check sensor connection and logs.")
            return True
        if command == "set" and len(parts) >= 3:
            key_path = parts[1]
            raw_value = line.split(None, 2)[2]
            try:
                value = yaml.safe_load(raw_value)
            except yaml.YAMLError as exc:
                print(f"Invalid value: {exc}")
                return True
            self.app.update_setting(key_path, value)
            print(f"Updated {key_path} = {value!r}")
            return True

        print("Unknown command. Type 'help' for commands.")
        return True

    def _print_help(self):
        print("Commands:")
        print("  status")
        print("  capture-scene")
        print("  clear-scene")
        print("  auto-floor")
        print("  set <dot.path> <yaml-value>")
        print("  save")
        print("  quit")


def build_parser():
    parser = argparse.ArgumentParser(description="TiM240 headless runtime")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument(
        "--status-interval",
        type=float,
        default=5.0,
        help="Seconds between headless status lines",
    )
    parser.add_argument(
        "--no-console",
        action="store_true",
        help="Disable the interactive headless console",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Apply config overrides before startup, example: --set alerts.output.transport=gpio",
    )
    parser.add_argument(
        "--capture-scene-on-start",
        action="store_true",
        help="Capture the current empty scene as soon as the first scans arrive",
    )
    return parser


def parse_override(override: str):
    if "=" not in override:
        raise ValueError(f"Invalid override '{override}'. Expected KEY=VALUE.")
    key_path, raw_value = override.split("=", 1)
    return key_path.strip(), yaml.safe_load(raw_value)


def main():
    args = build_parser().parse_args()
    app = TiM240Application(config_path=args.config)
    runtime = HeadlessRuntime(app, status_interval=args.status_interval, enable_console=not args.no_console)
    app.on_processed_data = runtime.handle_data

    app.update_setting("runtime.headless", True)
    for override in args.set:
        key_path, value = parse_override(override)
        app.update_setting(key_path, value)

    if args.capture_scene_on_start:
        app.update_setting("scene_reference.auto_capture", True)

    def signal_handler(sig, frame):
        _ = (sig, frame)
        app.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    runtime.maybe_start_console()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
