import random
import threading
from typing import List, Tuple, Literal, Callable, Optional, Dict, Generator

from PyQt6 import QtCore
from PyQt6.QtCore import QPoint, Qt, QRect, QPropertyAnimation, QTimer, QThread
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout

from base.Config import Config
from base.SensorComm import SensorComm
from base.UIConfig import UIConfig, Theme
from base.UIConfig import MonitorRow

import logging

from monitors.MonitorBase import MonitorBase
from monitors.MonitorInternal import MonitorInternal
from monitors.MonitorUSB import MonitorUSB
import atexit

# use global logger
logger = logging.getLogger(Config.app_name)


def get_supported_monitors() -> List[MonitorUSB]:
    """
    Get all MonitorBase implementations that are supported by the connected USB devices.
    :return: a list of all MonitorBase implementations instantiated with the corresponding USB Device
    """
    import os, importlib, inspect, usb1
    from typing import Type
    monitor_impls = set()
    directory = "monitors"
    for filename in os.listdir(Config.root_dir / directory):
        if not filename.endswith(".py"):
            continue
        module_name = filename.replace(".py", "")
        full_module_name = f"{directory}.{module_name}"
        try:
            module = importlib.import_module(full_module_name)
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, MonitorUSB) and obj is not MonitorUSB:
                    monitor_impls.add(obj)
        except ImportError:
            pass

    logger.info(f"Found {len(monitor_impls)} monitor implementation(s): {monitor_impls}")

    monitor_inst: List[Tuple[Type[MonitorUSB], usb1.USBDevice]] = []

    context = usb1.USBContext()
    devices = context.getDeviceList(skip_on_error=True)

    logger.info(f"Found {len(devices)} USB device(s)")

    for d in devices:
        for impl in monitor_impls:
            if impl.vid() == d.getVendorID() and impl.pid() == d.getProductID():
                monitor_inst.append((impl, d))
                break

    return [impl(d) for impl, d in monitor_inst]


class BaseApp(QMainWindow):
    def __init__(self, config: Config, theme_cb: Callable[[], Theme],
                 internal_monitor_cb: Callable[[], Optional[MonitorInternal]],
                 parent=None):
        super(BaseApp, self).__init__(parent, Qt.WindowType.Tool)

        self.config: Config = config

        # The rows contain one MonitorRow for each supported Monitor connected
        self.rows: QVBoxLayout = QVBoxLayout()
        self.central_widget = QWidget(self)
        self.central_widget.setLayout(self.rows)
        self.setCentralWidget(self.central_widget)

        self.__anim_lock: threading.Lock = threading.Lock()
        self.__top_left: QPoint | None = None
        self.__get_theme = theme_cb
        self.__get_internal_monitor = internal_monitor_cb
        self.__ui_config: UIConfig = UIConfig()
        self.__sensor_comm = SensorComm()

        # Start timer that reads sensor data every 500ms
        self.__sensor_thread = QThread()
        self.__sensor_comm.moveToThread(self.__sensor_thread)

        atexit.register(self.__sensor_thread.quit)

        self.__sensor_timer = QTimer(self)
        self.__sensor_timer.timeout.connect(self.__sensor_comm.update_signal.emit)
        self.__sensor_timer.timeout.connect(self.update_ui_from_sensor)

        # Animations:
        self.fade_animation = QPropertyAnimation(self, b"geometry")
        self.fade_animation.finished.connect(lambda: self.__anim_lock.release())

    @property
    def ui_config(self) -> UIConfig:
        return self.__ui_config

    def __config_layout(self):
        self.setWindowTitle(self.config.app_name)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.FramelessWindowHint)
        self.rows.setContentsMargins(self.ui_config.pad_horizontal, self.ui_config.pad_vertical,
                                     self.ui_config.pad_horizontal, self.ui_config.pad_vertical)
        self.rows.setSpacing(self.ui_config.pad_horizontal)

    @staticmethod
    def __config_slider(row: MonitorRow):
        def on_change(value):
            row.brightness_label.setText(f"{value}%")

        row.slider.valueChanged.connect(lambda value: on_change(value))

    @staticmethod
    def __connect_monitor(row: MonitorRow, monitor: MonitorBase):
        row.slider.setValue(monitor.get_brightness(force=True))
        row.slider.valueChanged.connect(lambda value: monitor.set_brightness(value, force=True))
        row.monitor = monitor

    def __get_monitor_rows(self) -> Generator[MonitorRow, None, None]:
        for i in range(self.rows.count()):
            row = self.rows.itemAt(i).widget()
            if isinstance(row, MonitorRow):
                yield row

    def update_ui_from_sensor(self):
        monitor_rows = filter(lambda r: r.monitor is not None, self.__get_monitor_rows())
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
                return
            # disable the slider
            row.slider.setEnabled(False)
            # lazily set the slider to the current brightness
            brightness = row.monitor.convert_sensor_readings(self.__sensor_comm.measurements)
            if brightness is not None:
                # also sets the brightness label and sends the brightness to the monitor as we connected the slider
                row.slider.setValue(brightness)

    def __load_test_rows(self):
        max_label_width = 0
        for i in range(3):
            row = MonitorRow(self.ui_config.theme, parent=self)
            monitor_name = f"Monitor({i})"
            row.name_label.setText(monitor_name)
            max_label_width = max(max_label_width, row.name_label.minimumSizeHint().width())
            self.__config_slider(row)
            row.slider.setValue(random.randint(0, 100))
            self.rows.addWidget(row)
            row.show()

    def clear_rows(self):
        while self.rows.count():
            widget = self.rows.takeAt(0).widget()
            if isinstance(widget, MonitorRow):
                if widget.monitor is not None:
                    widget.monitor.__del__()   # delete the monitor object
            if widget is not None:
                widget.deleteLater()

    def __load_rows(self):
        self.clear_rows()
        max_label_width = 0
        monitors: List[MonitorBase] = get_supported_monitors()
        internal_monitor = self.__get_internal_monitor()

        # if no monitors are connected, add some dummy monitors.
        # Make sure it uses the same code path as the real monitors
        if not monitors and not internal_monitor:  # pragma: no cover
            logger.warning(
                "No monitors were found, running in test mode. "
                "Try to reconnect the monitor (Really, this works a lot of the time)")
            self.__load_test_rows()
            return

        if internal_monitor:
            logger.info("Internal monitor found")
            monitors.append(internal_monitor)
        else:
            logger.info("No internal monitor found")

        for m in monitors:
            logger.info(f"Adding monitor: {m.name}")
            row = MonitorRow(self.ui_config.theme, parent=self)
            row.slider.setRange(m.min_brightness, m.max_brightness)
            row.name_label.setText(m.name)
            max_label_width = max(max_label_width, row.name_label.minimumSizeHint().width())
            self.__config_slider(row)
            self.__connect_monitor(row, m)
            self.rows.addWidget(row)
            row.show()

        # set the minimum width of the name labels to the maximum width over all labels
        for row in self.__get_monitor_rows():
            row.name_label.setMinimumWidth(max_label_width)

    def __update_theme(self):
        theme = self.__get_theme()
        if self.ui_config.theme == theme:
            logger.debug("No theme update needed")
            return
        self.ui_config.theme = theme
        logger.debug(f"Theme updated to: {theme}")

    def redraw(self):
        logger.debug("Redrawing the app")
        self.__update_theme()
        self.__config_layout()
        self.setStyleSheet(self.ui_config.style_sheet)
        self.__load_rows()
        # start the sensor thread if it is not running
        if not self.__sensor_thread.isRunning():
            self.__sensor_thread.start()
        # start the sensor timer if it is not running
        if not self.__sensor_timer.isActive():
            self.__sensor_timer.start(500)

    def move(self, a0: QPoint | Tuple[int, int]) -> None:
        if isinstance(a0, Tuple) and len(a0) == 2 and isinstance(a0[0], int) and isinstance(a0[1], int):
            x, y = a0
            dest = QPoint(x, y)
        elif isinstance(a0, QPoint):
            dest = a0
        else:
            logger.warning(f"Unexpected type {type(a0)}")
            return
        # store the top left corner for the animation
        self.__top_left = dest
        return super().move(dest)

    def change_state(self, new_state: Literal["show", "hide", "invert"] = "invert"):
        if self.__top_left is None:
            logger.error("Top left corner not set")
            return
        # prevent multiple animations
        if self.__anim_lock.locked():
            return

        # lock the animation
        self.__anim_lock.acquire()
        if new_state == "invert":
            new_state = "show" if self.geometry().topLeft() != self.__top_left else "hide"
        # TODO verify that screen rotation does not affect the animation on darwin and linux
        up = QRect(self.__top_left, QPoint(self.__top_left.x() + self.width(),
                                           self.__top_left.y() + self.height()))

        down = QRect(QPoint(self.__top_left.x(), self.__top_left.y() + self.height()),
                     QPoint(self.__top_left.x() + self.width(), self.__top_left.y() + 2 * self.height()))

        if new_state == "show":
            logger.debug(f"Showing window")
            self.show()
            self.activateWindow()
            self.ui_config.config_fade_animation(self.fade_animation, down, up)
            self.fade_animation.start()
        else:
            logger.debug(f"Hiding window")
            self.ui_config.config_fade_animation(self.fade_animation, up, down)
            self.fade_animation.start()

    def close(self):
        logger.info("Closing app")
        super().close()
