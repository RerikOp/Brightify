import logging
import sys
import argparse
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from brightify import app_name, host_os, brightify_dir, __version__, get_parser
from brightify.brightify_log import configure_logging, start_logging, init_logging

# use global logger
logger = logging.getLogger(app_name)


def except_hook(exc_type, exc_value, exc_tb):
    from PyQt6.QtWidgets import QApplication
    if exc_type is KeyboardInterrupt:
        logger.debug("User interrupted the program, exiting.")
        QApplication.quit()
    else:
        logger.exception("An unhandled exception occurred", exc_info=(exc_type, exc_value, exc_tb))


def exec_action(args):
    # import the actions for the different OS
    if host_os == "Windows":
        from brightify.src_py.windows.actions import run, add_startup_task, add_startup_icon, remove_startup_task, \
            remove_startup_icon, add_menu_icon, remove_menu_icon
    elif host_os == "Linux":
        from brightify.src_py.linux.actions import run, add_startup_task, add_startup_icon, remove_startup_task, \
            remove_startup_icon, add_menu_icon, remove_menu_icon
    else:
        logger.error(f"Unsupported OS: {host_os}")
        exit(1)

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
                remove_startup_icon()
        if args.action in ["menu-icon", "all"]:
            logger.debug("Removing menu icon")
            remove_menu_icon()
    elif args.command == "run":
        app = QApplication(sys.argv)
        if args.backend == "python":
            logger.info("Brightify started")
            run(app, args)
        else:
            logger.info(
                "This will in the future launch the C++ backend, which will use less power and be more reliable")
            exit(0)
    elif args.command is None:
        logger.warning(
            "No command specified, if you want to run Brightify, use 'run' as command. For more information, use --help")
        exit(0)
    else:
        logger.error(f"Unknown command: {args.command}")
        exit(1)


def main():
    # for writing logs before logging is configured
    install_log = brightify_dir / "logs" / "install.log"
    Path(install_log).parent.mkdir(parents=True, exist_ok=True)
    try:
        init_logging()
        start_logging()
    except Exception as e:
        with open(install_log, "a+") as f:
            f.write("Failed to configure logging\n")
            f.write(str(e) + "\n")

    try:
        parser = get_parser()
        args, _ = parser.parse_known_args()
    except argparse.ArgumentError as e:
        logger.warning(f"Argument parsing failed at {e}")
        exit(1)
    configure_logging(args.verbose, args.quiet)

    # set global exception hook to the generic one
    sys.excepthook = except_hook

    # if version is requested, print it and exit
    if args.version:
        print(__version__)
        exit(0)

    exec_action(args)


if __name__ == '__main__':
    main()
