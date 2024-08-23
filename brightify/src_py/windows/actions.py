import argparse
import ctypes
import os
import winshell
import sys
from pathlib import Path

from brightify import app_name, icon_light, icon_dark
from brightify.src_py.windows.helpers import get_mode


def elevated_add_startup_task(runtime_args):
    from brightify.src_py.windows import add_startup_task
    args = ["--task-name", app_name,
            "--path", f"\"{exec_path(runtime_args)}\"",
            "--args", run_call(runtime_args)]

    ctypes.windll.shell32.ShellExecuteW(None,  # hwnd
                                        "runas",  # operation
                                        sys.executable,  # program, the python interpreter
                                        f'"{add_startup_task.__file__}" {" ".join(args)}',  # script to run
                                        None,  # working directory
                                        1)  # show window


def elevated_remove_startup_task():
    from brightify.src_py.windows import remove_startup_task
    args = ["--task-name", app_name]
    # run the script as admin
    ctypes.windll.shell32.ShellExecuteW(None,  # hwnd
                                        "runas",  # operation
                                        sys.executable,  # program, the python interpreter
                                        f'"{remove_startup_task.__file__}" {" ".join(args)}',  # script to run
                                        None,  # working directory
                                        1)  # show window


def exec_path(runtime_args: argparse.Namespace):
    return sys.executable.replace("python.exe", "pythonw.exe") if not runtime_args.force_console else sys.executable


def run_call(runtime_args: argparse.Namespace):
    force_console = " --force-console" if runtime_args.force_console else ""
    no_animations = " --no-animations" if runtime_args.no_animations else ""
    return f"-m brightify run{force_console}{no_animations}"


def add_icon(runtime_args: argparse.Namespace, directory):
    # create a shortcut in the directory folder
    Path(directory).mkdir(parents=True, exist_ok=True)
    shortcut_path = Path(directory) / f"{app_name}.lnk"
    with winshell.shortcut(str(shortcut_path)) as shortcut:
        shortcut: winshell.Shortcut
        shortcut.path = exec_path(runtime_args)
        shortcut.arguments = run_call(runtime_args)
        shortcut.description = f"Startup link for {app_name}"
        icon_path = icon_light if get_mode() == "dark" else icon_dark
        if icon_path.exists():
            shortcut.icon_location = (str(icon_path), 0)


def add_menu_icon(runtime_args: argparse.Namespace):
    programs_folder = winshell.programs()
    add_icon(runtime_args, programs_folder)


def remove_menu_icon():
    programs_folder = winshell.programs()
    shortcut_path = Path(programs_folder) / f"{app_name}.lnk"
    if shortcut_path.exists():
        os.remove(shortcut_path)


def add_startup_icon(runtime_args: argparse.Namespace):
    startup_folder = winshell.startup()
    add_icon(runtime_args, startup_folder)


def remove_startup_folder():
    startup_folder = winshell.startup()
    shortcut_path = Path(startup_folder) / f"{app_name}.lnk"
    if shortcut_path.exists():
        os.remove(shortcut_path)
