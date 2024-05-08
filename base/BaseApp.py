import random
import threading
from contextlib import ExitStack
from typing import List, Tuple, Literal, Callable, Optional

from PyQt6 import QtCore
from PyQt6.QtCore import QPoint, Qt, QRect, QPropertyAnimation
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout

from base.Config import Config
from base.UIConfig import UIConfig, Theme
from base.UIConfig import MonitorRow

import logging

from base.misc import get_supported_monitors
from monitors.MonitorBase import MonitorBase

# use global logger
logger = logging.getLogger(Config.app_name)


class BaseApp(QMainWindow):
    def __init__(self, config: Config, exit_stack: ExitStack,
                 get_theme: Callable[[], Theme],
                 parent=None):
        super(BaseApp, self).__init__(parent, Qt.WindowType.Tool)

        self.config: Config = config
        self.exit_stack: ExitStack = exit_stack

        # The rows contain one MonitorRow for each supported Monitor connected
        self.rows: QVBoxLayout = QVBoxLayout()
        self.central_widget = QWidget(self)
        self.central_widget.setLayout(self.rows)
        self.setCentralWidget(self.central_widget)

        self.__fade_lock: threading.Lock = threading.Lock()
        self.__top_left: QPoint | None = None
        self.__get_theme = get_theme
        self.__monitors: List[MonitorBase] = []
        self.__ui_config: UIConfig = UIConfig()

        # Animations:
        self.fade_animation = QPropertyAnimation(self, b"geometry")
        self.fade_animation.finished.connect(lambda: self.__fade_lock.release())

    @property
    def ui_config(self) -> UIConfig:
        return self.__ui_config

    def __set_window_properties(self):
        self.setWindowTitle(self.config.app_name)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.FramelessWindowHint)

    def __config_slider(self, row: MonitorRow):
        def on_change(value):
            logger.debug(f"Slider value of {row.name_label.text()} changed to {value}")
            row.brightness_label.setText(f"{value}%")

        row.slider.valueChanged.connect(lambda value: on_change(value))

    def __config_auto_tick(self, row: MonitorRow):
        def on_change(state):
            logger.debug(f"Auto of {row.name_label.text()} set to {state}")

        row.is_auto_tick.stateChanged.connect(lambda state: on_change(state))

    def __connect_monitor(self, row: MonitorRow, monitor: MonitorBase):
        row.slider.setValue(monitor.get_brightness())
        row.slider.valueChanged.connect(monitor.set_brightness)
        # TODO connect the auto tick

    def __load_rows(self):
        self.exit_stack.pop_all()
        self.__monitors.clear()
        self.rows.setSpacing(self.ui_config.pad_horizontal)
        max_label_width = 0

        # if the code is in debug mode, add some random monitors
        if __debug__:  # pragma: no cover
            logger.debug("Adding random monitors")
            for i in range(8):
                row = MonitorRow(self.ui_config.theme, self)
                monitor_name = f"Monitor {str(i).zfill(random.randint(1, 5))}"
                row.name_label.setText(monitor_name)
                max_label_width = max(max_label_width, row.name_label.minimumSizeHint().width())
                self.__config_slider(row)
                self.__config_auto_tick(row)
                row.slider.setValue(random.randint(0, 100))
                self.rows.addWidget(row)
                row.show()
        else:
            for m in get_supported_monitors():
                self.__monitors.append(m)
                self.exit_stack.push(m)
                row = MonitorRow(self.ui_config.theme, self)
                row.slider.setRange(m.min_brightness, m.max_brightness)
                row.name_label.setText(m.name)
                max_label_width = max(max_label_width, row.name_label.minimumSizeHint().width())
                self.__config_slider(row)
                self.__config_auto_tick(row)
                self.__connect_monitor(row, m)

                self.rows.addWidget(row)
                row.show()

        # set the minimum width of the name labels to the maximum width over all labels
        for i in range(self.rows.count()):
            row = self.rows.itemAt(i).widget()
            if isinstance(row, MonitorRow):
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
        self.__set_window_properties()
        self.setStyleSheet(self.ui_config.style_sheet)
        self.__load_rows()

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
        if self.__fade_lock.locked():
            return

        # lock the animation
        self.__fade_lock.acquire()
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

    def exit(self):
        pass
