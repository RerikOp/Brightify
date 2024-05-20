import ctypes
import os
import winshell
import sys
from pathlib import Path

from brightify import app_name, icon_light, icon_dark
from brightify.windows.helpers import get_mode


def elevated_add_startup_task(force_console):
    from brightify.windows import add_startup_task

    args = ["--task-name", app_name,
            "--path", f"\"{exec_path(force_console)}\"",
            "--args", exec_arg()]

    ctypes.windll.shell32.ShellExecuteW(None,  # hwnd
                                        "runas",  # operation
                                        sys.executable,  # program, the python interpreter
                                        f'"{add_startup_task.__file__}" {" ".join(args)}',  # script to run
                                        None,  # working directory
                                        1)  # show window


def elevated_remove_startup_task():
    from brightify.windows import remove_startup_task
    args = ["--task-name", app_name]
    # run the script as admin
    ctypes.windll.shell32.ShellExecuteW(None,  # hwnd
                                        "runas",  # operation
                                        sys.executable,  # program, the python interpreter
                                        f'"{remove_startup_task.__file__}" {" ".join(args)}',  # script to run
                                        None,  # working directory
                                        1)  # show window


def exec_path(force_console):
    return sys.executable.replace("python.exe", "pythonw.exe") if not force_console else sys.executable


def exec_arg():
    return "-m brightify run"


def add_icon(force_console, directory):
    # create a shortcut in the directory folder
    Path(directory).mkdir(parents=True, exist_ok=True)
    shortcut_path = Path(directory) / f"{app_name}.lnk"
    with winshell.shortcut(str(shortcut_path)) as shortcut:
        shortcut: winshell.Shortcut
        shortcut.path = exec_path(force_console)
        shortcut.arguments = exec_arg()
        shortcut.description = f"Startup link for {app_name}"
        icon_path = icon_light if get_mode() == "dark" else icon_dark
        if icon_path.exists():
            shortcut.icon_location = (str(icon_path), 0)


def add_menu_icon(force_console):
    programs_folder = winshell.programs()
    add_icon(force_console, programs_folder)


def remove_menu_icon():
    programs_folder = winshell.programs()
    shortcut_path = Path(programs_folder) / f"{app_name}.lnk"
    if shortcut_path.exists():
        os.remove(shortcut_path)


def add_startup_icon(force_console):
    startup_folder = winshell.startup()
    add_icon(force_console, startup_folder)


def remove_startup_folder():
    startup_folder = winshell.startup()
    shortcut_path = Path(startup_folder) / f"{app_name}.lnk"
    if shortcut_path.exists():
        os.remove(shortcut_path)
