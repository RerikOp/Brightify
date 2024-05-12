import random
import threading
from typing import List, Tuple, Type, Callable, Generator, Optional, Literal, Dict

from PyQt6 import QtCore
from PyQt6.QtCore import QPoint, Qt, QRect, QPropertyAnimation, QTimer, QThread
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout

from brightify import app_name, root_dir
from brightify.SensorComm import SensorComm
from brightify.UIConfig import UIConfig, Theme
from brightify.UIConfig import MonitorRow

import logging

from brightify.monitors.MonitorBase import MonitorBase
from brightify.monitors.MonitorBaseImpl import MonitorBaseImpl
from brightify.monitors.MonitorUSB import MonitorUSB
import atexit

# use global logger
logger = logging.getLogger(app_name)


def _supported_usb_impls() -> List[Type[MonitorUSB]]:
    import os, importlib, inspect
    monitor_impls = set()
    directory = "monitors"
    for filename in os.listdir(root_dir / directory):
        if not filename.endswith(".py"):
            continue
        module_name = filename.replace(".py", "")
        full_module_name = f"{__package__}.{directory}.{module_name}"
        try:
            module = importlib.import_module(full_module_name)
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, MonitorUSB) and obj is not MonitorUSB:
                    monitor_impls.add(obj)
        except ImportError:
            pass
    return list(monitor_impls)


def _usb_monitors(monitor_impls: List[Type[MonitorUSB]]) -> List[MonitorUSB]:
    import usb1
    context = usb1.USBContext()
    devices = context.getDeviceList(skip_on_error=True)
    monitor_inst: List[Tuple[Type[MonitorUSB], usb1.USBDevice]] = []
    for dev in devices:
        for impl in monitor_impls:
            if impl.vid() == dev.getVendorID() and impl.pid() == dev.getProductID():
                monitor_inst.append((impl, dev))
                break

    return [impl(dev) for impl, dev in monitor_inst]


def _ddcci_monitors() -> List[MonitorBase]:
    import monitorcontrol
    monitors = monitorcontrol.get_monitors()
    supported_monitors = []

    def force_vcp_cap(monitor: monitorcontrol.Monitor) -> Dict:
        with monitor:
            for _ in range(10):
                try:
                    vcp_cap = monitor.get_vcp_capabilities()
                    return vcp_cap
                except monitorcontrol.vcp.vcp_abc.VCPError:
                    pass
        return {}

    def get_brightness_cb(monitor: monitorcontrol.Monitor):
        def get_luminance(blocking, force):
            max_tries = 1 if not blocking and not force else 10
            for _ in range(max_tries):
                with monitor:
                    try:
                        return monitor.get_luminance()
                    except monitorcontrol.vcp.vcp_abc.VCPError:
                        pass
            logger.debug(f"Failed to get luminance of CCDDI monitor")
            return None

        return lambda blocking, force: get_luminance(blocking, force)

    def set_brightness_cb(monitor: monitorcontrol.Monitor):
        def set_luminance(brightness, blocking, force):
            max_tries = 1 if not blocking and not force else 10
            for _ in range(max_tries):
                with monitor:
                    try:
                        monitor.set_luminance(brightness)
                    except monitorcontrol.vcp.vcp_abc.VCPError:
                        pass
            logger.debug(f"Failed to set luminance of CCDDI monitor")

        return lambda brightness, blocking, force: set_luminance(brightness, blocking, force)

    for monitor in monitors:
        vcp_cap = force_vcp_cap(monitor)
        name = vcp_cap.get('model', 'Monitor').upper()
        logger.info(f"Found DDCCI Monitor {name}")
        mon = MonitorBaseImpl(name,
                              get_brightness_cb(monitor),
                              set_brightness_cb(monitor))
        supported_monitors.append(mon)
    return supported_monitors


def get_supported_monitors() -> List[MonitorBase]:
    """
    Finds all user implemented MonitorUSB classes and instantiates them with the corresponding USB device.
    If a monitor without a USB device is found or an implementation is missing, we try to connect to the monitor via DDC-CI.
    :return: a list of all MonitorBase implementations
    """
    monitor_impls = _supported_usb_impls()
    usb_monitors = _usb_monitors(monitor_impls)
    logger.info(f"Found {len(usb_monitors)} USB monitor(s) with implementation: {[m.name() for m in usb_monitors]}")
    ddcci_monitors = _ddcci_monitors()
    logger.info(f"Found {len(ddcci_monitors)} DDCCI monitor(s)")
    return usb_monitors + ddcci_monitors


class BaseApp(QMainWindow):
    def __init__(self, theme_cb: Callable[[], Theme], parent=None):
        super(BaseApp, self).__init__(parent, Qt.WindowType.Tool)

        # The rows contain one MonitorRow for each supported Monitor connected
        self.rows: QVBoxLayout = QVBoxLayout()
        self.central_widget = QWidget(self)
        self.central_widget.setLayout(self.rows)
        self.setCentralWidget(self.central_widget)

        self.__anim_lock: threading.Lock = threading.Lock()
        # Store the top left corner given by the OS
        self.top_left: QPoint | None = None
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
        self.fade_animation = QPropertyAnimation(self, b"geometry")
        self.fade_animation.finished.connect(lambda: self.__anim_lock.release())

        atexit.register(self.close)

    @property
    def ui_config(self) -> UIConfig:
        return self.__ui_config

    def __config_layout(self):
        self.setWindowTitle(app_name)
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
        initial_brightness = monitor.get_brightness(force=True)
        if initial_brightness is not None:
            row.slider.setValue(initial_brightness)
        else:
            logger.debug(f"Failed to get brightness of monitor {monitor.name()}")
        # for CCDDI monitors, set the brightness after releasing the slider to prevent lag
        if isinstance(monitor, MonitorBaseImpl):
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
                    widget.monitor.__del__()  # delete the monitor object
            if widget is not None:
                widget.deleteLater()

    def __load_rows(self):
        self.clear_rows()
        max_label_width = 0
        monitors: List[MonitorBase] = get_supported_monitors()

        # if no monitors are connected, add some dummy monitors.
        # Make sure it uses the same code path as the real monitors
        if not monitors:
            logger.warning(
                "No monitors were found, running in test mode. "
                "Try to reconnect the monitor (Really, this works a lot of the time)")
            self.__load_test_rows()
            return

        for m in monitors:
            logger.info(f"Adding monitor: {m.name()}")
            row = MonitorRow(self.ui_config.theme, parent=self)
            row.slider.setRange(m.min_brightness, m.max_brightness)
            row.name_label.setText(m.name())
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
        self.hide()
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
            self.__sensor_timer.start(500)
        self.show()

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
        up = QRect(self.top_left, QPoint(self.top_left.x() + self.width(),
                                         self.top_left.y() + self.height()))

        down = QRect(QPoint(self.top_left.x(), self.top_left.y() + self.height()),
                     QPoint(self.top_left.x() + self.width(), self.top_left.y() + 2 * self.height()))

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

    def show(self):
        super().show()
        self.activateWindow()

    def close(self):
        self.__sensor_timer.stop()
        self.__sensor_comm.__del__()
        self.__sensor_thread.quit()

        logger.info("Closing app")
        super().close()
