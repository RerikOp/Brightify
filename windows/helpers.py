from typing import Literal

from base.Config import Config

if Config.host_os != "Windows":
    raise RuntimeError("This code is designed to run on Windows only")
try:
    import win32con, win32api, win32gui, win32ui, winerror
except ModuleNotFoundError:
    raise RuntimeError("This code is designed to run with pywin32")
except ImportError as e:
    raise RuntimeError("Failed importing pywin32: \n" + e.msg)


def get_mode() -> Literal["light", "dark"]:
    import winreg
    registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
    key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
    value = winreg.QueryValueEx(key, "AppsUseLightTheme")

    if value[0] == 1:
        return "light"
    else:
        return "dark"
