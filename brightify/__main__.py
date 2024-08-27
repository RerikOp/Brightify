import logging
import sys
import argparse
from pathlib import Path
import atexit

from brightify import app_name, host_os, brightify_dir, OSEvent, parse_args
from brightify.src_py.BrightifyApp import BrightifyApp
from brightify.brightify_log import configure_logging, start_logging

# use global logger
logger = logging.getLogger(app_name)


def except_hook(exc_type, exc_value, exc_tb):
    from PyQt6.QtWidgets import QApplication
    if exc_type is KeyboardInterrupt:
        logger.debug("User interrupted the program, exiting.")
        QApplication.quit()
    else:
        logger.exception("An unhandled exception occurred", exc_info=(exc_type, exc_value, exc_tb))


def main_win(app, runtime_args: argparse.Namespace):
    from PyQt6.QtCore import QThread, Qt
    import win32gui
    import ctypes
    from brightify.src_py.windows.WindowsApp import WindowsApp
    os_event = OSEvent()
    brightify_app = BrightifyApp(os_event, runtime_args, window_type=Qt.WindowType.Tool)  # must be tool window to hide from taskbar
    win_app = WindowsApp(os_event)
    running = True

    class WindowsThread(QThread):
        def run(self):
            # It appears that LBUTTONDOWN is only received after LBUTTONUP. Thus, we need to poll the mouse state
            already_handled = False
            while running:
                l_button_down = ctypes.windll.user32.GetAsyncKeyState(win_app.primary_click) & 0x8000 != 0
                if l_button_down and not already_handled:  # corresponds to LBUTTONDOWN
                    already_handled = True
                elif not l_button_down and already_handled:  # corresponds to LBUTTONUP
                    os_event.locked = True  # make sure that the app does not interrupt
                    already_handled = False
                    os_event.last_click = win32gui.GetCursorPos()
                win32gui.PumpWaitingMessages()
                self.msleep(10)
                os_event.locked = False
            logger.debug("Windows thread stopped")

    def cleanup():
        nonlocal running
        if not running:
            return
        running = False
        win_app.close()
        brightify_app.close()
        windows_thread.quit()
        windows_thread.wait()
    # connect cleanup to app exit
    app.aboutToQuit.connect(cleanup)
    atexit.register(cleanup)
    windows_thread = WindowsThread()
    try:
        windows_thread.start()
        app.exec()
    finally:
        cleanup()


def main_linux(app, runtime_args: argparse.Namespace):
    base_app = BrightifyApp(None, runtime_args)
    logger.warning("Linux not tested yet")
    # disable animations
    base_app.ui_config.theme.has_animations = False
    base_app.redraw()
    base_app.change_state("show")
    ret_code = app.exec()
    logger.info(f"Exiting with code {ret_code}")
    exit(ret_code)


def main_darwin(app, runtime_args: argparse.Namespace):
    raise NotImplementedError("MacOS not supported yet")


def launch_python_backend(runtime_args: argparse.Namespace):
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    if host_os == "Windows":
        logger.debug("Running on Windows")
        main_win(app, runtime_args)
    elif host_os == "Linux":
        logger.debug("Running on Linux")
        main_linux(app, runtime_args)
    elif host_os == "Darwin":
        logger.debug("Running on MacOS")
        main_darwin(app, runtime_args)
    else:
        logger.error(f"Unsupported OS: {host_os}")
        exit(1)


def add_startup_task(runtime_args):
    if host_os == "Windows":
        from brightify.src_py.windows.actions import elevated_add_startup_task
        elevated_add_startup_task(runtime_args)
    elif host_os == "Linux":
        raise NotImplementedError("Not implemented yet")
    elif host_os == "Darwin":
        raise NotImplementedError("Not implemented yet")
    else:
        logger.error(f"Unsupported OS: {host_os}")
        exit(1)


def remove_startup_task():
    if host_os == "Windows":
        from brightify.src_py.windows.actions import elevated_remove_startup_task
        elevated_remove_startup_task()
    elif host_os == "Linux":
        raise NotImplementedError("Not implemented yet")
    elif host_os == "Darwin":
        raise NotImplementedError("Not implemented yet")
    else:
        logger.error(f"Unsupported OS: {host_os}")
        exit(1)


def add_startup_icon(runtime_args: argparse.Namespace):
    if host_os == "Windows":
        from brightify.src_py.windows.actions import add_startup_icon
        add_startup_icon(runtime_args)
    elif host_os == "Linux":
        raise NotImplementedError("Not implemented yet")
    elif host_os == "Darwin":
        raise NotImplementedError("Not implemented yet")
    else:
        logger.error(f"Unsupported OS: {host_os}")
        exit(1)


def remove_startup_dir_link():
    if host_os == "Windows":
        from brightify.src_py.windows.actions import remove_startup_folder
        remove_startup_folder()
    elif host_os == "Linux":
        raise NotImplementedError("Not implemented yet")
    elif host_os == "Darwin":
        raise NotImplementedError("Not implemented yet")
    else:
        logger.error(f"Unsupported OS: {host_os}")
        exit(1)


def add_menu_icon(runtime_args: argparse.Namespace):
    if host_os == "Windows":
        from brightify.src_py.windows.actions import add_menu_icon
        add_menu_icon(runtime_args)
    elif host_os == "Linux":
        raise NotImplementedError("Not implemented yet")
    elif host_os == "Darwin":
        raise NotImplementedError("Not implemented yet")
    else:
        logger.error(f"Unsupported OS: {host_os}")
        exit(1)


def remove_menu_icon():
    if host_os == "Windows":
        from brightify.src_py.windows.actions import remove_menu_icon
        remove_menu_icon()
    elif host_os == "Linux":
        raise NotImplementedError("Not implemented yet")
    elif host_os == "Darwin":
        raise NotImplementedError("Not implemented yet")
    else:
        logger.error(f"Unsupported OS: {host_os}")
        exit(1)


def main():
    # for writing logs before logging is configured
    install_log = brightify_dir / "logs" / "install.log"
    Path(install_log).parent.mkdir(parents=True, exist_ok=True)
    try:
        configure_logging()
        start_logging()
        logger.info("Brightify started")
    except Exception as e:
        with open(install_log, "a+") as f:
            f.write("Failed to configure logging\n")
            f.write(str(e) + "\n")
    # set global exception hook to the generic one
    sys.excepthook = except_hook

    try:
        args = parse_args()
    except SystemExit as e:
        logger.warning(f"Argument parsing failed. Most likely due to unknown arguments. Arguments: {sys.argv}")
        exit(1)
    except argparse.ArgumentError as e:
        logger.warning(f"Argument parsing failed at {e}")
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
                remove_startup_dir_link()
        if args.action in ["menu-icon", "all"]:
            logger.debug("Removing menu icon")
            remove_menu_icon()
    elif args.command == "run":
        if args.backend == "python":
            launch_python_backend(args)
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


if __name__ == '__main__':
    main()
