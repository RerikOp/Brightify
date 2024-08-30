import argparse
import ctypes
import sys
from ctypes import wintypes
from pathlib import Path
from typing import Literal

import winshell
import winreg
from brightify import icon_light, app_name, icon_dark
from brightify.src_py.ui_config import Theme
from ctypes.wintypes import DWORD, WCHAR, HMONITOR, BOOL, HDC, RECT, LPARAM, CHAR
from typing import Optional, Dict
from brightify.src_py.windows import logger

import wmi


# HELPER FUNCTIONS FOR ACTIONS:
def exec_path(runtime_args: argparse.Namespace):
    return sys.executable.replace("python.exe", "pythonw.exe") if not runtime_args.force_console else sys.executable


def run_call(runtime_args: argparse.Namespace):
    # only store true and choices are supported
    force_console = " --force-console" if runtime_args.force_console else ""
    no_animations = " --no-animations" if runtime_args.no_animations else ""
    verbose = " --verbose" if runtime_args.verbose else ""
    quiet = " --quiet" if runtime_args.quiet else ""
    backend = f" --backend={runtime_args.backend}" if runtime_args.backend else ""
    return f"-m brightify run{force_console}{no_animations}{verbose}{quiet}{backend}"


def add_icon(runtime_args: argparse.Namespace, directory):
    try:
        # create a shortcut in the directory folder
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        shortcut_path = directory / f"{app_name}.lnk"
        with winshell.shortcut(str(shortcut_path)) as shortcut:
            shortcut: winshell.Shortcut
            shortcut.path = exec_path(runtime_args)
            shortcut.arguments = run_call(runtime_args)
            shortcut.description = f"Startup link for {app_name}"
            icon_path = icon_light if get_mode() == "dark" else icon_dark
            if icon_path.exists():
                shortcut.icon_location = (str(icon_path), 0)
        logger.info(f"Added icon successfully to {directory.stem}")
        return True
    except PermissionError:
        logger.error(f"Failed to add icon: Permission denied")
    except Exception as e:
        logger.error(f"Failed to add icon: {e}")
    return False


# HELPER FUNCTIONS FOR WINDOWS API:
_DISPLAY_DEVICE_ACTIVE = 0x1


class DISPLAY_DEVICE(ctypes.Structure):
    _fields_ = [
        ("cb", DWORD),
        ("DeviceName", WCHAR * 32),
        ("DeviceString", WCHAR * 128),
        ("StateFlags", DWORD),
        ("DeviceID", WCHAR * 128),
        ("DeviceKey", WCHAR * 128)
    ]


class MONITORINFOEXA(ctypes.Structure):
    _fields_ = [
        ("cbSize", DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", DWORD),
        ("szDevice", CHAR * 32)
    ]


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


def _get_display(device_name):
    # only return the part between \\\\.\\ and \\ or until the end of the string
    import re
    match = re.search(r'\\\\\.\\(.*?)(\\|$)', device_name)
    if match:
        return match.group(1)
    return None


def _handle_to_display_mapping():
    hmonitors = []
    mapping = {}
    try:
        def _callback(hmonitor, hdc, lprect, lparam):
            hmonitors.append(HMONITOR(hmonitor))
            del hmonitor, hdc, lprect, lparam
            return True  # continue enumeration

        MONITORENUMPROC = ctypes.WINFUNCTYPE(BOOL, HMONITOR, HDC, ctypes.POINTER(RECT), LPARAM)
        callback = MONITORENUMPROC(_callback)
        if not ctypes.windll.user32.EnumDisplayMonitors(0, 0, callback, 0):
            raise RuntimeError("Call to EnumDisplayMonitors failed")
    except OSError as _:
        raise RuntimeError("failed to enumerate VCPs")

    for hmonitor in hmonitors:
        monitor_info = MONITORINFOEXA()
        monitor_info.cbSize = ctypes.sizeof(MONITORINFOEXA)
        if not ctypes.windll.user32.GetMonitorInfoA(hmonitor, ctypes.byref(monitor_info)):
            raise RuntimeError("Call to GetMonitorInfoA failed")
        mapping[_get_display(monitor_info.szDevice.decode("ascii"))] = hmonitor
    return mapping


def _display_to_device_id_mapping(only_active=True):
    i = 0
    devices = []
    # first get all display devices:
    while True:
        display_device = DISPLAY_DEVICE()
        display_device.cb = ctypes.sizeof(DISPLAY_DEVICE)
        if not ctypes.windll.user32.EnumDisplayDevicesW(None, i, ctypes.byref(display_device), 0):
            break
        if not only_active or display_device.StateFlags & _DISPLAY_DEVICE_ACTIVE:
            devices.append(display_device.DeviceName)
        i += 1
    mapping = {}
    for device_name in devices:
        j = 0
        while True:
            display_device = DISPLAY_DEVICE()
            display_device.cb = ctypes.sizeof(DISPLAY_DEVICE)
            # Query each monitor associated with the adapter
            if not ctypes.windll.user32.EnumDisplayDevicesW(device_name, j, ctypes.byref(display_device), 0):
                break
            if not only_active or display_device.StateFlags & _DISPLAY_DEVICE_ACTIVE:
                mapping[_get_display(display_device.DeviceName)] = display_device.DeviceID
            j += 1
    return mapping


def _device_id_to_f_name_mapping():
    c = wmi.WMI(namespace='root\\wmi')
    monitors = c.WmiMonitorID()
    mapping = {}
    for monitor in monitors:
        mapping[monitor.InstanceName] = ''.join(chr(c) for c in monitor.UserFriendlyName if c != 0)
    return mapping


def _display_to_handle_and_f_name_mapping(dmapping, hmapping, nmapping):
    dmapping_parts = {k: tuple(v.split('\\')) for k, v in dmapping.items()}
    nmapping_parts = {tuple(k.split('\\')): v for k, v in nmapping.items()}

    mapping: Dict[str, Optional[ctypes.POINTER]] = {display: None for display in hmapping.keys()}
    for device_id_parts, f_name in nmapping_parts.items():
        for did_part in device_id_parts:
            # we need to find the corresponding display in the dmapping parts
            for display, display_parts in dmapping_parts.items():
                if did_part in display_parts and display in hmapping:
                    mapping[display] = (f_name, hmapping[display])
    return mapping


def display_to_handle_and_f_name_mapping():
    try:
        dmapping = _display_to_device_id_mapping(True)
        hmapping = _handle_to_display_mapping()
        nmapping = _device_id_to_f_name_mapping()
        return _display_to_handle_and_f_name_mapping(dmapping, hmapping, nmapping)
    except Exception as e:
        logger.debug(f"Failed to map display to handle and friendly name: {e}")
        return {}
