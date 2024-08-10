import logging
from typing import List, Tuple, Callable, Generator, Literal, Any

from PyQt6 import QtCore
from PyQt6.QtCore import QPoint, Qt, QRect, QPropertyAnimation, QTimer, QThread, QObject, QEvent, QCoreApplication
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication, QPushButton

from brightify import app_name
from brightify.SensorComm import SensorComm
from brightify.monitors.finder import get_supported_monitors
from brightify.ui_config import MonitorRow
from brightify.ui_config import UIConfig, Theme
from brightify.monitors.MonitorBase import MonitorBase
from brightify.monitors.MonitorDDCCI import MonitorDDCCI

# use global logger
logger = logging.getLogger(app_name)


class BaseApp(QMainWindow):
    """
    The main application window that contains all MonitorRows.
    """

    def __init__(self, theme_cb: Callable[[], Theme], os_managed=False, parent=None):
        super(BaseApp, self).__init__(parent, Qt.WindowType.Tool)

        # The rows contain one MonitorRow for each supported Monitor connected
        self.rows: QVBoxLayout = QVBoxLayout()
        self.monitor_rows: List[MonitorRow] = []  # initialized on redraw
        self.central_widget = QWidget(self)
        self.central_widget.setLayout(self.rows)
        self.setCentralWidget(self.central_widget)

        # On a state change (show/hide), prevent multiple clicks by waiting for
        self.__click_lock: QTimer = QTimer(self)
        self.__click_lock.setSingleShot(True)
        self.__os_managed = os_managed

        self.__top_left: QPoint | None = None
        self.__get_theme = theme_cb
        self.__ui_config: UIConfig = UIConfig()
        self.__sensor_comm = SensorComm()

        self.__sensor_thread = QThread()
        self.__sensor_comm.moveToThread(self.__sensor_thread)
        self.__sensor_timer = QTimer(self)
        self.__sensor_timer.timeout.connect(self.__sensor_comm.update_signal.emit)
        self.__sensor_timer.timeout.connect(self.update_ui_from_sensor)

        # Animations:
        self.fade_up_animation = QPropertyAnimation(self, b"geometry")
        self.fade_up_animation.finished.connect(self.__click_lock.stop)
        self.fade_up_animation.finished.connect(self.activateWindow)
        self.fade_up_animation.finished.connect(self.setFocus)

        self.fade_down_animation = QPropertyAnimation(self, b"geometry")
        self.fade_down_animation.finished.connect(self.__click_lock.stop)
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
    def __connect_monitor(row: MonitorRow, monitor: MonitorBase) -> bool:
        try:
            initial_brightness = monitor.get_brightness(force=True)
        except Exception as e:
            logger.error(f"Failed to get initial brightness for {monitor.name()}: {e}. Dropping monitor.")
            return False

        if initial_brightness is not None:
            row.slider.setValue(initial_brightness)
        else:
            row.slider.setValue(0)
        # for DDCCI monitors, set the brightness after releasing the slider to prevent lag
        if isinstance(monitor, MonitorDDCCI):
            row.slider.sliderReleased.connect(lambda: monitor.set_brightness(row.slider.value(), force=True))
        else:
            row.slider.valueChanged.connect(lambda value: monitor.set_brightness(value, force=True))
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
        if not monitors:
            logger.warning("No monitors were found - try to reconnect the monitor")
            return

        self.__add_reload_button()

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

    def __update_theme(self):
        theme = self.__get_theme()
        if self.ui_config.theme == theme:
            logger.debug("No theme update needed")
            return
        self.ui_config.theme = theme
        logger.debug(f"Theme updated to: {theme}")

    def redraw(self):
        if self.top_left is None:
            self.top_left = self.default_position()
        logger.debug("Redrawing the app")
        self.__update_theme()
        self.__config_layout()
        self.setStyleSheet(self.ui_config.style_sheet)
        self.__load_rows()
        self.move(self.top_left)
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

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        # If not OS managed, an outside click should not do anything
        if event.type() == QEvent.Type.WindowDeactivate and obj is self:
            self.change_state("hide")
        return super().eventFilter(obj, event)

    @staticmethod
    def default_position():
        screen = QApplication.primaryScreen().availableGeometry()
        logger.debug("Requesting default position for window")
        return QPoint(screen.width() // 2, screen.height() // 2)

    def __activate(self):
        self.raise_()
        self.show()
        self.activateWindow()
        self.setFocus()

    def __deactivate(self):
        self.clearFocus()
        self.hide()

    def change_state(self, new_state: Literal["show", "hide", "invert"] = "invert"):
        if self.top_left is None:
            self.top_left = self.default_position()

        # prevent multiple animations
        if self.__click_lock.isActive():
            return

        self.__click_lock.start(self.ui_config.animation_duration)

        if new_state == "invert":
            new_state = "show" if self.isHidden() else "hide"

        up = QRect(self.top_left, QPoint(self.top_left.x() + self.minimumSizeHint().width(),
                                         self.top_left.y() + self.minimumSizeHint().height()))
        down = QRect(QPoint(self.top_left.x(), self.top_left.y() + self.minimumSizeHint().height()),
                     QPoint(self.top_left.x() + self.minimumSizeHint().width(),
                            self.top_left.y() + 2 * self.height()))
        # only show or hide the window if animations are disabled
        if not self.ui_config.theme.has_animations:
            if new_state == "show":
                self.setGeometry(up)
                self.__activate()
            else:
                self.setGeometry(down)
                self.__deactivate()
            return

        # TODO verify that screen rotation does not affect the animation on darwin and linux
        # make visible before animating
        self.show()
        if new_state == "show":
            self.ui_config.config_fade_animation(self.fade_up_animation, down, up)
            self.fade_up_animation.start()
        else:
            self.ui_config.config_fade_animation(self.fade_down_animation, up, down)
            self.fade_down_animation.start()

        self.updateGeometry()
