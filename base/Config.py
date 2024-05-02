import logging
import os
import platform
import sys
from pathlib import Path
from typing import Literal


class Config:
    # The name of the app
    app_name: str = "Brightify"

    # The host operating system
    host_os: Literal["Windows", "Darwin", "Linux"] | str = platform.system()

    # The root directory of the project (static)
    root_dir: Path = Path(__file__).parent.parent

    # The lib directory of the project
    lib_dir = os.path.join(sys.prefix, 'Lib')

    # The root logger for the project
    root_logger = logging.getLogger("Brightify")
