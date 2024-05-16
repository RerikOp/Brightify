import logging
from typing import Literal

from brightify import host_os
from brightify.UIConfig import Theme
from brightify.monitors.MonitorBase import MonitorBase

if host_os != "Windows":
    raise RuntimeError("This code is designed to run on Windows only")
try:
    import win32con, win32api, win32gui, win32ui, winerror, winreg
except ModuleNotFoundError:
    raise RuntimeError("This code is designed to run with pywin32")
except ImportError as e:
    raise RuntimeError("Failed importing pywin32: \n" + e.msg)

# Use OS specific logger
logger = logging.getLogger("Windows")

def get_registry_key(sub_key: str, name: str):
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key)
        value, reg_type = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return value, reg_type
    except FileNotFoundError as e:
        logger.error(f"Registry key not found: {e}")
    except OSError as e:
        logger.error(f"Failed to connect to registry: {e}")

    return None, None


def get_color() -> str:
    logger.debug("Requested accent color from OS")
    color, reg_type = get_registry_key('Software\\Microsoft\\Windows\\DWM', 'ColorizationColor')
    if color is None:
        color = "#0078D4"
    else:
        # Convert the color to hexadecimal and remove the alpha channel
        color = '#{:06X}'.format(color & 0xFFFFFF)
    return color


def get_mode() -> Literal["light", "dark"]:
    logger.debug("Requested Theme from OS")
    is_light, reg_type = get_registry_key(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                                          "AppsUseLightTheme")
    if is_light:
        return "light"
    else:
        return "dark"


def get_theme() -> Theme:
    logger.info("Using Theme from Windows")
    return Theme(mode=get_mode(), accent_color=get_color())
