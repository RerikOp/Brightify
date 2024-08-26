import argparse
import logging
from typing import List, Tuple, Callable, Literal, Any, Optional

from PyQt6 import QtCore
from PyQt6.QtCore import QPoint, Qt, QRect, QPropertyAnimation, QTimer, QThread
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication, QPushButton

from brightify import app_name, OSEvent
from brightify.src_py.SensorComm import SensorComm
from brightify.src_py.monitors.finder import get_supported_monitors
from brightify.src_py.ui_config import MonitorRow
from brightify.src_py.ui_config import UIConfig
from brightify.src_py.monitors.MonitorBase import MonitorBase

# use global logger
logger = logging.getLogger(app_name)


class BaseApp(QMainWindow):
    """
    The main application window that contains all MonitorRows.
    """

    def __init__(self, os_event: Optional[OSEvent],
                 args: argparse.Namespace,
                 window_type=Qt.WindowType.Window,
                 parent=None):
        super(BaseApp, self).__init__(parent, window_type)
        self.__args = args

        # The rows contain one MonitorRow for each supported Monitor connected
        self.rows: QVBoxLayout = QVBoxLayout()
        self.monitor_rows: List[MonitorRow] = []  # initialized on redraw
        self.central_widget = QWidget(self)
        self.central_widget.setLayout(self.rows)
        self.setCentralWidget(self.central_widget)

        self.__os_event = os_event

        self.__bottom_right: QPoint | None = None
        self.__ui_config: UIConfig = UIConfig()

        self.__sensor_comm = SensorComm()
        self.__sensor_thread = QThread()
        self.__sensor_comm.moveToThread(self.__sensor_thread)
        self.__sensor_timer = QTimer(self)
        self.__sensor_timer.timeout.connect(self.__sensor_comm.update_signal.emit)
        self.__sensor_timer.timeout.connect(self.update_ui_from_sensor)

        if self.__os_event is not None:
            logger.debug("OS event is set, starting OS update timer")
            self.__os_update_timer = QTimer(self)
            self.__os_update_timer.timeout.connect(self.handle_os_update)
            self.__os_update_timer.start(100)

        # Animations:
        self.fade_up_animation = QPropertyAnimation(self, b"geometry")
        self.fade_up_animation.finished.connect(self.activateWindow)
        self.fade_up_animation.finished.connect(self.setFocus)

        self.fade_down_animation = QPropertyAnimation(self, b"geometry")
        self.fade_down_animation.finished.connect(self.clearFocus)
        self.fade_down_animation.finished.connect(self.hide)

    @property
    def top_left(self) -> QPoint:
        if self.__bottom_right is None:
            return self.default_position()
        min_size = self.minimumSizeHint()
        return QPoint(self.__bottom_right.x() - min_size.width(), self.__bottom_right.y() - min_size.height())

    def up_geometry(self):
        top_left = self.top_left
        min_size = self.minimumSizeHint()
        up = QRect(top_left, QPoint(top_left.x() + min_size.width(),
                                    top_left.y() + min_size.height()))
        return up

    def down_geometry(self):
        top_left = self.top_left
        min_size = self.minimumSizeHint()
        min_height = min_size.height()
        min_width = min_size.width()
        down = QRect(QPoint(top_left.x(), top_left.y() + min_height),
                     QPoint(top_left.x() + min_width, top_left.y() + 2 * self.height()))
        return down

    @staticmethod
    def _coord_to_qpoint(coord: Tuple[int, int]) -> QPoint:
        x, y = coord
        ratio = QApplication.primaryScreen().devicePixelRatio()
        return QPoint(int(x // ratio), int(y // ratio))

    def handle_os_update(self):
        if self.__os_event.locked:
            return
        if self.__os_event.theme is not None:
            theme = self.__os_event.theme
            if self.__args.no_animations:
                theme.has_animations = False
            self.__os_event.theme = None
            if self.ui_config.theme == theme:
                logger.debug("No theme update needed")
            else:
                self.ui_config.theme = theme
                logger.debug(f"Theme updated to: {theme}")
        if self.__os_event.bottom_right is not None:
            x, y = self.__os_event.bottom_right
            self.__os_event.bottom_right = None
            self.__bottom_right = self._coord_to_qpoint((x, y))
        if self.__os_event.force_redraw:
            self.__os_event.force_redraw = False
            self.deactivate()
            self.redraw()
        if self.__os_event.last_click is not None:
            p = self._coord_to_qpoint(self.__os_event.last_click)
            self.__os_event.last_click = None
            if self.__os_event.click_on_icon:
                logger.debug("Click on icon")
                self.__os_event.click_on_icon = False
                self.change_state("invert")
            # else check if the click was inside the window
            elif not self.geometry().contains(p):
                self.change_state("hide")

    @property
    def ui_config(self) -> UIConfig:
        return self.__ui_config

    def __config_layout(self):
        self.setWindowTitle(app_name)
        if self.__os_event is not None:
            self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.FramelessWindowHint)
        else:
            # set icon path
            icon = QIcon(str(self.ui_config.theme.icon_path))
            self.setWindowIcon(icon)
        self.rows.setContentsMargins(self.ui_config.pad, self.ui_config.pad,
                                     self.ui_config.pad, self.ui_config.pad)
        self.rows.setSpacing(self.ui_config.pad)

    @staticmethod
    def __config_slider(row: MonitorRow):
        def on_change(value):
            row.brightness_label.setText(f"{value}%")

        row.slider.valueChanged.connect(lambda value: on_change(value))

    @staticmethod
    def __connect_monitor(row: MonitorRow, monitor: MonitorBase) -> bool:
        initial_brightness = monitor.get_brightness(force=True)
        if initial_brightness is None:
            logger.warning(f"Failed to get initial brightness of monitor {monitor.name()}. Skipping it.")
            return False

        row.slider.setValue(initial_brightness)
        row.slider.valueChanged.connect(lambda value: monitor.set_brightness(value, blocking=True))
        row.monitor = monitor
        return True

    def update_ui_from_sensor(self):
        monitor_rows = list(filter(lambda r: r.monitor is not None, self.monitor_rows))

        if not self.__sensor_comm.has_serial():
            logger.info("Sensor disconnected, press reload to reconnect")
            for row in monitor_rows:
                row.slider.setEnabled(True)  # enable the slider
                row.is_auto_tick.setChecked(False)  # disable the auto tick
                row.is_auto_tick.setEnabled(False)  # disable the auto tick
            self.__sensor_timer.stop()
            return

        if not self.__sensor_comm.measurements:
            return  # no sensor data available, do nothing for now

        for row in monitor_rows:
            # enable the auto tick
            row.is_auto_tick.setEnabled(True)
            if not row.is_auto_tick.isChecked():
                # enable the slider
                row.slider.setEnabled(True)
                continue
            # disable the slider
            row.slider.setEnabled(False)
            # lazily set the slider to the current brightness or keep it where the user set it
            brightness = row.monitor.convert_sensor_readings(self.__sensor_comm.measurements)
            if brightness is not None:
                # also sets the brightness label and sends the brightness to the monitor as we connected the slider
                row.slider.setValue(brightness)
                # trigger release event to set the brightness on DDCCI monitors
                row.slider.sliderReleased.emit()

    def clear_rows(self):
        self.monitor_rows.clear()
        while self.rows.count():
            widget = self.rows.takeAt(0).widget()
            if isinstance(widget, MonitorRow):
                if widget.monitor is not None:
                    widget.monitor.__del__()  # delete the monitor object
            self.rows.removeWidget(widget)
            widget.hide()  # hide the widget
            widget.deleteLater()  # schedule the widget for deletion

    @staticmethod
    def run_once(animation: QPropertyAnimation, finished: Callable[[], Any]):
        def run_and_disconnect():
            finished()
            animation.finished.disconnect(run_and_disconnect)

        animation.finished.connect(run_and_disconnect)

    def __add_reload_button(self):
        # add a reload button to the top of self.rows
        reload_button = QPushButton("Reload", self)
        reload_button.clicked.connect(lambda: self.change_state("hide"))
        if self.ui_config.theme.has_animations:
            reload_button.clicked.connect(lambda: self.run_once(self.fade_down_animation, self.redraw))
        else:
            reload_button.clicked.connect(self.redraw)
        reload_button.setStyleSheet(self.ui_config.button_style)
        self.rows.addWidget(reload_button)

    def __load_rows(self):
        self.clear_rows()
        max_name_width = 0
        max_type_width = 0
        monitors: List[MonitorBase] = get_supported_monitors()
        self.__add_reload_button()
        if not monitors:
            logger.warning("No monitors were found - try to reconnect the monitor")
            return

        for m in monitors:
            row = MonitorRow(self.ui_config.theme, parent=self)
            row.slider.setRange(m.min_brightness, m.max_brightness)
            row.name_label.setText(m.name())
            self.__config_slider(row)
            succ = self.__connect_monitor(row, m)
            if not succ:
                row.deleteLater()
                continue

            self.rows.addWidget(row)
            self.monitor_rows.append(row)
            max_name_width = max(max_name_width, row.name_label.minimumSizeHint().width())
            max_type_width = max(max_type_width, row.type_label.minimumSizeHint().width())

        # set the minimum width of the name labels to the maximum width over all labels
        for row in self.monitor_rows:
            row.name_label.setMinimumWidth(max_name_width + 5)
            row.type_label.setMinimumWidth(max_type_width + 5)
            row.show()

    def redraw(self):
        logger.debug(f"Redrawing window")
        self.__config_layout()
        self.setStyleSheet(self.ui_config.style_sheet)
        self.__load_rows()
        # On every redraw we (re)connect the sensor
        has_sensor = self.__sensor_comm.reinit()
        if has_sensor:
            # start the sensor thread if it's not running
            if not self.__sensor_thread.isRunning():
                logger.debug("Initial start of sensor thread")
                self.__sensor_thread.start()
            if not self.__sensor_timer.isActive():
                logger.debug("Starting sensor timer")
                self.__sensor_timer.start(250)
        else:
            self.__sensor_timer.stop()
        # we only hide if os managed:
        if self.__os_event is not None:
            self.hide()
        else:
            self.show()

    @staticmethod
    def default_position():
        screen = QApplication.primaryScreen().availableGeometry()
        logger.debug("Requesting default position for window")
        return QPoint(screen.width() // 2, screen.height() // 2)

    def activate(self):
        self.raise_()
        self.show()
        self.activateWindow()
        self.setFocus()

    def deactivate(self):
        self.hide()

    def change_state(self, new_state: Literal["show", "hide", "invert"] = "invert"):
        if new_state == "invert":
            new_state = "show" if self.isHidden() else "hide"
        old_state = "show" if self.isVisible() else "hide"

        if old_state == new_state:
            return

        # only show or hide the window if animations are disabled
        if not self.ui_config.theme.has_animations:
            logger.debug(f"Setting state to {new_state} (no animations)")
            self.move(self.top_left)
            if new_state == "hide":
                self.deactivate()
            elif new_state == "show":
                self.activate()
            return

        # if any animation is running, return:
        if (self.fade_up_animation.state() == QPropertyAnimation.State.Running or
                self.fade_down_animation.state() == QPropertyAnimation.State.Running):
            logger.debug("Animation is already running")
            return

        logger.debug(f"Setting state to {new_state} (with animations)")

        up = self.up_geometry()
        down = self.down_geometry()
        self.show()
        if new_state == "show":
            logger.debug(f"Showing window")
            self.ui_config.config_fade_animation(self.fade_up_animation, down, up)
            self.fade_up_animation.start()
        else:
            logger.debug(f"Hiding window")
            self.ui_config.config_fade_animation(self.fade_down_animation, up, down)
            self.fade_down_animation.start()
