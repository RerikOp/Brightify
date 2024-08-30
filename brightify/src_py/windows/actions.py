import argparse
import ctypes
import os
import winshell
import sys
from pathlib import Path
from brightify import app_name
from brightify.src_py.windows.helpers import exec_path, run_call, add_icon
from brightify.src_py.windows import logger


def add_startup_task(runtime_args):
    from brightify.src_py.windows import add_startup_task
    args = ["--task-name", app_name,
            "--path", f"\"{exec_path(runtime_args)}\"",
            "--args", run_call(runtime_args)]

    ret = ctypes.windll.shell32.ShellExecuteW(None,  # hwnd
                                              "runas",  # operation
                                              sys.executable,  # program, the python interpreter
                                              f'"{add_startup_task.__file__}" {" ".join(args)}',  # script to run
                                              None,  # working directory
                                              1)  # show window
    if ret <= 32:
        logger.error(f"Failed to add startup task: {ctypes.FormatError()}")
        return False
    else:
        logger.info("Added startup task successfully")
        return True


def remove_startup_task():
    from brightify.src_py.windows import remove_startup_task
    args = ["--task-name", app_name]
    # run the script as admin
    ret = ctypes.windll.shell32.ShellExecuteW(None,  # hwnd
                                              "runas",  # operation
                                              sys.executable,  # program, the python interpreter
                                              f'"{remove_startup_task.__file__}" {" ".join(args)}',  # script to run
                                              None,  # working directory
                                              1)  # show window

    if ret <= 32:
        logger.error(f"Failed to remove startup task: {ctypes.FormatError()}")
        return False
    else:
        logger.info("Removed startup task successfully")
        return True


def add_menu_icon(runtime_args: argparse.Namespace):
    programs_folder = winshell.programs()
    add_icon(runtime_args, programs_folder)


def remove_menu_icon():
    programs_folder = winshell.programs()
    shortcut_path = Path(programs_folder) / f"{app_name}.lnk"
    if shortcut_path.exists():
        try:
            os.remove(shortcut_path)
            logger.info("Removed menu icon successfully")
            return True
        except PermissionError:
            logger.error(f"Failed to remove menu icon: Permission denied")
    else:
        logger.info("Menu icon not found - nothing to remove")
    return False



def add_startup_icon(runtime_args: argparse.Namespace):
    startup_folder = winshell.startup()
    add_icon(runtime_args, startup_folder)


def remove_startup_icon():
    startup_folder = winshell.startup()
    shortcut_path = Path(startup_folder) / f"{app_name}.lnk"
    if shortcut_path.exists():
        try:
            os.remove(shortcut_path)
            logger.info("Removed startup icon successfully")
            return True
        except PermissionError:
            logger.error(f"Failed to remove startup icon: Permission denied")
    else:
        logger.info("Startup icon not found - nothing to remove")
    return False


def run(app, runtime_args):
    import ctypes
    import win32gui
    import logging
    from brightify import OSEvent
    from brightify.src_py.BrightifyApp import BrightifyApp
    from brightify.src_py.windows.WindowsApp import WindowsApp
    from PyQt6.QtCore import QThread, Qt

    os_event = OSEvent()
    brightify_app = BrightifyApp(os_event, runtime_args, window_type=Qt.WindowType.Tool)
    win_app = WindowsApp(os_event)
    running = True
    logger = logging.getLogger("Windows")

    class WindowsThread(QThread):
        def run(self):
            already_handled = False
            while running:
                l_button_down = ctypes.windll.user32.GetAsyncKeyState(win_app.primary_click) & 0x8000 != 0
                if l_button_down and not already_handled:
                    already_handled = True
                elif not l_button_down and already_handled:
                    os_event.locked = True
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

    app.aboutToQuit.connect(cleanup)
    windows_thread = WindowsThread()
    try:
        windows_thread.start()
        app.exec()
    finally:
        cleanup()
