import threading
import logging
import sys
import argparse
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from brightify import app_name, host_os, root_dir
from brightify.BaseApp import BaseApp
from brightify.Brightylog import configure_logging, start_logging

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
    parser = argparse.ArgumentParser(description="Brightify")
    subparsers = parser.add_subparsers(dest="command", help="The command to run. Defaults to 'run' if not specified.")

    subparsers.add_parser("run", help="Runs Brightify. This is the default command if no other is specified.")
    parser.set_defaults(command="run")

    add_parser = subparsers.add_parser("add", help="Add Brightify to the system.")
    add_subparsers = add_parser.add_subparsers(dest="action")

    startup_parser = add_subparsers.add_parser("startup",
                                               help="Start Brightify on startup. Defaults to adding a shortcut to the startup folder which requires no elevated permissions.")
    add_subparsers.add_parser("menu-icon", help="Add a shortcut to the start menu.")

    modes = ["task-scheduler", "startup-folder"]
    mode = {"choices": modes, "default": "startup-folder",
            "help": "How the OS starts the app. Defaults to a shortcut in the startup folder."}
    startup_parser.add_argument("--mode", **mode)

    add_parser.add_argument("--force-console", action="store_true", default=False,
                            help="Always show the console when starting the app via task / icon etc.")

    # brightify remove action
    remove_parser = subparsers.add_parser("remove", help="Remove Brightify from the system.")
    remove_subparsers = remove_parser.add_subparsers(dest="action")
    remove_startup_parser = remove_subparsers.add_parser("startup", help="Remove Brightify from startup.")
    remove_startup_parser.add_argument("--mode", **mode)
    remove_subparsers.add_parser("menu-icon", help="Remove the start menu shortcut.")

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


def add_startup_task(force_console):
    match host_os:
        case "Windows":
            from brightify.scripts.windows.actions import elevated_add_startup_task
            elevated_add_startup_task(force_console)
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


def add_startup_icon(force_console):
    match host_os:
        case "Windows":
            from brightify.scripts.windows.actions import add_startup_icon
            add_startup_icon(force_console)
        case "Linux":
            raise NotImplementedError("Not implemented yet")
        case "Darwin":
            raise NotImplementedError("Not implemented yet")
        case _:
            logger.error(f"Unsupported OS: {host_os}")
            exit(1)


def remove_startup_folder():
    match host_os:
        case "Windows":
            from brightify.scripts.windows.actions import remove_startup_folder
            remove_startup_folder()
        case "Linux":
            raise NotImplementedError("Not implemented yet")
        case "Darwin":
            raise NotImplementedError("Not implemented yet")
        case _:
            logger.error(f"Unsupported OS: {host_os}")
            exit(1)


def add_menu_icon(force_console):
    match host_os:
        case "Windows":
            from brightify.scripts.windows.actions import add_menu_icon
            add_menu_icon(force_console)
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
            from brightify.scripts.windows.actions import remove_menu_icon
            remove_menu_icon()
        case "Linux":
            raise NotImplementedError("Not implemented yet")
        case "Darwin":
            raise NotImplementedError("Not implemented yet")
        case _:
            logger.error(f"Unsupported OS: {host_os}")
            exit(1)


if __name__ == '__main__':
    _args = parse_args()
    # for writing logs before logging is configured
    install_log = root_dir / "logs" / "install.log"
    Path(install_log).parent.mkdir(parents=True, exist_ok=True)
    try:
        configure_logging()
        start_logging()
        logger.critical("Brightify started")
    except Exception as e:
        with open(install_log, "a+") as f:
            f.write("Failed to configure logging\n")
            f.write(str(e) + "\n")

    match _args.command:
        case "add":
            match _args.action:
                case "startup":
                    match _args.mode:
                        case "task-scheduler":
                            add_startup_task(_args.force_console)
                        case "startup-folder":
                            add_startup_icon(_args.force_console)
                case "menu-icon":
                    add_menu_icon(_args.force_console)
        case "remove":
            match _args.action:
                case "startup":
                    match _args.mode:
                        case "task-scheduler":
                            remove_startup_task()
                        case "startup-folder":
                            remove_startup_folder()
                case "menu-icon":
                    remove_menu_icon()
        case _:
            run()
