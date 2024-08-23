import argparse
import subprocess
import ctypes
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='Remove a startup task.')
    parser.add_argument('--task-name', required=True, help='The name of the task.')
    return parser.parse_args()


if __name__ == '__main__':
    script_dir = Path(__file__).parent
    install_log = Path(__file__).parent.parent / "logs" / "install.log"
    Path(install_log).parent.mkdir(parents=True, exist_ok=True)

    with open(install_log, 'a+') as f:
        try:
            args = parse_args()
        except Exception as e:
            f.write("Failed to parse arguments\n")
            f.write(str(e) + "\n")
            raise e
        f.write(f"Removing {args.task_name} startup task\n")
        if not ctypes.windll.shell32.IsUserAnAdmin():
            s = "This script must be run as admin"
            f.write(s + "\n")
            raise PermissionError(s)
        subprocess.run(['schtasks', '/Delete',
                        '/TN', args.task_name,
                        '/F'], check=True, stdout=f, stderr=f)
