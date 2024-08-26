import binascii
import ctypes
from ctypes.wintypes import DWORD, WCHAR, HMONITOR, BOOL, HDC, RECT, LPARAM, CHAR
from typing import NamedTuple, Optional, Dict

import wmi


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


_DISPLAY_DEVICE_ACTIVE = 0x1


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
    dmapping = _display_to_device_id_mapping(True)
    hmapping = _handle_to_display_mapping()
    nmapping = _device_id_to_f_name_mapping()
    return _display_to_handle_and_f_name_mapping(dmapping, hmapping, nmapping)


if __name__ == "__main__":
    print(display_to_handle_and_f_name_mapping())
