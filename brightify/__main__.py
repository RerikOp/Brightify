import threading
import logging
import sys
import argparse
from PyQt6.QtWidgets import QApplication

from brightify import app_name, host_os
from brightify.BaseApp import BaseApp
from brightify.Brightylog import configure_logging

# use global logger
logger = logging.getLogger(app_name)


def excepthook(exc_type, exc_value, exc_tb):
    if exc_type is KeyboardInterrupt:
        logger.info("User interrupted the program, exiting...")
        exit(0)
    logger.exception("An unhandled exception occurred", exc_info=(exc_type, exc_value, exc_tb))


def main_win(app: QApplication):
    import win32gui
    from brightify.windows.WindowsApp import WindowsApp
    from brightify.windows.helpers import get_theme

    base_app = BaseApp(get_theme)
    WindowsApp(base_app)
    threading.Thread(target=win32gui.PumpMessages, daemon=True).start()
    base_app.show()
    ret_code = app.exec()
    logger.info(f"Exiting with code {ret_code}")
    exit(ret_code)


def main_linux():
    raise NotImplementedError("Linux not supported yet")


def main_darwin():
    raise NotImplementedError("MacOS not supported yet")


def parse_args():
    actions = ["run", "add_startup_task", "remove_startup_task"]
    parser = argparse.ArgumentParser(description="Brightify")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    # No flag specifies the action, i.e. python -m brightify <action>.
    parser.add_argument("action", choices=actions, default="run", nargs="?",
                        help="The action to perform. Run the app or add/remove startup task (may require elevated permission).")
    return parser.parse_args()


def run():
    sys.excepthook = excepthook
    try:
        app = QApplication(sys.argv)
        match host_os:
            case "Windows":
                logger.debug("Running on Windows")
                main_win(app)
            case "Linux":
                logger.debug("Running on Linux")
                main_linux()
            case "Darwin":
                logger.debug("Running on MacOS")
                main_darwin()
            case _:
                logger.error(f"Unsupported OS: {host_os}")
                exit(1)
    except KeyboardInterrupt:
        logger.info("User interrupted the program, exiting...")
        exit(0)


def add_startup_task():
    match host_os:
        case "Windows":
            from brightify.scripts.windows.actions import elevated_add_startup_task
            elevated_add_startup_task()
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
            from brightify.scripts.windows.actions import elevated_remove_startup_task
            elevated_remove_startup_task()
        case "Linux":
            raise NotImplementedError("Not implemented yet")
        case "Darwin":
            raise NotImplementedError("Not implemented yet")
        case _:
            logger.error(f"Unsupported OS: {host_os}")
            exit(1)


if __name__ == '__main__':
    args = parse_args()
    configure_logging()
    logger.debug("Logging configured")

    # Check which action to perform
    match args.action:
        case "run":
            run()
        case "add_startup_task":
            add_startup_task()
        case "remove_startup_task":
            remove_startup_task()
        case _:
            logger.error(f"Unsupported action: {args.action}")
            exit(1)
