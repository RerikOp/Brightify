import dataclasses
from pathlib import Path
from typing import Literal

from PyQt6 import QtCore
from PyQt6.QtGui import QFont

from base.Config import Config
from PyQt6.QtWidgets import QWidget, QMainWindow, QSlider, QCheckBox, QLabel, QHBoxLayout, QSizePolicy


class MonitorRow(QWidget):
    def __init__(self, parent=None):
        super(MonitorRow, self).__init__(parent)
        self.font = QFont('Helvetica', 15)

        self.slider_style_sheet = """
            QSlider {
                min-height: 30px;
                max-height: 30px;
                min-width: 200px;
                max-width: 200px;
            }
            
            QSlider::handle:horizontal {
                border: 10px solid #007AD9;
            }
        """

        # Create components
        self.name_label = QLabel(self, font=self.font)
        self.slider = QSlider(self, orientation=QtCore.Qt.Orientation.Horizontal)
        self.brightness_label = QLabel(self, font=self.font)
        self.is_auto_tick = QCheckBox(self)

        # Set size policy for each widget
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.brightness_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.is_auto_tick.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # apply style sheet
        self.slider.setStyleSheet(self.slider_style_sheet)

        # Create layout and add components
        layout = QHBoxLayout()
        layout.addWidget(self.name_label)
        layout.addWidget(self.slider)
        layout.addWidget(self.brightness_label)
        layout.addWidget(self.is_auto_tick)

        self.setLayout(layout)


@dataclasses.dataclass
class UIConfig:
    # Colors:
    bg_color: str = dataclasses.field(default="#2A2A2A")
    text_color: str = dataclasses.field(default="white")
    heading_color: str = dataclasses.field(default="grey")
    theme: Literal["dark", "light"] = dataclasses.field(default="dark")

    # Layout:
    pad: int = 15

    # Window properties
    window_width: int = 450
    window_height: int = 300

    # Icon
    icon_path: Path = dataclasses.field(default=Config.root_dir / "res" / "assets" / "icon_light.ico")

    # Style Sheets
    style_sheet: str = dataclasses.field(init=False)

    def __post_init__(self):
        self.style_sheet = f"""
            background-color: {self.bg_color};
            color: {self.text_color};
        """


def dark_theme_ui():
    return UIConfig()


def light_theme_ui():
    return UIConfig(bg_color="white", text_color="black", heading_color="darkgrey", theme="light",
                    icon_path=Config.root_dir / "res" / "assets" / "icon_dark.ico")
