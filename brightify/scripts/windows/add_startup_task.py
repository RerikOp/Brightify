import sys

import win32com.client
from pathlib import Path


# must be run as admin
def create_startup_task(task_name, script_path):
    TASK_TRIGGER_AT_SYSTEMSTART = 8
    TASK_CREATE_OR_UPDATE = 6
    TASK_ACTION_EXEC = 0
    TASK_LOGON_NONE = 0  # Add this line

    scheduler = win32com.client.Dispatch('Schedule.Service')
    scheduler.Connect()

    root_folder = scheduler.GetFolder('\\')
    task_def = scheduler.NewTask(0)

    # Create a trigger for the task
    trigger = task_def.Triggers.Create(TASK_TRIGGER_AT_SYSTEMSTART)
    trigger.Enabled = True

    # Set the action to execute the script
    action = task_def.Actions.Create(TASK_ACTION_EXEC)
    action.Path = r'C:\Windows\System32\cmd.exe'
    action.Arguments = str(Path('/c ').joinpath(script_path))

    # Register the task (create or update)
    root_folder.RegisterTaskDefinition(
        task_name,  # Task name
        task_def,
        TASK_CREATE_OR_UPDATE,
        '',  # No user
        '',  # No password
        TASK_LOGON_NONE)

    print(f'Task "{task_name}" has been created.')


def create_bat_file(bat_file: Path):
    text = f"""@echo off
    python -m brightify
    """
    with open(bat_file, 'w+') as f:
        f.write(text)


if __name__ == '__main__':
    # verify the script is being run as admin
    import ctypes
    this_dir = Path(__file__).parent
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("This script must be run as admin, elevating...")
        # elevate the script
        ctypes.windll.shell32.ShellExecuteW(None,  # hwnd
                                            "runas",  # operation
                                            sys.executable,  # file
                                            str(Path(__file__)),  # parameters
                                            str(this_dir),  # directory
                                            1  # show cmd window
                                            )
        exit(0)

    bat_file = this_dir / "run_brightify.bat"
    create_bat_file(bat_file)
    create_startup_task('Brightify', bat_file)
