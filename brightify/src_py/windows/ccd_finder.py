from ctypes import wintypes
from ctypes.wintypes import HMONITOR, BOOL, HDC, RECT, LPARAM

from winerror import ERROR_SUCCESS

from brightify.src_py.windows.ccd_paths import query_display_config, DISPLAYCONFIG_PATH_INFO, LUID, full_struct
import ctypes


class DISPLAYCONFIG_DEVICE_INFO_TYPE(wintypes.DWORD):
    DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME = 1
    DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME = 2
    DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_PREFERRED_MODE = 3
    DISPLAYCONFIG_DEVICE_INFO_GET_ADAPTER_NAME = 4
    DISPLAYCONFIG_DEVICE_INFO_SET_TARGET_PERSISTENCE = 5
    DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_BASE_TYPE = 6
    DISPLAYCONFIG_DEVICE_INFO_GET_SUPPORT_VIRTUAL_RESOLUTION = 7
    DISPLAYCONFIG_DEVICE_INFO_SET_SUPPORT_VIRTUAL_RESOLUTION = 8
    DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO = 9
    DISPLAYCONFIG_DEVICE_INFO_SET_ADVANCED_COLOR_STATE = 10
    DISPLAYCONFIG_DEVICE_INFO_GET_SDR_WHITE_LEVEL = 11
    DISPLAYCONFIG_DEVICE_INFO_GET_MONITOR_SPECIALIZATION = 12
    DISPLAYCONFIG_DEVICE_INFO_SET_MONITOR_SPECIALIZATION = 13
    DISPLAYCONFIG_DEVICE_INFO_SET_RESERVED1 = 14
    DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO_2 = 15
    DISPLAYCONFIG_DEVICE_INFO_SET_HDR_STATE = 16
    DISPLAYCONFIG_DEVICE_INFO_SET_WCG_STATE = 17
    DISPLAYCONFIG_DEVICE_INFO_FORCE_UINT32 = 0xFFFFFFFF  # Forces this enumeration to compile to 32 bits in size. Without this value, some compilers would allow this enumeration to compile to a size other than 32 bits. You should not use this value.


class DISPLAYCONFIG_DEVICE_INFO_HEADER(ctypes.Structure):
    _fields_ = [
        ("type", DISPLAYCONFIG_DEVICE_INFO_TYPE),  # DISPLAYCONFIG_DEVICE_INFO_TYPE
        ("size", wintypes.DWORD),  # UINT32
        ("adapterId", LUID),  # LUID
        ("id", wintypes.DWORD),  # UINT32
    ]


class DISPLAYCONFIG_TARGET_DEVICE_NAME(ctypes.Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("flags", wintypes.DWORD),
        ("outputTechnology", wintypes.DWORD),
        ("edidManufactureId", wintypes.WORD),
        ("edidProductCodeId", wintypes.WORD),
        ("connectorInstance", wintypes.DWORD),
        ("monitorFriendlyDeviceName", wintypes.WCHAR * 64),
        ("monitorDevicePath", wintypes.WCHAR * 128)
    ]


class DISPLAYCONFIG_SOURCE_DEVICE_NAME(ctypes.Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("viewGdiDeviceName", wintypes.WCHAR * 32)
    ]


def enum_monitors():
    monitors = []
    try:
        def _callback(hmonitor, hdc, lprect, lparam):
            monitors.append(HMONITOR(hmonitor))
            del hmonitor, hdc, lprect, lparam
            return True  # continue enumeration

        MONITORENUMPROC = ctypes.WINFUNCTYPE(BOOL, HMONITOR, HDC, ctypes.POINTER(RECT), LPARAM)
        callback = MONITORENUMPROC(_callback)
        if not ctypes.windll.user32.EnumDisplayMonitors(0, 0, callback, 0):
            raise RuntimeError("Call to EnumDisplayMonitors failed")
    except OSError as e:
        raise RuntimeError("failed to enumerate VCPs") from e

    return monitors


def get_device_info(paths):
    for path in paths:
        path: DISPLAYCONFIG_PATH_INFO
        print(f"Target Adapter ID: {path.targetInfo.adapterId}")
        print(f"Target ID: {path.targetInfo.id}")

        # Get the target device name
        target_device_name = DISPLAYCONFIG_TARGET_DEVICE_NAME()
        target_device_name.header.adapterId = path.targetInfo.adapterId
        target_device_name.header.id = path.targetInfo.id
        target_device_name.header.type = DISPLAYCONFIG_DEVICE_INFO_TYPE.DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME
        target_device_name.header.size = ctypes.sizeof(DISPLAYCONFIG_TARGET_DEVICE_NAME)

        res = ctypes.windll.user32.DisplayConfigGetDeviceInfo(ctypes.byref(target_device_name.header))

        if res != ERROR_SUCCESS:
            print(f"Error in DisplayConfigGetDeviceInfo: {ctypes.FormatError(res)}")
            print(full_struct(target_device_name))
            continue

        print(f"Monitor Friendly Name: {target_device_name.monitorFriendlyDeviceName}")
        print(f"Monitor Device Path: {target_device_name.monitorDevicePath}")

        # Get the source device name (GDI Device Name)
        source_device_name = DISPLAYCONFIG_SOURCE_DEVICE_NAME()
        source_device_name.header.type = 1  # DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME
        source_device_name.header.size = ctypes.sizeof(DISPLAYCONFIG_SOURCE_DEVICE_NAME)
        source_device_name.header.adapterId = path.targetInfo.adapterId
        source_device_name.header.id = path.sourceInfo.id

        ctypes.windll.user32.DisplayConfigGetDeviceInfo(ctypes.byref(source_device_name.header))
        if ctypes.get_last_error() != ERROR_SUCCESS:
            #print(f"Error in DisplayConfigGetDeviceInfo: {ctypes.FormatError(res)}")
            continue

        print(f"GDI Device Name: {source_device_name.viewGdiDeviceName}")

        # Match the monitor with this device name
        monitors = enum_monitors()
        print(source_device_name.viewGdiDeviceName)


def main():
    paths, modes = query_display_config()
    get_device_info(paths)


if __name__ == "__main__":
    main()
