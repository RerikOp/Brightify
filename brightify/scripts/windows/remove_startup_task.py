import subprocess
from brightify import app_name
import ctypes
import logging

logger = logging.getLogger("Windows")

if __name__ == '__main__':
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise PermissionError("This script must be run as admin")
    result = subprocess.run(['schtasks', '/Delete', '/TN', app_name, '/F'], capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Failed to delete task {app_name}: {result.stderr}")
    else:
        logger.error(f"Deleted task {app_name}")
