import platform
from pathlib import Path
from typing import Literal, Tuple, Optional

app_name: str = str(__package__).capitalize()

# The host operating system
host_os: Literal["Windows", "Darwin", "Linux"] | str = platform.system()

# The root directory of the project (static)
root_dir: Path = Path(__file__).parent

# The res directory
res_dir: Path = root_dir / "res"

# The icon paths
icon_light: Path = res_dir / "icon_light.ico"
icon_dark: Path = res_dir / "icon_dark.ico"


# Events that can be emitted by the operating system
class OSEvent:
    theme = None  # if not None, the theme has changed
    force_redraw: bool = False  # force the app to redraw
    bottom_right: Optional[Tuple[int, int]] = None  # the bottom right corner of the app
    last_click: Optional[Tuple[int, int]] = None  # the last click position
    click_on_icon: bool = False  # last_click was on the icon
