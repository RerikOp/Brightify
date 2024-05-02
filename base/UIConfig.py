import dataclasses
from pathlib import Path
from typing import Literal

from base.Config import Config


@dataclasses.dataclass
class UIConfig:
    # Colors:
    bg_color: str = dataclasses.field(default="black")
    text_color: str = dataclasses.field(default="white")
    heading_color: str = dataclasses.field(default="grey")
    accent_color: str = dataclasses.field(default="#007AD9")
    mode: Literal["dark", "light"] = dataclasses.field(default="dark")

    # Layout:
    pad: int = 15

    # Window properties
    window_width: int = 300
    window_height: int = 300
    min_width: int = 200
    min_height: int = 200
    resizeable: bool = False

    # Icon
    icon_path: Path = dataclasses.field(default=Config.root_dir / "res" / "assets" / "icon_dark.ico")





def dark_mode_ui():
    return UIConfig()


def light_mode_ui():
    return UIConfig(bg_color="white", text_color="black", heading_color="darkgrey", mode="light",
                    icon_path=Config.root_dir / "res" / "assets" / "icon_light.ico")
