import logging
import threading
from typing import List, Tuple, Type, Callable, Generator, Literal, Any

from PyQt6 import QtCore
from PyQt6.QtCore import QPoint, Qt, QRect, QPropertyAnimation, QTimer, QThread, QObject, QEvent, QEasingCurve
from PyQt6.QtGui import QFocusEvent, QCursor
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication, QLabel, QPushButton

from brightify import app_name, root_dir
from brightify.SensorComm import SensorComm
from brightify.monitors.finder import get_supported_monitors
from brightify.ui_config import MonitorRow
from brightify.ui_config import UIConfig, Theme
from brightify.monitors.MonitorBase import MonitorBase
from brightify.monitors.MonitorDDCCI import MonitorDDCCI
from brightify.monitors.MonitorUSB import MonitorUSB

# use global logger
logger = logging.getLogger(app_name)


class BaseApp(QMainWindow):
    """
    The main application window that contains all MonitorRows.
    """

    def __init__(self, theme_cb: Callable[[], Theme], parent=None):
        super(BaseApp, self).__init__(parent, Qt.WindowType.Tool)

        # The rows contain one MonitorRow for each supported Monitor connected
        self.rows: QVBoxLayout = QVBoxLayout()
        self.central_widget = QWidget(self)
        self.central_widget.setLayout(self.rows)
        self.setCentralWidget(self.central_widget)

        # Lock for animations, rapid clicks can cause multiple animations to run at the same time
        self.__anim_lock: threading.Lock = threading.Lock()
        # Store the top left corner given by the OS to be used to position the window
        self.__top_left: QPoint | None = None
        self.__get_theme = theme_cb
        self.__ui_config: UIConfig = UIConfig()
        self.__sensor_comm = SensorComm()

        # Start timer that reads sensor data every 500ms
        self.__sensor_thread = QThread()
        self.__sensor_comm.moveToThread(self.__sensor_thread)

        self.__sensor_timer = QTimer(self)
        self.__sensor_timer.timeout.connect(self.__sensor_comm.update_signal.emit)
        self.__sensor_timer.timeout.connect(self.update_ui_from_sensor)

        # Animations:
        self.fade_up_animation = QPropertyAnimation(self, b"geometry")
        self.fade_up_animation.finished.connect(self.__anim_lock.release)
        self.fade_up_animation.finished.connect(self.activateWindow)
        self.fade_up_animation.finished.connect(self.setFocus)

        self.fade_down_animation = QPropertyAnimation(self, b"geometry")
        self.fade_down_animation.finished.connect(self.__anim_lock.release)
        self.fade_down_animation.finished.connect(self.clearFocus)
        self.fade_down_animation.finished.connect(self.hide)

        # Install event filter on the application to detect when the window loses focus
        QApplication.instance().installEventFilter(self)

    @property
    def top_left(self) -> QPoint | None:
        return self.__top_left

    @top_left.setter
    def top_left(self, value: QPoint | Tuple[int, int] | Any):
        if isinstance(value, tuple):
            value = QPoint(*value)
        elif not isinstance(value, QPoint):
            raise TypeError(f"Expected QPoint or Tuple[int, int], got {type(value)}")
        self.__top_left = value

    @property
    def ui_config(self) -> UIConfig:
        return self.__ui_config

    def __config_layout(self):
        self.setWindowTitle(app_name)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.FramelessWindowHint)
        self.rows.setContentsMargins(self.ui_config.pad, self.ui_config.pad,
                                     self.ui_config.pad, self.ui_config.pad)
        self.rows.setSpacing(self.ui_config.pad)

    @staticmethod
    def __config_slider(row: MonitorRow):
        def on_change(value):
            row.brightness_label.setText(f"{value}%")

        row.slider.valueChanged.connect(lambda value: on_change(value))

    @staticmethod
    def __connect_monitor(row: MonitorRow, monitor: MonitorBase):
        initial_brightness = monitor.get_brightness(force=True)
        if initial_brightness is not None:
            row.slider.setValue(initial_brightness)
        else:
            row.slider.setValue(0)
        # for CCDDI monitors, set the brightness after releasing the slider to prevent lag
        if isinstance(monitor, MonitorDDCCI):
            row.slider.sliderReleased.connect(lambda: monitor.set_brightness(row.slider.value(), force=True))
        if isinstance(monitor, MonitorUSB):
            row.slider.valueChanged.connect(lambda value: monitor.set_brightness(value, force=True))
        row.monitor = monitor

    def __get_monitor_rows(self) -> Generator[MonitorRow, None, None]:
        for i in range(self.rows.count()):
            row = self.rows.itemAt(i).widget()
            if isinstance(row, MonitorRow):
                yield row

    def update_ui_from_sensor(self):
        monitor_rows = list(filter(lambda r: r.monitor is not None, self.__get_monitor_rows()))
        # if no sensor data is available, enable all sliders
        if not self.__sensor_comm.measurements:
            for row in monitor_rows:
                row.slider.setEnabled(True)  # enable the slider
                row.is_auto_tick.setChecked(False)  # disable the auto tick
                row.is_auto_tick.setEnabled(False)  # disable the auto tick
            return

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
        while self.rows.count():
            widget = self.rows.takeAt(0).widget()
            if isinstance(widget, MonitorRow):
                if widget.monitor is not None:
                    widget.monitor.__del__()  # delete the monitor object
                self.rows.removeWidget(widget)
                widget.hide()  # hide the widget
                widget.deleteLater()  # schedule the widget for deletion

    def run_once(self, animation: QPropertyAnimation, finished: Callable[[], Any]):
        def run_and_disconnect():
            finished()
            animation.finished.disconnect(run_and_disconnect)

        animation.finished.connect(run_and_disconnect)

    def __add_reload_button(self):

        # add a reload button to the top of self.rows
        reload_button = QPushButton("Reload", self)
        reload_button.clicked.connect(lambda: self.change_state("hide"))
        reload_button.clicked.connect(lambda: self.run_once(self.fade_down_animation, self.redraw))
        reload_button.setStyleSheet(self.ui_config.button_style)
        self.rows.addWidget(reload_button)

    def __load_rows(self):
        self.clear_rows()
        max_name_width = 0
        max_type_width = 0
        monitors: List[MonitorBase] = get_supported_monitors()
        if not monitors:
            logger.warning("No monitors were found - try to reconnect the monitor")
            return

        self.__add_reload_button()

        for m in monitors:
            logger.info(f"Adding monitor: {m.name()}")
            row = MonitorRow(self.ui_config.theme, parent=self)
            row.slider.setRange(m.min_brightness, m.max_brightness)
            row.name_label.setText(m.name())
            self.__config_slider(row)
            self.__connect_monitor(row, m)
            self.rows.addWidget(row)
            max_name_width = max(max_name_width, row.name_label.minimumSizeHint().width())
            max_type_width = max(max_type_width, row.type_label.minimumSizeHint().width())

        # set the minimum width of the name labels to the maximum width over all labels
        for row in self.__get_monitor_rows():
            row.name_label.setMinimumWidth(max_name_width + 5)
            row.type_label.setMinimumWidth(max_type_width + 5)
            row.show()

    def __update_theme(self):
        theme = self.__get_theme()
        if self.ui_config.theme == theme:
            logger.debug("No theme update needed")
            return
        self.ui_config.theme = theme
        logger.debug(f"Theme updated to: {theme}")

    def redraw(self):
        if self.top_left is None:
            logger.warning("Top left corner not set, cannot position the window. Using default position.")
            screen = QApplication.primaryScreen().availableGeometry()
            self.top_left = QPoint(screen.width() // 2, screen.height() // 2)
        logger.debug("Redrawing the app")
        self.__update_theme()
        self.__config_layout()
        self.setStyleSheet(self.ui_config.style_sheet)
        self.__load_rows()
        self.move(self.top_left)
        # start the sensor thread if it is not running
        if not self.__sensor_thread.isRunning():
            logger.debug("Starting sensor thread")
            self.__sensor_thread.start()
        # start the sensor timer if it is not running
        if not self.__sensor_timer.isActive():
            logger.debug("Starting sensor timer")
            self.__sensor_timer.start(250)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.WindowDeactivate and obj is self:
            # The application window has lost focus
            self.change_state("hide")
            return True  # Event was handled
        return super().eventFilter(obj, event)

    def change_state(self, new_state: Literal["show", "hide", "invert"] = "invert"):
        if self.top_left is None:
            logger.error("Top left corner not set")
            return
        # prevent multiple animations
        if self.__anim_lock.locked():
            return

        # lock the animation
        self.__anim_lock.acquire()
        if new_state == "invert":
            new_state = "show" if self.geometry().topLeft() != self.top_left else "hide"
        # TODO verify that screen rotation does not affect the animation on darwin and linux
        up = QRect(self.top_left, QPoint(self.top_left.x() + self.minimumSizeHint().width(),
                                         self.top_left.y() + self.minimumSizeHint().height()))

        down = QRect(QPoint(self.top_left.x(), self.top_left.y() + self.minimumSizeHint().height()),
                     QPoint(self.top_left.x() + self.minimumSizeHint().width(),
                            self.top_left.y() + 2 * self.height()))
        # make visible before animating
        self.show()
        if new_state == "show":
            logger.debug(f"Showing window")
            self.ui_config.config_fade_animation(self.fade_up_animation, down, up)
            self.fade_up_animation.start()
        else:
            logger.debug(f"Hiding window")
            self.ui_config.config_fade_animation(self.fade_down_animation, up, down)
            self.fade_down_animation.start()

        self.updateGeometry()
