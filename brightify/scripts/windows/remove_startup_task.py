import subprocess
import ctypes
from pathlib import Path

if __name__ == '__main__':
    script_dir = Path(__file__).parent
    install_log = Path(__file__).parent.parent.parent / "logs" / "install.log"
    Path(install_log).parent.mkdir(parents=True, exist_ok=True)
    task_name = "Brightify"

    with open(install_log, 'a+') as f:
        f.write(f"Removing {task_name} startup task\n")
        if not ctypes.windll.shell32.IsUserAnAdmin():
            s = "This script must be run as admin"
            f.write(s + "\n")
            raise PermissionError(s)
        subprocess.run(['schtasks', '/Delete',
                        '/TN', task_name,
                        '/F'], check=True, stdout=f, stderr=f)
