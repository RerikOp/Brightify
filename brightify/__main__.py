import logging
import sys
import argparse
from pathlib import Path

from PyQt6.QtCore import QThread, Qt
from PyQt6.QtWidgets import QApplication

from brightify import app_name, host_os, brightify_dir, OSEvent
from brightify.src_py.BaseApp import BaseApp
from brightify.src_py.brightylog import configure_logging, start_logging

# use global logger
logger = logging.getLogger(app_name)


def excepthook(exc_type, exc_value, exc_tb):
    if exc_type is KeyboardInterrupt:
        logger.info("User interrupted the program, exiting...")
        exit(0)
    logger.exception("An unhandled exception occurred", exc_info=(exc_type, exc_value, exc_tb))


def main_win(app: QApplication, args: argparse.Namespace):
    import win32gui
    from brightify.src_py.windows.WindowsApp import WindowsApp
    os_event = OSEvent()
    base_app = BaseApp(os_event, args, window_type=Qt.WindowType.Tool)
    win_app = WindowsApp(os_event)

    class PumpMessagesThread(QThread):
        def run(self):
            logger.debug("Starting message pump")
            while True:
                win32gui.PumpWaitingMessages()

    class MouseListenerThread(QThread):
        def run(self):
            while True:
                win_app.handle_mouse_click_func()

    pump_thread = PumpMessagesThread()
    pump_thread.start()

    mouse_thread = MouseListenerThread()
    mouse_thread.start()
    ret_code = app.exec()
    logger.info(f"Exiting with code {ret_code}")
    exit(ret_code)


def main_linux(app: QApplication, args: argparse.Namespace):
    base_app = BaseApp(None, args)
    logger.warning("Linux not tested yet")
    # disable animations
    base_app.ui_config.theme.has_animations = False
    base_app.redraw()
    base_app.change_state("show")
    ret_code = app.exec()
    logger.info(f"Exiting with code {ret_code}")
    exit(ret_code)


def main_darwin(app: QApplication, args: argparse.Namespace):
    raise NotImplementedError("MacOS not supported yet")


def parse_args() -> argparse.Namespace:
    def _add_to_parsers(_subparsers, _arg_name, _d):
        for _s in _subparsers:
            _s.add_argument(_arg_name, **_d)

    parser = argparse.ArgumentParser(description=app_name)
    subparsers = parser.add_subparsers(dest="command", help="The command to run. Defaults to 'run' if not specified.")
    parser.set_defaults(command="run")

    # python -m brightify run
    run_parser = subparsers.add_parser("run",
                                       help="Runs Brightify from console. This is the default command if no other is specified.")
    # python -m brightify add
    add_parser = subparsers.add_parser("add", help="Add Brightify to the system.")

    # python -m brightify remove
    remove_parser = subparsers.add_parser("remove", help="Remove Brightify from the system.")

    # python -m brightify add {startup, menu-icon, all}
    add_remove_actions = ["startup", "menu-icon", "all"]

    # python -m brightify add {startup, menu-icon, all} [--force-console] [--use-scheduler] [--disable-animations]
    add_parser.add_argument("--force-console", action="store_true", default=False,
                            help="Always show the console when starting the app via task / icon etc.")
    no_animation = {"action": "store_true", "default": False,
                    "help": "Disable animations. If the OS does not support icons in the system tray, this will be ignored - it never has animations."}

    _add_to_parsers([add_parser, run_parser], "--no-animations", no_animation)

    # OSs have a scheduler (Linux has cron, Windows has task scheduler, etc.)
    use_scheduler = {"action": "store_true", "default": False,
                     "help": "Use the OS scheduler. On Windows, this will create a task in the task scheduler, which requires elevated permissions. Ignored when targeting menu icon."}

    # python -m brightify remove {startup, menu-icon, all} [--use-scheduler]
    _add_to_parsers([add_parser, remove_parser], "--use-scheduler", use_scheduler)
    _add_to_parsers([add_parser, remove_parser], "action",
                    {"choices": add_remove_actions, "help": "The action to perform."})

    return parser.parse_args()


def run(runtime_args: argparse.Namespace):
    app = QApplication(sys.argv)
    try:
        match host_os:
            case "Windows":
                logger.debug("Running on Windows")
                main_win(app, runtime_args)
            case "Linux":
                logger.debug("Running on Linux")
                main_linux(app, runtime_args)
            case "Darwin":
                logger.debug("Running on MacOS")
                main_darwin(app, runtime_args)
            case _:
                logger.error(f"Unsupported OS: {host_os}")
                exit(1)
    except KeyboardInterrupt:
        logger.info("User interrupted the program, exiting...")
        app.quit()


def add_startup_task(runtime_args):
    match host_os:
        case "Windows":
            from brightify.src_py.windows.actions import elevated_add_startup_task
            elevated_add_startup_task(runtime_args)
        case "Linux":
            raise NotImplementedError("Not implemented yet")
        case "Darwin":
            raise NotImplementedError("Not implemented yet")
        case _:
            logger.error(f"Unsupported OS: {host_os}")
            exit(1)


def remove_startup_task():
    match host_os:
        case "Windows":
            from brightify.src_py.windows.actions import elevated_remove_startup_task
            elevated_remove_startup_task()
        case "Linux":
            raise NotImplementedError("Not implemented yet")
        case "Darwin":
            raise NotImplementedError("Not implemented yet")
        case _:
            logger.error(f"Unsupported OS: {host_os}")
            exit(1)


def add_startup_icon(runtime_args: argparse.Namespace):
    match host_os:
        case "Windows":
            from brightify.src_py.windows.actions import add_startup_icon
            add_startup_icon(runtime_args)
        case "Linux":
            raise NotImplementedError("Not implemented yet")
        case "Darwin":
            raise NotImplementedError("Not implemented yet")
        case _:
            logger.error(f"Unsupported OS: {host_os}")
            exit(1)


def remove_startup_dir_link():
    match host_os:
        case "Windows":
            from brightify.src_py.windows.actions import remove_startup_folder
            remove_startup_folder()
        case "Linux":
            raise NotImplementedError("Not implemented yet")
        case "Darwin":
            raise NotImplementedError("Not implemented yet")
        case _:
            logger.error(f"Unsupported OS: {host_os}")
            exit(1)


def add_menu_icon(runtime_args: argparse.Namespace):
    match host_os:
        case "Windows":
            from brightify.src_py.windows.actions import add_menu_icon
            add_menu_icon(runtime_args)
        case "Linux":
            raise NotImplementedError("Not implemented yet")
        case "Darwin":
            raise NotImplementedError("Not implemented yet")
        case _:
            logger.error(f"Unsupported OS: {host_os}")
            exit(1)


def remove_menu_icon():
    match host_os:
        case "Windows":
            from brightify.src_py.windows.actions import remove_menu_icon
            remove_menu_icon()
        case "Linux":
            raise NotImplementedError("Not implemented yet")
        case "Darwin":
            raise NotImplementedError("Not implemented yet")
        case _:
            logger.error(f"Unsupported OS: {host_os}")
            exit(1)


if __name__ == '__main__':
    # for writing logs before logging is configured
    install_log = brightify_dir / "logs" / "install.log"
    Path(install_log).parent.mkdir(parents=True, exist_ok=True)
    try:
        configure_logging()
        start_logging()
        logger.critical("Brightify started")
    except Exception as e:
        with open(install_log, "a+") as f:
            f.write("Failed to configure logging\n")
            f.write(str(e) + "\n")
    sys.excepthook = excepthook
    args = parse_args()
    if args.no_animations:
        logger.debug("Animations disabled")
        animations_disabled = True

    # Thanks to no fall-through in match-case, have fun reading this...
    if args.command == "add":
        if args.action in ["startup", "all"]:
            if args.use_scheduler:
                logger.debug("Adding startup task")
                add_startup_task(args)
            else:
                logger.debug("Adding startup icon")
                add_startup_icon(args)
        if args.action in ["menu-icon", "all"]:
            logger.debug("Adding menu icon")
            add_menu_icon(args)

    elif args.command == "remove":
        if args.action in ["startup", "all"]:
            if args.use_scheduler:
                logger.debug("Removing startup task")
                remove_startup_task()
            else:
                logger.debug("Removing startup icon")
                remove_startup_dir_link()
        if args.action in ["menu-icon", "all"]:
            logger.debug("Removing menu icon")
            remove_menu_icon()
    elif args.command == "run":
        run(args)
