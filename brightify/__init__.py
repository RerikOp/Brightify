import argparse
import platform
from pathlib import Path
from typing import Literal, Tuple, Optional
from importlib.metadata import version, PackageNotFoundError

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

__version__ = "Unknown"
try:
    __version__ = version(app_name)
except PackageNotFoundError as _:
    pass


# Events that can be emitted by the operating system
class OSEvent:
    locked = False
    theme = None  # if not None, the theme has changed
    force_redraw: bool = False  # force the app to redraw
    bottom_right: Optional[Tuple[int, int]] = None  # the bottom right corner of the app
    last_click: Optional[Tuple[int, int]] = None  # the last click position
    click_on_icon: bool = False  # last_click was on the icon
    exit_requested: bool = False  # the user requested to exit the app


def get_parser() -> argparse.ArgumentParser:
    def _add_to_parsers(_subparsers, _arg_names, _d):
        if isinstance(_arg_names, str):
            _arg_names = [_arg_names]
        for _s in _subparsers:
            _s.add_argument(*_arg_names, **_d)

    # Base parser for common arguments
    base_parser = argparse.ArgumentParser(add_help=False)
    verbose_arg = {"action": "store_true", "help": "Enable verbose logging."}
    quiet_arg = {"action": "store_true", "help": "Disable logging."}
    _add_to_parsers([base_parser], ("-v", "--verbose"), verbose_arg)
    _add_to_parsers([base_parser], ("-q", "--quiet"), quiet_arg)

    # Main parser
    parser = argparse.ArgumentParser(prog="brightify",
                                     description=f"Brightify - A tool for managing screen brightness. Version: {__version__}",
                                     exit_on_error=False, add_help=True, parents=[base_parser])

    # Add subparsers
    subparsers = parser.add_subparsers(dest="command")
    # python -m brightify run
    run_parser = subparsers.add_parser("run", help="Runs Brightify from console.", parents=[base_parser])
    # python -m brightify add
    add_parser = subparsers.add_parser("add", help="Add Brightify to the system.", parents=[base_parser])
    # python -m brightify remove
    remove_parser = subparsers.add_parser("remove", help="Remove Brightify from the system.", parents=[base_parser])

    # Force the console to show
    force_console_arg = {"action": "store_true", "default": False,
                         "help": "Always show the console when starting the app via task / icon etc."}
    # The backend to use
    backend_arg = {"choices": ["python", "c++"], "default": "python",
                   "help": "The backend to use. The C++ backend is the default as it is faster and more reliable. Switch to Python if you experience issues."}
    # OSs have a scheduler (Linux has cron, Windows has task scheduler, etc.)
    use_scheduler_arg = {"action": "store_true", "default": False,
                         "help": "Use the OS scheduler. On Windows, this will create a task in the task scheduler, which requires elevated permissions. Ignored when targeting menu icon."}
    # Disable animations
    no_animation_arg = {"action": "store_true", "default": False,
                        "help": "Disable animations. If the OS does not support icons in the system tray, this will be ignored - it never has animations."}
    # Add or remove action
    action_arg = {"choices": ["startup", "menu-icon", "all"], "help": "The action to perform.", "default": "all"}

    # Distribute the arguments to the subparsers. Make sure to add any new arguments to the actions in actions.py/helpers.py
    _add_to_parsers([add_parser, run_parser], "--no-animations", no_animation_arg)
    _add_to_parsers([add_parser, run_parser], "--force-console", force_console_arg)
    _add_to_parsers([add_parser, run_parser], "--backend", backend_arg)
    _add_to_parsers([add_parser, remove_parser], "--use-scheduler", use_scheduler_arg)
    _add_to_parsers([add_parser, remove_parser], "action", action_arg)

    version_arg = {"action": "store_true", "help": "Print the version and exit."}
    _add_to_parsers([parser], "--version", version_arg)  # only the main parser so add at the end

    return parser