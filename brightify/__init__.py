# The name of the app
import platform
from pathlib import Path
from typing import Literal

app_name: str = str(__package__).capitalize()

# The host operating system
host_os: Literal["Windows", "Darwin", "Linux"] | str = platform.system()

# The root directory of the project (static)
root_dir: Path = Path(__file__).parent

# The actions that can be performed by the app
actions = ["run", "add_startup_task", "remove_startup_task", "add_startup_icon", "remove_startup_icon"]
