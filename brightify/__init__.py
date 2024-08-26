import argparse
import platform
from pathlib import Path
from typing import Literal, Tuple, Optional

app_name: str = str(__package__).capitalize()

# The host operating system
host_os: Literal["Windows", "Darwin", "Linux"] | str = platform.system()

# The root directory of the pip project (brightify)
brightify_dir: Path = Path(__file__).parent

res_dir: Path = brightify_dir / "res"

log_dir: Path = brightify_dir / "logs"

# The icon paths
icon_light: Path = res_dir / "icon_light.ico"
icon_dark: Path = res_dir / "icon_dark.ico"


# Events that can be emitted by the operating system
class OSEvent:
    locked = False
    theme = None  # if not None, the theme has changed
    force_redraw: bool = False  # force the app to redraw
    bottom_right: Optional[Tuple[int, int]] = None  # the bottom right corner of the app
    last_click: Optional[Tuple[int, int]] = None  # the last click position
    click_on_icon: bool = False  # last_click was on the icon


def parse_args() -> argparse.Namespace | None:
    def _add_to_parsers(_subparsers, _arg_name, _d):
        for _s in _subparsers:
            _s.add_argument(_arg_name, **_d)

    # Exit on error does not catch unknown arguments (https://github.com/python/cpython/issues/103498)
    parser = argparse.ArgumentParser(description=app_name, exit_on_error=False)
    subparsers = parser.add_subparsers(dest="command", help="The command to run. Defaults to 'run' if not specified.")

    # python -m brightify run
    run_parser = subparsers.add_parser("run",
                                       help="Runs Brightify from console.")
    # python -m brightify add
    add_parser = subparsers.add_parser("add", help="Add Brightify to the system.")

    # python -m brightify remove
    remove_parser = subparsers.add_parser("remove", help="Remove Brightify from the system.")

    # python -m brightify add {startup, menu-icon, all}
    add_remove_actions = ["startup", "menu-icon", "all"]

    # python -m brightify add {startup, menu-icon, all} [--force-console] [--use-scheduler] [--disable-animations]
    force_console = {"action": "store_true", "default": False,
                     "help": "Always show the console when starting the app via task / icon etc."}

    no_animation = {"action": "store_true", "default": False,
                    "help": "Disable animations. If the OS does not support icons in the system tray, this will be ignored - it never has animations."}

    backend = {"choices": ["python", "c++"], "default": "python",
               "help": "The backend to use. The C++ backend is the default as it is faster and more reliable. Switch to Python if you experience issues."}

    _add_to_parsers([add_parser, run_parser], "--no-animations", no_animation)
    _add_to_parsers([add_parser, run_parser], "--force-console", force_console)
    _add_to_parsers([add_parser, run_parser], "--backend", backend)

    # OSs have a scheduler (Linux has cron, Windows has task scheduler, etc.)
    use_scheduler = {"action": "store_true", "default": False,
                     "help": "Use the OS scheduler. On Windows, this will create a task in the task scheduler, which requires elevated permissions. Ignored when targeting menu icon."}

    # python -m brightify remove {startup, menu-icon, all} [--use-scheduler]
    _add_to_parsers([add_parser, remove_parser], "--use-scheduler", use_scheduler)
    _add_to_parsers([add_parser, remove_parser], "action",
                    {"choices": add_remove_actions, "help": "The action to perform."})

    try:
        return parser.parse_args()
    except SystemExit as _:
        return None
