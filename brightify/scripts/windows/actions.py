import ctypes
import sys

from brightify import root_dir

bat_file = root_dir / "scripts" / "windows" / "brightify.bat"
no_console = root_dir / "scripts" / "windows" / "no-console.vbs"


def create_bat_file():
    # create a bat file to run the script
    content = \
        f"""
:: This script is generated by Brightify
@echo off
:: Run the brightify script
python.exe -m brightify
pause
    """
    with open(bat_file, 'w+') as f:
        f.write(content)


def create_no_console_vbs():
    # create a vbs script to run the bat file without showing the console
    content = \
        f"""   
CreateObject("Wscript.Shell").Run \"\"\"\" & WScript.Arguments(0) & \"\"\"\", 0, False
"""
    with open(no_console, 'w+') as f:
        f.write(content)


def elevated_add_startup_task(force_console):
    create_bat_file()
    create_no_console_vbs()
    from brightify.scripts.windows import add_startup_task
    args = ["--force-console"] if force_console else []
    # pass the arguments to the script
    ctypes.windll.shell32.ShellExecuteW(None,  # hwnd
                                        "runas",  # operation
                                        sys.executable,  # program, the python interpreter
                                        add_startup_task.__file__,  # script to run
                                        " ".join(args),  # arguments
                                        1)  # show window


def elevated_remove_startup_task():
    from brightify.scripts.windows import remove_startup_task
    ctypes.windll.shell32.ShellExecuteW(None,  # hwnd
                                        "runas",  # operation
                                        sys.executable,  # program, the python interpreter
                                        remove_startup_task.__file__,  # script to run
                                        None,  # working directory
                                        1)  # show window
