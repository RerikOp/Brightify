import ctypes
import sys

import win32com.client
from brightify import app_name
from brightify.scripts.windows.actions import bat_file, no_console


# must be run as admin
def __create_startup_task(force_console):
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
    # if force_console is True, run the bat file directly
    if force_console:
        action.Path = str(bat_file)
    else:
        # the path is wscript.exe
        action.Path = "wscript.exe"
        action.Arguments = f"{str(no_console)} {str(bat_file)}"

    # Register the task (create or update)
    root_folder.RegisterTaskDefinition(
        app_name,  # Task name
        task_def,
        TASK_CREATE_OR_UPDATE,
        '',  # No user
        '',  # No password
        TASK_LOGON_NONE)


if __name__ == '__main__':
    force_console = "--force-console" in sys.argv

    if not bat_file.exists():
        raise FileNotFoundError("The bat file does not exist")
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise PermissionError("This script must be run as admin")
    __create_startup_task(force_console)
