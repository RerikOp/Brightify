import dataclasses
from pathlib import Path
from typing import Literal, Optional

from PyQt6 import QtCore
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QFontMetrics

from PyQt6.QtWidgets import QWidget, QSlider, QCheckBox, QLabel, QHBoxLayout

from brightify import icon_light, icon_dark
from brightify.monitors.MonitorBase import MonitorBase
from brightify.monitors.MonitorUSB import MonitorUSB
from brightify.monitors.MonitorDDCCI import MonitorDDCCI


@dataclasses.dataclass
class Theme:
    bg_color: str = dataclasses.field(default="#2A2A2A")
    text_color: str = dataclasses.field(default="white")
    accent_color: str = dataclasses.field(default="#0078D4")
    # border color is slightly darker than bg_color
    border_color: str = dataclasses.field(default="#292929")
    font: str = dataclasses.field(default="Helvetica")
    font_size: int = dataclasses.field(default=13)
    mode: Literal["light", "dark"] = dataclasses.field(default="dark")


class MonitorRow(QWidget):
    def __init__(self, theme: Theme, monitor: Optional[MonitorBase] = None, parent=None):
        super(MonitorRow, self).__init__(parent)
        self.font = QFont(theme.font, theme.font_size)

        # Create components
        self.type_label = QLabel(self, font=self.font)
        self.name_label = QLabel(self, font=self.font)
        self.slider = QSlider(self, orientation=QtCore.Qt.Orientation.Horizontal)
        self.brightness_label = QLabel(self, font=self.font)
        self.is_auto_tick = QCheckBox(self)

        # The monitor that this row represents
        self.__monitor: Optional[MonitorBase] = monitor

        # Set properties
        self.slider.setRange(0, 100)
        self.slider.setStyleSheet(self.__slider_style(theme))
        self.is_auto_tick.setStyleSheet(self.__checkbox_style(theme))

        # the brightness label should be 4 characters wide (including the % sign)
        self.brightness_label.setFixedWidth(QFontMetrics(self.font).horizontalAdvance("100%"))

        # Create layout and add components
        layout = QHBoxLayout()
        layout.addWidget(self.type_label)
        layout.addWidget(self.name_label)
        layout.addWidget(self.slider)
        layout.addWidget(self.brightness_label)
        layout.addWidget(self.is_auto_tick)

        self.setLayout(layout)

    @property
    def monitor(self):
        return self.__monitor

    @monitor.setter
    def monitor(self, value: MonitorBase):
        self.__monitor = value
        if isinstance(value, MonitorUSB):
            self.type_label.setText("[USB]")
        elif isinstance(value, MonitorDDCCI):
            self.type_label.setText("[DDCCI]")
        else:
            self.type_label.setText("[ANY]")


    @staticmethod
    def __slider_style(theme: Theme):
        return f"""
            QSlider {{
                min-height: 30px;
                max-height: 30px;
                min-width: 200px;
                max-width: 200px;
            }}
            """

    def __checkbox_style(self, theme: Theme):
        # checkmark is in the accent color
        return f"""
            QCheckBox::indicator::checked {{ 
                background-color: {theme.accent_color};
                border: 1px solid {theme.accent_color};
                width: 20px;
                height: 20px;
                border-radius: 5px;
            }}
            QCheckBox::indicator::unchecked {{ 
                background-color: {theme.bg_color};
                border: 1px solid {theme.accent_color};
                width: 20px;
                height: 20px;
                border-radius: 5px;
            }}
        """


@dataclasses.dataclass
class UIConfig:
    # Theme
    theme: Theme = dataclasses.field(default_factory=Theme)

    # Layout:
    pad_horizontal: int = 5
    pad_vertical: int = 25

    # The maximum width of the label in the MonitorRow, or -1 if unbounded
    max_label_width: int = -1

    # Icon
    _icon_path: Path = dataclasses.field(default=icon_light)

    animation_duration: int = 100

    @property
    def icon_path(self):
        return icon_light if self.theme.mode == "dark" else icon_dark

    @property
    def style_sheet(self):
        return f"""
            background-color: {self.theme.bg_color};
            color: {self.theme.text_color};
        """

    def config_fade_animation(self, fa: QPropertyAnimation,
                              start_geometry: QtCore.QRect,
                              end_geometry: QtCore.QRect):
        fa.setDuration(self.animation_duration)
        fa.setEasingCurve(QEasingCurve.Type.Linear)
        fa.setStartValue(start_geometry)
        fa.setEndValue(end_geometry)
