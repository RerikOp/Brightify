import logging
from typing import Literal, Tuple, Optional
from base.Config import Config
from base.UIConfig import Theme

if Config.host_os != "Windows":
    raise RuntimeError("This code is designed to run on Windows only")
try:
    import win32con, win32api, win32gui, win32ui, winerror, winreg
except ModuleNotFoundError:
    raise RuntimeError("This code is designed to run with pywin32")
except ImportError as e:
    raise RuntimeError("Failed importing pywin32: \n" + e.msg)

# Use OS specific logger
logger = logging.getLogger("Windows")


def get_color() -> str:
    registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Software\\Microsoft\\Windows\\DWM')
    color, reg_type = winreg.QueryValueEx(registry_key, 'ColorizationColor')
    winreg.CloseKey(registry_key)

    # Convert the color to hexadecimal and remove the alpha channel
    color = '#{:06X}'.format(color & 0xFFFFFF)

    return color


def get_mode() -> Literal["light", "dark"]:
    logger.debug("Requested Theme from OS")
    import winreg
    registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
    key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
    value = winreg.QueryValueEx(key, "AppsUseLightTheme")
    winreg.CloseKey(key)
    if value[0] == 1:
        return "light"
    else:
        return "dark"


def get_theme() -> Theme:
    return Theme(mode=get_mode(), accent_color=get_color())
