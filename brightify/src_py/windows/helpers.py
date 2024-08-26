import ctypes
import logging
from ctypes import wintypes
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


class LUID(ctypes.Structure):
    __slots__ = ()
    _fields_ = (('LowPart', wintypes.DWORD),
                ('HighPart', wintypes.LONG))

    def __init__(self, value=0, *args, **kw):
        super().__init__(*args, **kw)
        self.HighPart = value >> 32
        self.LowPart = value & ((1 << 32) - 1)

    def __int__(self):
        return self.HighPart << 32 | self.LowPart


def ser_struct(ctypes_struct: ctypes.Structure | ctypes.Union, indent: int = 0) -> str:
    # get the name of the instance
    s = "\t" * indent + f"{ctypes_struct.__class__.__name__}\n"

    for field in ctypes_struct._fields_:
        bit_width = ""
        if len(field) == 2:
            field_name, field_type = field
        elif len(field) == 3:
            field_name, field_type, bit_width = field
            bit_width = f": {bit_width}"
        else:  # we hope for the best
            field_name = field[0]
            field_type = field[1]
        field_val = getattr(ctypes_struct, field_name)

        if isinstance(field_val, LUID):
            field_val = int(field_val)
        # if value is a function of field_val, call it
        if "value" in dir(field_val):
            field_val = field_val.value

        if isinstance(field_val, ctypes.Structure):
            s += "\t" * (indent + 1) + f"STRUCT {field_name}\n"
            s += ser_struct(field_val, indent + 1)
        elif issubclass(field_type, ctypes.Union):
            s += "\t" * (indent + 1) + f"UNION {field_name}\n"
            s += ser_struct(field_val, indent + 1)
        else:
            s += "\t" * (indent + 1) + f"{field_name}{bit_width} = {field_val}\n"
    s = s.replace("\t", "  ")
    lines = s.split("\n")
    longest_line = max([len(line) for line in lines])
    s = "\t" * indent + "-" * longest_line + "\n" + s + "\t" * indent + "-" * longest_line + "\n"
    return s
