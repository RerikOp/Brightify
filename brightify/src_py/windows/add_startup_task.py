import ctypes
import os
import subprocess
import argparse
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='Add a startup task.')
    parser.add_argument('--task-name', required=True, help='The name of the task.')
    parser.add_argument('--path', required=True, help='The path to the executable.')
    parser.add_argument('--args', nargs=argparse.REMAINDER, help='Space separated list with arguments.')

    return parser.parse_args()


if __name__ == '__main__':
    # This script should be standalone, so we need to hard-code the paths
    windows_dir = Path(__file__).parent
    src_py_dir = windows_dir.parent
    brightify_dir = src_py_dir.parent
    log_dir = brightify_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    install_log = log_dir / "install.log"

    with open(install_log, 'a+') as f:
        try:
            args = parse_args()
        except Exception as e:
            f.write("Failed to parse arguments\n")
            f.write(str(e) + "\n")
            raise e

        # write the arguments to the log file, omits the script path
        f.write(f"Adding {args.task_name} startup task with the following arguments: {args}\n")
        # check if the script is run as admin
        if not ctypes.windll.shell32.IsUserAnAdmin():
            s = "This script must be run as admin"
            f.write(s + "\n")
            raise PermissionError(s)

        # get the current user
        ru = os.getlogin()
        tn = args.task_name
        tr = args.path + " " + " ".join(args.args)

        schtasks_path = Path(os.getenv('SYSTEMROOT', 'C:\\Windows')) / 'System32' / 'schtasks.exe'
        if not schtasks_path.exists():
            s = "schtasks.exe not found"
            f.write(s + "\n")
            raise FileNotFoundError

        subprocess.run([schtasks_path, '/Create',
                        '/SC', 'ONSTART',
                        '/TN', tn,
                        '/TR', tr,
                        '/RU', ru,
                        '/F'],
                       check=True, stdout=f, stderr=f)
