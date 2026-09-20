import sys
import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.widgets import SpanSelector

from PyQt5 import QtCore, QtWidgets

class MplCanvas(FigureCanvas):
    """
    Real-time visualization panel using Matplotlib.
    Handles Point Cloud rendering, grid, and overlays.
    """
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#2b2b2b')
        self.axes = self.fig.add_subplot(111)
        self.axes.set_facecolor('#1e1e1e')
        
        # Grid and visual settings
        self.axes.grid(True, linestyle='--', color='#444444', alpha=0.5)
        self.axes.set_xlabel("X (meters)", color='white')
        self.axes.set_ylabel("Y (distance, m)", color='white')
        self.axes.tick_params(colors='white')
        self.axes.set_xlim(-5.5, 5.5)
        self.axes.set_ylim(0.0, 10.5)
        
        # Initial point cloud handle (empty)
        self.scatter_raw = self.axes.scatter([], [], s=8, c='#58708a', alpha=0.25)
        self.scatter_shadow = self.axes.scatter([], [], s=10, c='#4cc9f0', alpha=0.22)
        self.scatter_foreground = self.axes.scatter([], [], s=20, c='#f77f00', alpha=0.85)
        (self.line_raw,) = self.axes.plot([], [], color='#58708a', alpha=0.45, linewidth=1.0)
        (self.line_shadow,) = self.axes.plot([], [], color='#4cc9f0', alpha=0.65, linewidth=1.2)
        (self.line_foreground,) = self.axes.plot([], [], color='#f77f00', alpha=0.9, linewidth=1.8)
        self.object_rects = [] # Store bounding box patches
        self.floor_line = None
        self.floor_band = None
        self.floor_selector = None
        self.floor_selection_callback = None
        self.latest_points = None
        self.view_mode = 'clusters'
        
        super(MplCanvas, self).__init__(self.fig)
        self.setParent(parent)

    def update_cloud(self, points, objects_data=None, foreground_points=None, shadow_points=None):
        """
        Updates the visual points and object overlays.
        """
        if points is None or len(points) == 0:
            self.latest_points = None
            empty = np.empty((0, 2))
            self.scatter_raw.set_offsets(empty)
            self.scatter_shadow.set_offsets(empty)
            self.scatter_foreground.set_offsets(empty)
            self._set_line_data(self.line_raw, empty)
            self._set_line_data(self.line_shadow, empty)
            self._set_line_data(self.line_foreground, empty)
            self.draw_idle()
            return

        # Update point data
        self.latest_points = points
        xy_points = np.column_stack((points['x'], points['y']))
        self.scatter_raw.set_offsets(xy_points)
        self._update_viewport(xy_points)
        foreground_xy = self._to_xy(foreground_points)
        shadow_xy = self._to_xy(shadow_points)
        self.scatter_foreground.set_offsets(foreground_xy)
        self.scatter_shadow.set_offsets(shadow_xy)
        self._set_line_data(self.line_raw, self._sort_scan_points(xy_points))
        self._set_line_data(self.line_shadow, self._sort_scan_points(shadow_xy))
        self._set_line_data(self.line_foreground, self._sort_scan_points(foreground_xy))
        self._apply_view_mode()
        
        # Clear old object highlights (bounding boxes)
        for rect in self.object_rects:
            rect.remove()
        self.object_rects = []

        # Draw objects (boxes/overlays)
        if objects_data:
            for obj in objects_data:
                bounds = obj.get('bounds')
                if not bounds:
                    continue

                width = bounds['max_x'] - bounds['min_x']
                height = bounds['max_y'] - bounds['min_y']
                rect = Rectangle(
                    (bounds['min_x'], bounds['min_y']),
                    max(width, 0.001),
                    max(height, 0.001),
                    linewidth=2,
                    edgecolor='#ffd166',
                    facecolor='#ffd166',
                    alpha=0.15,
                )
                self.axes.add_patch(rect)
                self.object_rects.append(rect)
                
        self.draw_idle()

    def _to_xy(self, points):
        if points is None or len(points) == 0:
            return np.empty((0, 2))
        return np.column_stack((points['x'], points['y']))

    def _sort_scan_points(self, xy_points):
        if len(xy_points) == 0:
            return xy_points
        angles = np.arctan2(xy_points[:, 1], xy_points[:, 0])
        return xy_points[np.argsort(angles)]

    def _set_line_data(self, line, xy_points):
        if len(xy_points) == 0:
            line.set_data([], [])
            return
        line.set_data(xy_points[:, 0], xy_points[:, 1])

    def set_view_mode(self, mode):
        self.view_mode = mode
        self._apply_view_mode()
        self.draw_idle()

    def _apply_view_mode(self):
        show_clusters = self.view_mode == 'clusters'
        self.scatter_raw.set_visible(show_clusters)
        self.scatter_shadow.set_visible(show_clusters)
        self.scatter_foreground.set_visible(show_clusters)
        self.line_raw.set_visible(not show_clusters)
        self.line_shadow.set_visible(not show_clusters)
        self.line_foreground.set_visible(not show_clusters)
        for rect in self.object_rects:
            rect.set_visible(show_clusters)

    def begin_floor_selection(self, floor_axis, on_selected):
        self.floor_selection_callback = on_selected
        if self.floor_selector is not None:
            self.floor_selector.disconnect_events()
            self.floor_selector = None

        direction = 'horizontal' if floor_axis == 'y' else 'vertical'
        self.floor_selector = SpanSelector(
            self.axes,
            self._handle_floor_selection,
            direction,
            useblit=True,
            props=dict(alpha=0.18, facecolor='#4cc9f0'),
            interactive=False,
            drag_from_anywhere=False,
        )

    def cancel_floor_selection(self):
        if self.floor_selector is not None:
            self.floor_selector.disconnect_events()
            self.floor_selector = None
        self.floor_selection_callback = None

    def _handle_floor_selection(self, min_x, max_x):
        if self.floor_selection_callback is not None:
            self.floor_selection_callback((min_x, max_x))
        self.cancel_floor_selection()

    def update_floor_reference(self, height_m, selection_range=None, floor_axis='y'):
        if self.floor_line is not None:
            self.floor_line.remove()
            self.floor_line = None
        if self.floor_band is not None:
            self.floor_band.remove()
            self.floor_band = None

        if height_m is None:
            self.draw_idle()
            return

        if floor_axis == 'y':
            if selection_range is None:
                x_min, x_max = self.axes.get_xlim()
            else:
                x_min, x_max = sorted((float(selection_range[0]), float(selection_range[1])))

            self.floor_line = self.axes.hlines(
                y=height_m,
                xmin=x_min,
                xmax=x_max,
                colors='#4cc9f0',
                linestyles='--',
                linewidth=2,
            )
            self.floor_band = self.axes.fill_between(
                [x_min, x_max],
                [height_m, height_m],
                [height_m + 0.01, height_m + 0.01],
                color='#4cc9f0',
                alpha=0.12,
            )
        else:
            if selection_range is None:
                y_min, y_max = self.axes.get_ylim()
            else:
                y_min, y_max = sorted((float(selection_range[0]), float(selection_range[1])))

            self.floor_line = self.axes.vlines(
                x=height_m,
                ymin=y_min,
                ymax=y_max,
                colors='#4cc9f0',
                linestyles='--',
                linewidth=2,
            )
            self.floor_band = self.axes.fill_betweenx(
                [y_min, y_max],
                [height_m, height_m],
                [height_m + 0.01, height_m + 0.01],
                color='#4cc9f0',
                alpha=0.12,
            )
        self.draw_idle()

    def _update_viewport(self, xy_points):
        """Keep the full scan visible with a small dynamic margin."""
        min_x = float(np.min(xy_points[:, 0]))
        max_x = float(np.max(xy_points[:, 0]))
        min_y = float(np.min(xy_points[:, 1]))
        max_y = float(np.max(xy_points[:, 1]))

        x_margin = max(0.5, (max_x - min_x) * 0.1)
        y_margin = max(0.5, (max_y - min_y) * 0.1)

        self.axes.set_xlim(min(min_x - x_margin, -5.5), max(max_x + x_margin, 5.5))
        self.axes.set_ylim(min(min_y - y_margin, 0.0), max(max_y + y_margin, 10.5))

class DashboardWindow(QtWidgets.QMainWindow):
    """
    Main TiM240 Dashboard Window with Tabbed Interface (Phase 6).
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SICK TiM240-2050300 Control Panel")
        self.resize(1200, 800)
        self.setStyleSheet("background-color: #2b2b2b; color: white;")
        self._last_frame_time = None

        # --- TABS ---
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # 1. Dashboard Tab
        self.tab_dash = QtWidgets.QWidget()
        self.setup_dash_tab()
        self.tabs.addTab(self.tab_dash, "Live Dashboard")
        
        # 2. Settings Tab
        self.tab_settings = QtWidgets.QWidget()
        self.setup_settings_tab()
        self.tabs.addTab(self.tab_settings, "Configuration")
        self.combo_view_mode.currentIndexChanged.connect(self._handle_view_mode_change)

    def setup_dash_tab(self):
        layout = QtWidgets.QHBoxLayout(self.tab_dash)
        
        # --- LEFT PANEL: VISUALIZATION ---
        viz_container = QtWidgets.QVBoxLayout()
        self.canvas = MplCanvas(self, width=8, height=6)
        viz_container.addWidget(self.canvas)
        
        status_bar = QtWidgets.QHBoxLayout()
        self.lbl_status = QtWidgets.QLabel("● Status: Initializing...")
        self.lbl_rate = QtWidgets.QLabel("Rate: 0.0 Hz")
        self.lbl_points = QtWidgets.QLabel("Points: 0")
        self.combo_view_mode = QtWidgets.QComboBox()
        self.combo_view_mode.addItem("Cluster Points", "clusters")
        self.combo_view_mode.addItem("Connection Graph", "graph")
        status_bar.addWidget(self.lbl_status)
        status_bar.addWidget(self.lbl_rate)
        status_bar.addWidget(self.lbl_points)
        status_bar.addWidget(self.combo_view_mode)
        viz_container.addLayout(status_bar)
        layout.addLayout(viz_container, stretch=3)

        # --- RIGHT PANEL: MEASUREMENTS ---
        sidebar = QtWidgets.QVBoxLayout()
        layout.addLayout(sidebar, stretch=1)

        group_meas = QtWidgets.QGroupBox("Live Measurements")
        meas_layout = QtWidgets.QVBoxLayout()
        self.meas_list = QtWidgets.QTextEdit()
        self.meas_list.setReadOnly(True)
        self.meas_list.setStyleSheet("background-color: #1e1e1e; font-family: monospace;")
        meas_layout.addWidget(self.meas_list)
        group_meas.setLayout(meas_layout)
        sidebar.addWidget(group_meas)

        group_compare = QtWidgets.QGroupBox("Length Comparison")
        compare_layout = QtWidgets.QVBoxLayout()
        self.compare_table = QtWidgets.QTableWidget(0, 5)
        self.compare_table.setHorizontalHeaderLabels(["Obj", "Active", "BBox", "Hull", "PCA"])
        self.compare_table.horizontalHeader().setStretchLastSection(True)
        self.compare_table.verticalHeader().setVisible(False)
        self.compare_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.compare_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.compare_table.setStyleSheet("background-color: #1e1e1e;")
        compare_layout.addWidget(self.compare_table)
        group_compare.setLayout(compare_layout)
        sidebar.addWidget(group_compare)

        self.lbl_alert = QtWidgets.QLabel("SYSTEM STATUS: OK")
        self.lbl_alert.setStyleSheet("padding: 10px; background-color: green; font-weight: bold; border-radius: 5px;")
        self.lbl_alert.setAlignment(QtCore.Qt.AlignCenter)
        sidebar.addWidget(self.lbl_alert)

        group_base = QtWidgets.QGroupBox("Baseline")
        base_layout = QtWidgets.QFormLayout()
        self.lbl_base_height = QtWidgets.QLabel("0.000 m")
        self.lbl_floor_mode = QtWidgets.QLabel("Mode: Auto")
        self.lbl_floor_hint = QtWidgets.QLabel("Drag on the plot to choose which wall/floor strip is the reference.")
        self.lbl_floor_hint.setWordWrap(True)
        self.btn_pick_floor = QtWidgets.QPushButton("Pick Floor From View")
        self.btn_recalibrate = QtWidgets.QPushButton("Use Auto Floor")
        base_layout.addRow("Floor Level:", self.lbl_base_height)
        base_layout.addRow("Reference:", self.lbl_floor_mode)
        base_layout.addRow(self.lbl_floor_hint)
        base_layout.addRow(self.btn_pick_floor)
        base_layout.addRow(self.btn_recalibrate)
        group_base.setLayout(base_layout)
        sidebar.addWidget(group_base)

        group_scene = QtWidgets.QGroupBox("Scene Reference")
        scene_layout = QtWidgets.QFormLayout()
        self.lbl_scene_status = QtWidgets.QLabel("Reference: None")
        self.btn_capture_scene = QtWidgets.QPushButton("Capture Empty Scene")
        self.btn_clear_scene = QtWidgets.QPushButton("Clear Scene Reference")
        scene_layout.addRow(self.lbl_scene_status)
        scene_layout.addRow(self.btn_capture_scene)
        scene_layout.addRow(self.btn_clear_scene)
        group_scene.setLayout(scene_layout)
        sidebar.addWidget(group_scene)

        self.btn_start = QtWidgets.QPushButton("Start Scanning")
        self.btn_stop = QtWidgets.QPushButton("Stop Scanning")
        sidebar.addWidget(self.btn_start)
        sidebar.addWidget(self.btn_stop)
        sidebar.addStretch()

    def setup_settings_tab(self):
        layout = QtWidgets.QVBoxLayout(self.tab_settings)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(content)
        
        # Lidar Section
        self.inp_ip = QtWidgets.QLineEdit()
        self.inp_port = QtWidgets.QLineEdit("2111")
        form.addRow("LiDAR IP Address:", self.inp_ip)
        form.addRow("LiDAR Port:", self.inp_port)
        
        # Processing Section
        self.combo_method = QtWidgets.QComboBox()
        self.combo_method.addItems(["bbox", "hull", "pca"])
        self.combo_units = QtWidgets.QComboBox()
        self.combo_units.addItems(["m", "cm", "mm", "inch", "ft"])
        self.combo_floor_axis = QtWidgets.QComboBox()
        self.combo_floor_axis.addItems(["y", "x"])
        form.addRow("Length Algorithm:", self.combo_method)
        form.addRow("Display Units:", self.combo_units)
        form.addRow("Floor Axis:", self.combo_floor_axis)
        
        # Detection Section
        self.inp_eps = QtWidgets.QDoubleSpinBox()
        self.inp_eps.setRange(0.01, 1.0)
        self.inp_eps.setSingleStep(0.01)
        form.addRow("Clustering Epsilon:", self.inp_eps)

        self.inp_floor_percentile = QtWidgets.QDoubleSpinBox()
        self.inp_floor_percentile.setRange(1.0, 50.0)
        self.inp_floor_percentile.setSingleStep(1.0)
        self.inp_floor_percentile.setSuffix(" %")
        form.addRow("Floor Sample Percentile:", self.inp_floor_percentile)

        self.chk_scene_reference = QtWidgets.QCheckBox("Filter Static Room/Alley")
        self.inp_scene_tolerance = QtWidgets.QDoubleSpinBox()
        self.inp_scene_tolerance.setRange(0.01, 1.0)
        self.inp_scene_tolerance.setSingleStep(0.01)
        form.addRow(self.chk_scene_reference)
        form.addRow("Scene Match Tolerance (m):", self.inp_scene_tolerance)
        
        # Thresholds Section
        self.inp_warn = QtWidgets.QDoubleSpinBox()
        self.inp_warn.setRange(0.0, 10.0)
        self.inp_crit = QtWidgets.QDoubleSpinBox()
        self.inp_crit.setRange(0.0, 10.0)
        self.inp_length_warn = QtWidgets.QDoubleSpinBox()
        self.inp_length_warn.setRange(0.0, 10.0)
        self.inp_length_crit = QtWidgets.QDoubleSpinBox()
        self.inp_length_crit.setRange(0.0, 10.0)
        form.addRow("Warning Threshold (m):", self.inp_warn)
        form.addRow("Critical Threshold (m):", self.inp_crit)
        form.addRow("Length Warning (m):", self.inp_length_warn)
        form.addRow("Length Critical (m):", self.inp_length_crit)

        # Hardware Alert Section
        self.chk_esp = QtWidgets.QCheckBox("Enable Hardware Alerts")
        self.combo_esp_transport = QtWidgets.QComboBox()
        self.combo_esp_transport.addItems(["http", "serial", "gpio"])
        self.inp_esp_ip = QtWidgets.QLineEdit()
        self.inp_esp_port = QtWidgets.QSpinBox()
        self.inp_esp_port.setRange(1, 65535)
        self.inp_esp_port.setValue(80)
        self.inp_esp_serial_port = QtWidgets.QLineEdit()
        self.inp_esp_baudrate = QtWidgets.QSpinBox()
        self.inp_esp_baudrate.setRange(1200, 2000000)
        self.inp_esp_baudrate.setValue(115200)
        self.inp_esp_cooldown = QtWidgets.QDoubleSpinBox()
        self.inp_esp_cooldown.setRange(0.0, 10.0)
        self.inp_esp_cooldown.setSingleStep(0.1)
        self.inp_gpio_pin = QtWidgets.QSpinBox()
        self.inp_gpio_pin.setRange(1, 40)
        self.inp_gpio_pin.setValue(18)
        self.chk_gpio_active_high = QtWidgets.QCheckBox("GPIO Active High")
        self.chk_gpio_active_high.setChecked(True)
        self.inp_gpio_duration = QtWidgets.QDoubleSpinBox()
        self.inp_gpio_duration.setRange(0.05, 10.0)
        self.inp_gpio_duration.setSingleStep(0.05)
        self.inp_gpio_duration.setValue(0.3)
        form.addRow(self.chk_esp)
        form.addRow("Alert Transport:", self.combo_esp_transport)
        form.addRow("HTTP IP:", self.inp_esp_ip)
        form.addRow("HTTP Port:", self.inp_esp_port)
        form.addRow("Serial Port:", self.inp_esp_serial_port)
        form.addRow("Serial Baudrate:", self.inp_esp_baudrate)
        form.addRow("GPIO BCM Pin:", self.inp_gpio_pin)
        form.addRow(self.chk_gpio_active_high)
        form.addRow("GPIO Buzz Time (s):", self.inp_gpio_duration)
        form.addRow("Alert Cooldown (s):", self.inp_esp_cooldown)

        # Standalone Section
        form.addRow(QtWidgets.QLabel("")) # Spacer
        self.lbl_standalone_header = QtWidgets.QLabel("Standalone Embedded Mode")
        self.lbl_standalone_header.setStyleSheet("font-weight: bold; color: #4cc9f0; margin-top: 10px;")
        form.addRow(self.lbl_standalone_header)
        self.lbl_standalone_desc = QtWidgets.QLabel(
            "Push your current Forklift Threshold and Alley Zone directly into the LiDAR's "
            "internal memory. Once synced, you can unplug the PC and the LiDAR will "
            "trigger its internal Pin 4 directly."
        )
        self.lbl_standalone_desc.setWordWrap(True)
        self.lbl_standalone_desc.setStyleSheet("font-size: 10px; color: #aaaaaa;")
        form.addRow(self.lbl_standalone_desc)
        
        self.btn_sync_embedded = QtWidgets.QPushButton("⚡ Sync to Standalone Mode (EEPROM)")
        self.btn_sync_embedded.setStyleSheet("background-color: #f77f00; font-weight: bold; height: 30px;")
        self.lbl_sync_status = QtWidgets.QLabel("Status: Not Synced")
        form.addRow(self.btn_sync_embedded)
        form.addRow(self.lbl_sync_status)

        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        self.btn_save = QtWidgets.QPushButton("💾 Save & Apply Settings")
        self.btn_save.setStyleSheet("background-color: #007acc; font-weight: bold; height: 40px;")
        layout.addWidget(self.btn_save)

    def load_settings_to_ui(self, config):
        """Populates the settings tab with current config values."""
        self.inp_ip.setText(config.get('lidar.ip'))
        self.inp_port.setText(str(config.get('lidar.port')))
        self.combo_method.setCurrentText(config.get('measurement.length.method'))
        self.combo_units.setCurrentText(config.get('measurement.length.units'))
        self.combo_floor_axis.setCurrentText(config.get('baseline.floor_axis', 'y'))
        self.inp_eps.setValue(config.get('object_detection.epsilon'))
        self.inp_floor_percentile.setValue(config.get('baseline.floor_percentile', 15.0))
        self.chk_scene_reference.setChecked(config.get('scene_reference.enabled', True))
        self.inp_scene_tolerance.setValue(config.get('scene_reference.distance_tolerance', 0.08))
        
        thresholds = config.get('measurement.height.thresholds', [])
        if len(thresholds) >= 2:
            self.inp_warn.setValue(thresholds[0]['level'])
            self.inp_crit.setValue(thresholds[1]['level'])
        length_thresholds = config.get('measurement.length.thresholds', [])
        if len(length_thresholds) >= 2:
            self.inp_length_warn.setValue(length_thresholds[0]['level'])
            self.inp_length_crit.setValue(length_thresholds[1]['level'])
            
        self.chk_esp.setChecked(config.get('alerts.output.enabled'))
        self.combo_esp_transport.setCurrentText(config.get('alerts.output.transport', 'gpio'))
        self.inp_esp_ip.setText(config.get('alerts.output.ip'))
        self.inp_esp_port.setValue(config.get('alerts.output.port', 80))
        self.inp_esp_serial_port.setText(config.get('alerts.output.serial_port', '/dev/serial0'))
        self.inp_esp_baudrate.setValue(config.get('alerts.output.baudrate', 115200))
        self.inp_gpio_pin.setValue(config.get('alerts.output.gpio_pin', 18))
        self.chk_gpio_active_high.setChecked(config.get('alerts.output.gpio_active_high', True))
        self.inp_gpio_duration.setValue(config.get('alerts.output.gpio_duration_s', 0.3))
        self.inp_esp_cooldown.setValue(config.get('alerts.output.cooldown_s', 0.5))

    def update_ui(self, measurements, points_count, alert_status=None):
        """
        Updates the dashboard with current sensor results.
        """
        now = QtCore.QTime.currentTime()
        if self._last_frame_time is None:
            self.lbl_rate.setText("Rate: -- Hz")
        else:
            elapsed_ms = self._last_frame_time.msecsTo(now)
            if elapsed_ms > 0:
                self.lbl_rate.setText(f"Rate: {1000.0 / elapsed_ms:.1f} Hz")
        self._last_frame_time = now

        # Update point count
        self.lbl_points.setText(f"Foreground Points: {points_count}")
        self.lbl_status.setText("● Status: Receiving Data")
        
        # Update measurements text
        text = ""
        for i, m in enumerate(measurements):
            unit = m.get('units', 'm')
            text += f"Object #{i+1}\n"
            text += f"├─ Length:   {m['length']:.3f} {unit}\n"
            text += f"├─ Offset:   {m['height_above_baseline']:.3f} {unit}\n"
            text += f"└─ Sensor:   {m['distance']:.2f} {unit}\n\n"
        if not text:
            text = "No objects detected in the current frame."
        self.meas_list.setPlainText(text)
        self._update_comparison_table(measurements)
        
        # Update Alert Status
        if alert_status and alert_status != "OK":
            self.lbl_alert.setText(f"ALERT: {alert_status}")
            self.lbl_alert.setStyleSheet("padding: 10px; background-color: red; font-weight: bold; border-radius: 5px;")
        else:
            self.lbl_alert.setText("SYSTEM STATUS: OK")
            self.lbl_alert.setStyleSheet("padding: 10px; background-color: green; font-weight: bold; border-radius: 5px;")

    def update_baseline(self, height_m, units='m'):
        scale = {
            'm': 1.0,
            'cm': 100.0,
            'mm': 1000.0,
            'inch': 39.3701,
            'ft': 3.28084,
        }.get(units, 1.0)
        self.lbl_base_height.setText(f"{height_m * scale:.3f} {units}")

    def update_floor_mode(self, mode_text):
        self.lbl_floor_mode.setText(mode_text)

    def update_scene_status(self, has_reference):
        self.lbl_scene_status.setText("Reference: Captured" if has_reference else "Reference: None")

    def _handle_view_mode_change(self):
        self.canvas.set_view_mode(self.combo_view_mode.currentData())

    def _update_comparison_table(self, measurements):
        self.compare_table.setRowCount(len(measurements))
        for row, measurement in enumerate(measurements):
            unit = measurement.get('units', 'm')
            active_method = measurement.get('length_method', 'current')
            comp = measurement.get('length_comparison', {})
            values = [
                str(row + 1),
                f"{active_method}: {measurement.get('length', 0.0):.3f} {unit}",
                f"{comp.get('bbox', 0.0):.3f} {unit}",
                f"{comp.get('hull', 0.0):.3f} {unit}",
                f"{comp.get('pca', 0.0):.3f} {unit}",
            ]
            for col, value in enumerate(values):
                self.compare_table.setItem(row, col, QtWidgets.QTableWidgetItem(value))

    def set_scanning_state(self, is_scanning):
        if is_scanning:
            self.lbl_status.setText("● Status: Starting Scan...")
        else:
            self.lbl_status.setText("● Status: Stopped")
            self.lbl_rate.setText("Rate: 0.0 Hz")
