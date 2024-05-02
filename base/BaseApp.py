from contextlib import ExitStack
from typing import List, Tuple, Literal, Callable

from PyQt6 import QtCore
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QHBoxLayout, QWidget, QVBoxLayout

from base.Config import Config
from base.UIConfig import UIConfig
from base.UIConfig import light_theme_ui, dark_theme_ui
from base.UIConfig import MonitorRow

import logging

from monitors.MonitorBase import MonitorBase

# use global logger
logger = logging.getLogger(Config.app_name)


class BaseApp(QMainWindow):
    def __init__(self, config: Config, exit_stack: ExitStack, get_theme: Callable[[], Literal["dark", "light"]],
                 parent=None):
        super(BaseApp, self).__init__(parent, Qt.WindowType.Tool)
        # the internal state of the app, dark mode by default
        self.config: Config = config
        self.exit_stack: ExitStack = exit_stack
        self.rows: QVBoxLayout = QVBoxLayout()
        self.central_widget = QWidget(self)
        self.central_widget.setLayout(self.rows)
        self.setCentralWidget(self.central_widget)

        self.__get_theme = get_theme
        self.__monitors: List[MonitorBase] = []
        self.__ui_config: UIConfig | None = None

    @property
    def ui_config(self) -> UIConfig:
        return self.__ui_config

    def __set_window_properties(self):
        self.setWindowTitle(self.config.app_name)
        self.resize(self.ui_config.window_width, self.ui_config.window_height)
        self.setFixedSize(self.ui_config.window_width, self.ui_config.window_height)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.FramelessWindowHint)


    def __conect_slider(self, row: MonitorRow):
        def on_change(value):
            logger.debug(f"Slider value of {row.name_label.text()} changed to {value}")
            row.brightness_label.setText(f"{value}%")

        row.slider.valueChanged.connect(lambda value: on_change(value))

    def __load_rows(self):
        self.exit_stack.pop_all()
        self.__monitors.clear()

        for i in range(3):
            row = MonitorRow(self)
            self.rows.addWidget(row)
            row.name_label.setText(f"M27Q({i})")
            self.__conect_slider(row)
            row.slider.setValue(50)
            """""
            row.is_auto_tick.setText("Auto")
            row.is_auto_tick.setChecked(True)
            row.is_auto_tick.stateChanged.connect(lambda state, row=row: logger.debug(f"Auto ticked: {state}"))
            row.move(0, i * 50)"""
            row.show()

        """for m in get_supported_monitors():
            self.__monitors.append(m)
            self.exit_stack.push(m)"""

    def redraw(self):
        logger.debug("Redrawing the app")
        self.__ui_config = dark_theme_ui() if self.__get_theme() == "dark" else light_theme_ui()
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
        return super().move(dest)

    def exit(self):
        pass
