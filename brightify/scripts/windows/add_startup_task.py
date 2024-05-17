import ctypes
import os
import subprocess
import sys
from pathlib import Path


if __name__ == '__main__':
    script_dir = Path(__file__).parent
    bat_file = script_dir / "brightify.bat"
    no_console = script_dir / "no-console.vbs"
    install_log = script_dir / "install.log"
    task_name = "Brightify"
    force_console = "--force-console" in sys.argv

    with open(install_log, 'a+') as f:
        # write the arguments to the log file, omits the script path
        f.write(f"Adding {task_name} startup task with the following arguments: {sys.argv[1:]}\n")
        # check if the script is run as admin
        if not ctypes.windll.shell32.IsUserAnAdmin():
            s = "This script must be run as admin"
            f.write(s + "\n")
            raise PermissionError(s)
        if not force_console and not no_console.exists():
            s = "The vbs file does not exist but is required to run the script without a console"
            f.write(s + "\n")
            raise FileNotFoundError(s)
        if not bat_file.exists():
            s = "The bat file does not exist"
            f.write(s + "\n")
            raise FileNotFoundError(s)
        # get the current user
        current_user = os.getlogin()
        # create the task
        subprocess.run(
            ['schtasks', '/Create',
             '/SC', 'ONSTART',
             '/TN', task_name,
             '/TR', f"wscript.exe {str(no_console)} {bat_file}" if not force_console else str(bat_file),
             '/RU', current_user,
             '/F'],
            check=True, stdout=f, stderr=f)


