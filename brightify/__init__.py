# The name of the app
import platform
from pathlib import Path
from typing import Literal

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
