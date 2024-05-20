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
    parser = argparse.ArgumentParser(description=app_name)
    subparsers = parser.add_subparsers(dest="command", help="The command to run. Defaults to 'run' if not specified.")
    parser.set_defaults(command="run")

    # python -m brightify run
    run_parser = subparsers.add_parser("run",
                                       help="Runs Brightify. This is the default command if no other is specified.")

    # python -m brightify add
    add_parser = subparsers.add_parser("add", help="Add Brightify to the system.")

    # python -m brightify remove
    remove_parser = subparsers.add_parser("remove", help="Remove Brightify from the system.")

    # python -m brightify add {startup, menu-icon, all}
    add_remove_actions = ["startup", "menu-icon", "all"]
    add_parser.add_argument("action", choices=add_remove_actions, help="The action to perform. ")
    # python -m brightify add {startup, menu-icon, all} [--force-console] [--use-scheduler]
    add_parser.add_argument("--force-console", action="store_true", default=False,
                            help="Always show the console when starting the app via task / icon etc.")

    # OSs have a scheduler (Linux has cron, Windows has task scheduler, etc.)
    # TODO way to specify the scheduler?
    use_scheduler = {"action": "store_true", "default": False,
                     "help": "Use the OS scheduler. On Windows, this will create a task in the task scheduler, which requires elevated permissions. Ignored when targeting menu icon."}
    add_parser.add_argument("--use-scheduler", **use_scheduler)

    # python -m brightify remove {startup, menu-icon, all} [--use-scheduler]
    remove_parser.add_argument("action", choices=add_remove_actions, help="The action to perform.")
    remove_parser.add_argument("--use-scheduler", **use_scheduler)

    return parser.parse_args()


def run():
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
            from brightify.windows.actions import elevated_add_startup_task
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
            from brightify.windows.actions import elevated_remove_startup_task
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
            from brightify.windows.actions import add_startup_icon
            add_startup_icon(force_console)
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
            from brightify.windows.actions import remove_startup_folder
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
            from brightify.windows.actions import add_menu_icon
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
            from brightify.windows.actions import remove_menu_icon
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
    sys.excepthook = excepthook
    args = parse_args()
    # Thanks to no fall-through in match-case, have fun reading this...
    if args.command == "add":
        if args.action in ["startup", "all"]:
            if args.use_scheduler:
                logger.debug("Adding startup task")
                add_startup_task(args.force_console)
            else:
                logger.debug("Adding startup icon")
                add_startup_icon(args.force_console)
        if args.action in ["menu-icon", "all"]:
            logger.debug("Adding menu icon")
            add_menu_icon(args.force_console)
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
        run()
