from contextlib import ExitStack
from typing import List, Tuple, Literal, Callable

from PyQt6 import QtCore
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QWidget, QMainWindow, QSlider, QCheckBox, QLabel

from base.Config import Config
from base.UIConfig import UIConfig
from base.UIConfig import light_mode_ui, dark_mode_ui
from base.misc import get_supported_monitors

import logging

from monitors.MonitorBase import MonitorBase

# use global logger
logger = logging.getLogger(Config.app_name)


class MonitorRow:
    name_label: QLabel
    slider: QSlider
    brightness_label: QLabel
    is_auto_tick: QCheckBox
    monitor: MonitorBase


class BaseApp(QMainWindow):
    def __init__(self, config: Config, exit_stack: ExitStack, mode_callback: Callable[[], Literal["dark", "light"]],
                 parent=None):
        super(BaseApp, self).__init__(parent)
        # the internal state of the app, dark mode by default
        self.config: Config = config
        self.exit_stack: ExitStack = exit_stack
        self.__mode_callback = mode_callback
        self.__rows: List[MonitorRow] = []
        self.__monitors: List[MonitorBase] = []
        self.__ui_config: UIConfig | None = None

    @property
    def ui_config(self) -> UIConfig:
        return self.__ui_config

    def __set_window_properties(self):
        self.setWindowTitle(self.config.app_name)
        self.setWindowIcon(QIcon(str(self.__ui_config.icon_path)))
        self.resize(self.__ui_config.window_width, self.__ui_config.window_height)
        if not self.__ui_config.resizeable:
            self.setFixedSize(self.__ui_config.window_width, self.__ui_config.window_height)
        else:
            self.setMinimumSize(self.__ui_config.min_width, self.__ui_config.min_height)

    def __set_style(self):
        self.setStyleSheet(f"""
            background-color: {self.__ui_config.bg_color};
            color: {self.__ui_config.text_color};
        """)

    def __load_rows(self):
        self.exit_stack.pop_all()  # TODO what if the OS app put elements in here?
        self.__monitors.clear()

        for m in get_supported_monitors():
            self.__monitors.append(m)
            self.exit_stack.push(m)
        print(m)

    def redraw(self):
        self.__ui_config = dark_mode_ui() if self.__mode_callback() == "dark" else light_mode_ui()
        self.__set_window_properties()
        self.__set_style()
        self.__load_rows()

    def move(self, a0: QPoint | Tuple[int, int]) -> None:
        dest = None
        if isinstance(a0, Tuple) and len(a0) == 2 and isinstance(a0[0], int) and isinstance(a0[1], int):
            x, y = a0
            dest = QPoint(x, y)
        elif isinstance(a0, QPoint):
            dest = a0
        else:
            return
            # TODO log invalid input
        return super().move(dest)

    def exit(self):
        pass
