import logging
from typing import Literal

from brightify import host_os
from brightify.src_py.ui_config import Theme

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


def get_registry_key(sub_key: str, name: str, root_key=winreg.HKEY_CURRENT_USER):
    import winreg
    try:
        key = winreg.OpenKey(root_key, sub_key)
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
    color, reg_type = get_registry_key(r'Software\Microsoft\Windows\DWM', 'ColorizationColor')
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


def animation_enabled() -> bool:
    logger.debug("Requested animations from OS")
    animations, reg_type = get_registry_key(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                                            "TaskbarAnimations")
    return animations == 1


def get_theme() -> Theme:
    return Theme(mode=get_mode(), accent_color=get_color(),
                 has_animations=animation_enabled())
