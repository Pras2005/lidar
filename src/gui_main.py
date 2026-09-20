import sys
import os
import time
import threading
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, pyqtSignal

# Add current directory to path to ensure local imports work
sys.path.append(os.path.join(os.path.dirname(__file__)))

from main import TiM240Application
from ui.dashboard import DashboardWindow

class DataBridge(QObject):
    """
    Refined Bridge (Phase 10).
    Now includes a throttle to prevent UI flooding.
    """
    data_received = pyqtSignal(object, object, object, object, int, str) # measurements, raw, foreground, shadow, count, alert

    def __init__(self):
        super().__init__()
        self.last_emit_time = 0
        self.throttle_interval = 0.05 # Limit to ~20 FPS updates to keep GUI responsive

    def handle_data(self, measurements, points, foreground_points, shadow_points, count, alert_status):
        """Standardized bridge callback from the application pipeline."""
        now = time.time()
        if now - self.last_emit_time > self.throttle_interval:
            self.data_received.emit(measurements, points, foreground_points, shadow_points, count, alert_status)
            self.last_emit_time = now

def main():
    qt_app = QApplication(sys.argv)
    
    # 1. Initialize UI first to setup bridge
    window = DashboardWindow()
    bridge = DataBridge()

    # 2. Initialize Logic with the Bridge callback
    logic = TiM240Application(processed_callback=bridge.handle_data)
    window.load_settings_to_ui(logic.config)
    
    # Connect signal: Bridge -> UI
    bridge.data_received.connect(lambda m, p, fg, sh, c, a: (
        window.canvas.update_cloud(p, m, fg, sh),
        window.update_ui(m, c, a),
        window.update_baseline(logic.baseline.baseline_height, logic.measurer.units),
        window.canvas.update_floor_reference(
            logic.baseline.baseline_height,
            logic.baseline.selection_range,
            logic.baseline.floor_axis,
        ),
        window.update_scene_status(logic.background.has_reference()),
        window.update_floor_mode(
            (
                f"Mode: Manual selection on {logic.baseline.floor_axis.upper()} axis"
                if logic.baseline.mode == 'manual' and logic.baseline.selection_range
                else f"Mode: Manual {logic.baseline.floor_axis.upper()} reference"
                if logic.baseline.mode == 'manual'
                else f"Mode: Auto {logic.baseline.floor_axis.upper()} reference"
            )
        )
    ))
    
    # Connect UI buttons to logic (using lock to prevent pipeline races)
    def run_lidar_action(action, failure_prefix):
        def worker():
            try:
                action()
            except Exception as e:
                print(f"{failure_prefix}: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def start_scanning():
        window.set_scanning_state(True)
        run_lidar_action(logic.lidar.start_scanning, "Start failed")
            
    def stop_scanning():
        window.set_scanning_state(False)
        run_lidar_action(logic.lidar.stop, "Stop failed")
            
    def enable_auto_floor():
        with logic.pipeline_lock:
            logic.baseline.mode = 'auto'
            logic.baseline.set_selection_range(None)
            logic.baseline.reset()
            logic.config.settings['baseline']['mode'] = 'auto'
            logic.config.settings['baseline']['height_m'] = logic.baseline.baseline_height
            logic.config.settings['baseline']['selection_range'] = None
            window.update_floor_mode(f"Mode: Auto {logic.baseline.floor_axis.upper()} reference")
            window.canvas.update_floor_reference(None)
            print("Switched to automatic floor detection.")

    def calibrate_floor_from_selection(selection_range):
        with logic.pipeline_lock:
            calibrated_height = logic.baseline.calibrate_from_scan(logic.latest_points, selection_range=selection_range)
            if calibrated_height is None:
                print("Floor selection failed. Drag across a denser wall/floor segment.")
                return

            logic.config.settings['baseline']['mode'] = 'manual'
            logic.config.settings['baseline']['height_m'] = calibrated_height
            logic.config.settings['baseline']['selection_range'] = [float(selection_range[0]), float(selection_range[1])]
            window.update_baseline(calibrated_height, logic.measurer.units)
            window.canvas.update_floor_reference(
                calibrated_height,
                logic.baseline.selection_range,
                logic.baseline.floor_axis,
            )
            window.update_floor_mode(f"Mode: Manual selection on {logic.baseline.floor_axis.upper()} axis")
            print(
                "Reference locked from selected view segment: "
                f"{('x' if logic.baseline.floor_axis == 'y' else 'y')}="
                f"{min(selection_range):.2f} to {max(selection_range):.2f}, "
                f"{logic.baseline.floor_axis}={calibrated_height:.3f} m"
            )

    def start_floor_selection():
        selected_floor_axis = window.combo_floor_axis.currentText()
        logic.baseline.update_floor_axis(selected_floor_axis)
        logic.baseline.set_selection_range(None)
        window.update_floor_mode(f"Mode: Select a strip for {selected_floor_axis.upper()} reference")
        window.canvas.begin_floor_selection(selected_floor_axis, calibrate_floor_from_selection)
        print("Drag across the plot over the strip you want to use as the floor/wall reference.")

    def capture_scene_reference():
        with logic.pipeline_lock:
            if not logic.background.capture(logic.latest_points):
                print("Scene reference capture failed. Start scanning and capture an empty alley/room view.")
                return
            logic.config.settings['scene_reference']['enabled'] = True
            logic.background.enabled = True
            window.chk_scene_reference.setChecked(True)
            window.update_scene_status(True)
            print("Empty-scene reference captured. Static room/alley structure will be ignored.")

    def clear_scene_reference():
        with logic.pipeline_lock:
            logic.background.clear()
            window.update_scene_status(False)
            print("Scene reference cleared.")

    window.btn_pick_floor.clicked.connect(start_floor_selection)
    window.btn_capture_scene.clicked.connect(capture_scene_reference)
    window.btn_clear_scene.clicked.connect(clear_scene_reference)
    window.btn_start.clicked.connect(start_scanning)
    window.btn_stop.clicked.connect(stop_scanning)
    window.btn_recalibrate.clicked.connect(enable_auto_floor)

    def trigger_sync():
        window.lbl_sync_status.setText("Status: Synchronizing...")
        window.btn_sync_embedded.setEnabled(False)
        
        def worker():
            try:
                ok = logic.sync_to_embedded()
                if ok:
                    window.lbl_sync_status.setText("Status: ✅ Standalone Ready")
                else:
                    window.lbl_sync_status.setText("Status: ❌ Sync Failed")
            except Exception as e:
                window.lbl_sync_status.setText(f"Status: ❌ Error: {str(e)}")
            finally:
                window.btn_sync_embedded.setEnabled(True)
        
        threading.Thread(target=worker, daemon=True).start()

    window.btn_sync_embedded.clicked.connect(trigger_sync)

    # Save & Apply Logic (Phase 6)
    def save_settings():
        # Ensure we don't modify params while the LiDAR thread is reading them
        with logic.pipeline_lock:
            selected_floor_axis = window.combo_floor_axis.currentText()
            axis_changed = logic.baseline.floor_axis != selected_floor_axis

            # Update config object from UI
            logic.config.settings['lidar']['ip'] = window.inp_ip.text()
            logic.config.settings['measurement']['length']['method'] = window.combo_method.currentText()
            logic.config.settings['measurement']['length']['units'] = window.combo_units.currentText()
            logic.config.settings['object_detection']['epsilon'] = window.inp_eps.value()
            logic.config.settings['baseline']['mode'] = logic.baseline.mode
            logic.config.settings['baseline']['height_m'] = logic.baseline.baseline_height
            logic.config.settings['baseline']['floor_percentile'] = window.inp_floor_percentile.value()
            logic.config.settings['baseline']['floor_axis'] = window.combo_floor_axis.currentText()
            logic.config.settings['baseline']['selection_range'] = logic.baseline.selection_range
            logic.config.settings['scene_reference']['enabled'] = window.chk_scene_reference.isChecked()
            logic.config.settings['scene_reference']['distance_tolerance'] = window.inp_scene_tolerance.value()
            
            # Update Thresholds
            logic.config.settings['measurement']['height']['thresholds'][0]['level'] = window.inp_warn.value()
            logic.config.settings['measurement']['height']['thresholds'][1]['level'] = window.inp_crit.value()
            logic.config.settings['measurement']['length']['thresholds'][0]['level'] = window.inp_length_warn.value()
            logic.config.settings['measurement']['length']['thresholds'][1]['level'] = window.inp_length_crit.value()
            
            # Alert Output
            logic.config.settings['alerts']['output']['enabled'] = window.chk_esp.isChecked()
            logic.config.settings['alerts']['output']['transport'] = window.combo_esp_transport.currentText()
            logic.config.settings['alerts']['output']['ip'] = window.inp_esp_ip.text()
            logic.config.settings['alerts']['output']['port'] = window.inp_esp_port.value()
            logic.config.settings['alerts']['output']['serial_port'] = window.inp_esp_serial_port.text()
            logic.config.settings['alerts']['output']['baudrate'] = window.inp_esp_baudrate.value()
            logic.config.settings['alerts']['output']['gpio_pin'] = window.inp_gpio_pin.value()
            logic.config.settings['alerts']['output']['gpio_active_high'] = window.chk_gpio_active_high.isChecked()
            logic.config.settings['alerts']['output']['gpio_duration_s'] = window.inp_gpio_duration.value()
            logic.config.settings['alerts']['output']['cooldown_s'] = window.inp_esp_cooldown.value()
            
            if axis_changed:
                logic.baseline.mode = 'auto'
                logic.baseline.baseline_height = 0.0
                logic.baseline.set_selection_range(None)
                logic.baseline.reset()
                logic.config.settings['baseline']['mode'] = 'auto'
                logic.config.settings['baseline']['height_m'] = 0.0
                logic.config.settings['baseline']['selection_range'] = None

            logic.config.save()
            
            # Re-apply live settings using centralized logic
            logic.apply_live_settings()
            
            # Sync UI state with applied logic
            window.update_baseline(logic.baseline.baseline_height, logic.measurer.units)
            window.canvas.update_floor_reference(
                logic.baseline.baseline_height,
                logic.baseline.selection_range,
                logic.baseline.floor_axis,
            )
            window.update_scene_status(logic.background.has_reference())
            window.update_floor_mode(
                f"Mode: Auto {logic.baseline.floor_axis.upper()} reference"
                if logic.baseline.mode == 'auto'
                else f"Mode: Manual {logic.baseline.floor_axis.upper()} reference"
            )
            
            print("✅ Settings Saved and Applied")

    window.btn_save.clicked.connect(save_settings)

    def shutdown_lidar():
        try:
            logic.lidar.stop()
        except Exception as e:
            print(f"Shutdown warning: {e}")

    qt_app.aboutToQuit.connect(shutdown_lidar)

    window.show()
    sys.exit(qt_app.exec_())

if __name__ == "__main__":
    main()
