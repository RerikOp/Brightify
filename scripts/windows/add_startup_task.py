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


if __name__ == '__main__':
    # verify the script is being run as admin
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise PermissionError("This script must be run as admin.")

    bat_file = Path(__file__).parent.joinpath("run_brightify.bat")
    create_startup_task('Brightify', bat_file)
