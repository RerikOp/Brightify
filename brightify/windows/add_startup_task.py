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
    install_log = Path(__file__).parent.parent / "logs" / "install.log"
    Path(install_log).parent.mkdir(parents=True, exist_ok=True)

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

        # create the task
        subprocess.run(
            ['schtasks', '/Create',
             '/SC', 'ONSTART',
             '/TN', tn,
             '/TR', tr,
             '/RU', ru,
             '/F'],
            check=True, stdout=f, stderr=f)
