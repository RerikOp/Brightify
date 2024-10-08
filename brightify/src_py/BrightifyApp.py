import argparse
import logging
from typing import List, Literal, Optional, Tuple, Dict

from PyQt6 import QtCore
from PyQt6.QtCore import QPoint, Qt, QRect, QPropertyAnimation, QTimer, QThread, QObject, pyqtSlot, pyqtSignal, QTime
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication, QPushButton, QAbstractSlider

from brightify import app_name, OSEvent
from brightify.src_py.SensorComm import SensorComm
from brightify.src_py.monitors.finder import get_supported_monitors
from brightify.src_py.ui_config import MonitorRow, run_once, coord_to_qpoint
from brightify.src_py.ui_config import UIConfig
from brightify.src_py.monitors.MonitorBase import MonitorBase

# use global logger
logger = logging.getLogger(app_name)


class MonitorWorker(QObject):
    """
    Worker class to interact with monitors in a separate thread.
    """
    update_signal = pyqtSignal(MonitorRow, bool)

    def __init__(self):
        super().__init__()
        # Connect signals to slots
        self.update_signal.connect(self._update)
        self.__request_store: Dict[MonitorBase, Optional[int]] = {}

    def request_change(self, monitor: MonitorBase, brightness: int):
        self.__request_store[monitor] = brightness  # Store the request. Overwrite if already exists

    @pyqtSlot(MonitorRow, bool)
    def _update(self, row: MonitorRow, force_sync: bool):
        monitor = row.monitor
        if monitor is None:
            return
        # Set the brightness of the monitor with the latest request
        if monitor in self.__request_store and (brightness := self.__request_store[monitor]) is not None:
            self.__request_store[monitor] = None
            monitor.set_brightness(brightness, blocking=True)


class BrightifyApp(QMainWindow):
    """
    The main application window that contains all MonitorRows.
    """

    def __init__(self, os_event: Optional[OSEvent],
                 args: argparse.Namespace, window_type=Qt.WindowType.Window, parent=None):
        super(BrightifyApp, self).__init__(parent, window_type)
        self.__args = args
        self.__os_event = os_event
        self.__bottom_right: Optional[QPoint] = None
        self.__ui_config: UIConfig = UIConfig()
        self.__init_constants()
        self.__init_monitor_worker()
        self.__init_ui()
        self.__init_sensor()
        self.__init_os_event()

    def __init_constants(self):
        self.__os_update_timer_duration = 100
        self.__last_change_duration = 200
        self.__sensor_timer_duration = 500

    def __init_ui(self):
        """Initialize the UI components."""
        self.rows: QVBoxLayout = QVBoxLayout()
        self.monitor_rows: List[MonitorRow] = []
        self.central_widget = QWidget(self)
        self.central_widget.setLayout(self.rows)
        self.setCentralWidget(self.central_widget)

        self.fade_up_animation = QPropertyAnimation(self, b"geometry")
        self.fade_up_animation.finished.connect(self.__activate)

        self.fade_down_animation = QPropertyAnimation(self, b"geometry")
        self.fade_down_animation.finished.connect(self.__deactivate)

        # Store the time of the last change to the window (to prevent flickering)
        self.__last_change = QTime.currentTime()

    def __init_monitor_worker(self):
        self.monitor_worker = MonitorWorker()
        self.monitor_thread = QThread()
        self.monitor_worker.moveToThread(self.monitor_thread)
        self.monitor_thread.start()

    def __init_sensor(self):
        """Initialize the sensor communication and related threads."""
        self.__sensor_comm = SensorComm()
        self.__sensor_thread = QThread()
        self.__sensor_comm.moveToThread(self.__sensor_thread)
        self.__sensor_timer = QTimer(self)
        self.__sensor_timer.timeout.connect(self.__sensor_comm.update_signal.emit)
        self.__sensor_timer.timeout.connect(self.__update_ui_from_sensor)

    def __init_os_event(self):
        """Initialize the OS event handling."""
        if self.is_os_managed():
            logger.debug("OS event is set, starting OS update timer")
            self.__os_update_timer = QTimer(self)
            self.__os_update_timer.timeout.connect(self.__handle_os_update)
            self.__os_update_timer.start(self.__os_update_timer_duration)

    def redraw(self):
        """Redraw the window and reinitialize the sensor if necessary."""
        logger.debug("Redrawing window")
        self.__config_layout()
        self.setStyleSheet(self.ui_config.style_sheet)
        self.__load_rows()
        self.__reinit_sensor()
        self.__toggle_visibility()

    def change_state(self, requested_state: Literal["show", "hide", "invert"] = "invert") -> None:
        """Change the state of the window with or without animations."""
        new_state = self.__determine_new_state(requested_state)
        current_state = "hide" if self.isHidden() else "show"
        if new_state == current_state:
            return
        else:
            now = QTime.currentTime()
            if self.__last_change is not None and self.__last_change.msecsTo(now) < self.__last_change_duration:
                return
            self.__last_change = now
        if not self.ui_config.theme.has_animations:
            self.__toggle_visibility_immediate(new_state)
        elif not self.__is_animation_running():
            self.__toggle_visibility_animated(new_state)

    def is_os_managed(self) -> bool:
        """Return whether the Brightify App is managed by the OS."""
        return self.__os_event is not None

    def __set_and_notify(self, row: MonitorRow, value: int):
        """Set the brightness of a monitor and notify the worker."""
        row.slider.setValue(value)
        row.slider.actionTriggered.emit(QAbstractSlider.SliderAction.SliderMove.value)

    def __connect_monitor(self, row: MonitorRow, monitor: MonitorBase) -> bool:
        """Connect a monitor to a row and return whether the connection was successful."""
        monitor.last_get_brightness = monitor.last_get_brightness or monitor.get_brightness(force=True)
        if monitor.last_get_brightness is None:
            logger.error(f"Failed to get initial brightness of monitor \"{monitor.name()}\"")
            return False
        row.monitor = monitor
        # Set the range of the slider
        row.slider.setRange(monitor.min_brightness, monitor.max_brightness)

        def handle_action(action: int):
            value = row.slider.sliderPosition()
            self.monitor_worker.request_change(monitor, value)
            self.monitor_worker.update_signal.emit(row, False)
            row.on_value_change(value)

        row.slider.actionTriggered.connect(handle_action)

        self.__set_and_notify(row, monitor.last_get_brightness)
        return True

    def __determine_new_state(self, requested_state: Literal["show", "hide", "invert"]) -> Literal["show", "hide"]:
        """Determine the new state based on the current state and the requested state."""
        if requested_state == "invert":
            return "show" if self.isHidden() else "hide"
        elif requested_state == "show":
            return "show"
        elif requested_state == "hide":
            return "hide"
        logger.error(f"Invalid state requested: {requested_state}")
        return "hide"

    def __toggle_visibility_immediate(self, new_state: Literal["show", "hide"]):
        """Toggle the visibility of the window immediately without animations."""
        logger.debug(f"Setting state to {new_state} (no animations)")
        self.move(self.top_left)
        if new_state == "hide":
            self.__deactivate()
        elif new_state == "show":
            self.__activate()

    def __toggle_visibility_animated(self, new_state: Literal["show", "hide"]):
        """Toggle the visibility of the window with animations."""
        logger.debug(f"Setting state to {new_state} (with animations)")
        up = self.__up_geometry()
        down = self.__down_geometry()
        if new_state == "show":
            self.__activate()
            self.ui_config.config_fade_animation(self.fade_up_animation, down, up)
            self.fade_up_animation.start()
        else:
            self.ui_config.config_fade_animation(self.fade_down_animation, up, down)
            self.fade_down_animation.start()

    def __is_animation_running(self) -> bool:
        """Check if any animation is currently running."""
        return (self.fade_up_animation.state() == QPropertyAnimation.State.Running or
                self.fade_down_animation.state() == QPropertyAnimation.State.Running)

    @property
    def top_left(self) -> QPoint:
        """Return the top left corner of the window."""
        # FIXME: Handle different orientations of the taskbar
        if self.__bottom_right is None:
            return self.default_position()
        min_size = self.minimumSizeHint()
        return QPoint(self.__bottom_right.x() - min_size.width(), self.__bottom_right.y() - min_size.height())

    @property
    def ui_config(self) -> UIConfig:
        """Return the UIConfig object that contains the current theme and other UI settings."""
        return self.__ui_config

    @staticmethod
    def default_position() -> QPoint:
        """Return the default position of the window (center of the screen)."""
        screen = QApplication.primaryScreen().availableGeometry()
        logger.debug("Requesting default position for window")
        return QPoint(screen.width() // 2, screen.height() // 2)

    def __up_geometry(self) -> QRect:
        """Return the geometry for the 'up' position of the window."""
        top_left = self.top_left
        min_size = self.minimumSizeHint()
        return QRect(top_left, QPoint(top_left.x() + min_size.width(), top_left.y() + min_size.height()))

    def __down_geometry(self) -> QRect:
        """Return the geometry for the 'down' position of the window."""
        top_left = self.top_left
        min_size = self.minimumSizeHint()
        return QRect(QPoint(top_left.x(), top_left.y() + min_size.height()),
                     QPoint(top_left.x() + min_size.width(), top_left.y() + 2 * self.height()))

    def __update_ui_from_sensor(self):
        """Update the UI based on sensor data."""
        monitor_rows = [r for r in self.monitor_rows if r.monitor is not None]

        if not self.__sensor_comm.has_serial():
            self.__handle_sensor_disconnection(monitor_rows)
            return

        if not self.__sensor_comm.measurements:
            return

        for row in monitor_rows:
            self.__update_row_from_sensor(row)

    def __handle_sensor_disconnection(self, monitor_rows: List[MonitorRow]):
        """Handle the disconnection of the sensor."""
        logger.info("Sensor disconnected, press reload to reconnect")
        for row in monitor_rows:
            row.slider.setEnabled(True)
            row.is_auto_tick.setChecked(False)
            row.is_auto_tick.setEnabled(False)
        self.__sensor_timer.stop()

    def __update_row_from_sensor(self, row: MonitorRow):
        """Update a single row based on sensor data."""
        row.is_auto_tick.setEnabled(True)
        if not row.is_auto_tick.isChecked():
            row.slider.setEnabled(True)
            return
        row.slider.setEnabled(False)
        brightness = row.monitor.convert_sensor_readings(self.__sensor_comm.measurements)
        if brightness is not None:
            self.__set_and_notify(row, brightness)

    def __handle_os_update(self):
        """Handle updates from the OS event."""
        if self.__os_event.locked:
            return
        self.__update_theme()
        self.__update_position()
        self.__handle_force_redraw()
        self.__handle_last_click()
        self.__handle_exit_request()

    def __handle_exit_request(self):
        """Handle an exit request based on the OS event. Does not return."""
        if self.__os_event.exit_requested:
            logger.debug("Exit from OS requested")
            raise KeyboardInterrupt

    def __update_theme(self):
        """Update the theme based on the OS event."""
        if self.__os_event.theme is not None:
            theme = self.__os_event.theme
            if self.__args.no_animations:
                theme.has_animations = False
            self.__os_event.theme = None
            if self.ui_config.theme != theme:
                self.ui_config.theme = theme
                logger.debug(f"Theme updated to: {theme}")

    def __update_position(self):
        """Update the position of the window based on the OS event."""
        if self.__os_event.bottom_right is not None:
            x, y = self.__os_event.bottom_right
            self.__os_event.bottom_right = None
            self.__bottom_right = coord_to_qpoint((x, y))

    def __handle_force_redraw(self):
        """Handle a forced redraw based on the OS event."""
        if self.__os_event.force_redraw:
            self.__os_event.force_redraw = False
            self.__deactivate()
            self.redraw()

    def __handle_last_click(self):
        """Handle the last click event based on the OS event."""
        if self.__os_event.last_click is not None:
            p = coord_to_qpoint(self.__os_event.last_click)
            self.__os_event.last_click = None
            if self.__os_event.click_on_icon:
                logger.debug("Click on icon")
                self.__os_event.click_on_icon = False
                self.change_state("invert")
            elif not self.geometry().contains(p):
                self.change_state("hide")

    def clear_rows(self):
        """Clear all rows from the layout."""
        self.monitor_rows.clear()
        while self.rows.count():
            widget = self.rows.takeAt(0).widget()
            if isinstance(widget, MonitorRow) and widget.monitor is not None:
                widget.monitor.__del__()
            self.rows.removeWidget(widget)
            widget.hide()
            widget.deleteLater()

    def __config_layout(self):
        """Configure the layout of the window."""
        self.setWindowTitle(app_name)
        if self.is_os_managed():
            self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.FramelessWindowHint)
        else:
            self.setWindowIcon(QIcon(str(self.ui_config.theme.icon_path)))
        self.rows.setContentsMargins(self.ui_config.pad, self.ui_config.pad, self.ui_config.pad, self.ui_config.pad)
        self.rows.setSpacing(self.ui_config.pad)

    def __add_reload_button(self):
        """Add a reload button to the layout."""
        reload_button = QPushButton("Reload", self)
        reload_button.clicked.connect(lambda: self.change_state("hide"))
        if self.ui_config.theme.has_animations:
            reload_button.clicked.connect(lambda: run_once(self.fade_down_animation, self.redraw))
        else:
            reload_button.clicked.connect(self.redraw)
        reload_button.setStyleSheet(self.ui_config.button_style)
        self.rows.addWidget(reload_button)

    def __load_rows(self):
        """Load the rows with monitor data."""
        self.clear_rows()
        self.__add_reload_button()
        monitors: List[MonitorBase] = get_supported_monitors()
        if not monitors:
            logger.warning("No monitors were found - try to reconnect the monitor")
            return

        max_name_width, max_type_width = self.__add_monitor_rows(monitors)
        self.__set_minimum_label_widths(max_name_width, max_type_width)

    def __add_monitor_rows(self, monitors: List[MonitorBase]) -> Tuple[int, int]:
        """Add rows for each monitor and return the maximum label widths."""
        max_name_width = 0
        max_type_width = 0

        for monitor in monitors:
            row = MonitorRow(self.ui_config.theme, parent=self)
            row.name_label.setText(monitor.name())
            if not self.__connect_monitor(row, monitor):
                row.deleteLater()
                continue
            self.rows.addWidget(row)
            self.monitor_rows.append(row)
            max_name_width = max(max_name_width, row.name_label.minimumSizeHint().width())
            max_type_width = max(max_type_width, row.type_label.minimumSizeHint().width())

        return max_name_width, max_type_width

    def __set_minimum_label_widths(self, max_name_width: int, max_type_width: int):
        """Set the minimum widths of the name and type labels."""
        for row in self.monitor_rows:
            row.name_label.setMinimumWidth(max_name_width + self.ui_config.pad)
            row.type_label.setMinimumWidth(max_type_width + self.ui_config.pad)
            row.show()

    def __reinit_sensor(self):
        """Reinitialize the sensor if necessary."""
        has_sensor = self.__sensor_comm.reinit()
        if has_sensor:
            if not self.__sensor_thread.isRunning():
                logger.debug("Initial start of sensor thread")
                self.__sensor_thread.start()
            if not self.__sensor_timer.isActive():
                logger.debug("Starting sensor timer")
                self.__sensor_timer.start(self.__sensor_timer_duration)
        else:
            self.__sensor_timer.stop()

    def __toggle_visibility(self):
        """Toggle the visibility of the window based on the OS event."""
        if self.is_os_managed():
            self.hide()
        else:
            self.show()

    def __activate(self):
        """Activate the window."""
        self.raise_()
        self.show()
        self.activateWindow()
        self.setFocus()

    def __deactivate(self):
        """Deactivate the window."""
        self.hide()

    def close(self):
        """Handle the close event."""
        logger.debug("Trying to stop SensorTimer")
        if self.__sensor_timer.isActive():
            self.__sensor_timer.stop()

        logger.debug("Trying to stop Sensor Communcation")
        self.__sensor_comm.close()

        logger.debug("Trying to stop clear rows")
        self.clear_rows()  # also calls __del__ on each monitor

        if self.__sensor_thread.isRunning():
            logger.debug("Trying to stop Sensor Thread")
            self.__sensor_thread.quit()
            self.__sensor_thread.wait()

        if self.monitor_thread.isRunning():
            logger.debug("Trying to stop Monitor Thread")
            self.monitor_thread.quit()
            self.monitor_thread.wait()

        if self.is_os_managed():
            if self.__os_update_timer.isActive():
                logger.debug("Trying to stop OS Update Timer")
                self.__os_update_timer.stop()

        logger.info("Closed BrightifyApp successfully")
