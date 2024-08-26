import ctypes
from ctypes import wintypes
from typing import Any
from winerror import ERROR_SUCCESS

# Constants and structures used in the Windows API
QDC_ONLY_ACTIVE_PATHS = 0x00000002


def full_struct(ctypes_struct: ctypes.Structure | ctypes.Union, indent: int = 0) -> str:
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
            s += full_struct(field_val, indent + 1)
        elif issubclass(field_type, ctypes.Union):
            s += "\t" * (indent + 1) + f"UNION {field_name}\n"
            s += full_struct(field_val, indent + 1)
        else:
            s += "\t" * (indent + 1) + f"{field_name}{bit_width} = {field_val}\n"
    s = s.replace("\t", "  ")
    lines = s.split("\n")
    longest_line = max([len(line) for line in lines])
    s = "\t" * indent + "-" * longest_line + "\n" + s + "\t" * indent + "-" * longest_line + "\n"
    return s


class LUID(ctypes.Structure):
    __slots__ = ()
    _fields_ = (('LowPart', wintypes.DWORD),
                ('HighPart', wintypes.LONG))

    def __init__(self, value=0, *args: Any, **kw: Any):
        super().__init__(*args, **kw)
        self.HighPart = value >> 32
        self.LowPart = value & ((1 << 32) - 1)

    def __int__(self):
        return self.HighPart << 32 | self.LowPart


class DISPLAYCONFIG_MODE_INFO_TYPE(wintypes.UINT):
    SOURCE = 1
    TARGET = 2
    DESKTOP_IMAGE = 3
    FORCE_UINT32 = 0xFFFFFFFF


class DISPLAYCONFIG_PIXELFORMAT(wintypes.UINT):
    DISPLAYCONFIG_PIXELFORMAT_8BPP = 1
    DISPLAYCONFIG_PIXELFORMAT_16BPP = 2
    DISPLAYCONFIG_PIXELFORMAT_24BPP = 3
    DISPLAYCONFIG_PIXELFORMAT_32BPP = 4
    DISPLAYCONFIG_PIXELFORMAT_NONGDI = 5
    DISPLAYCONFIG_PIXELFORMAT_FORCE_UINT32 = 0xFFFFFFFF


class POINTL(ctypes.Structure):
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG)
    ]


class RECTL(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG)
    ]


class DISPLAYCONFIG_RATIONAL(ctypes.Structure):
    _fields_ = [
        ("Numerator", wintypes.UINT),
        ("Denominator", wintypes.UINT)
    ]


class DISPLAYCONFIG_2DREGION(ctypes.Structure):
    _fields_ = [
        ("cx", wintypes.UINT),
        ("cy", wintypes.UINT)
    ]


class DISPLAYCONFIG_VIDEO_SIGNAL_INFO_UNION_STRUCT(ctypes.Structure):
    _fields_ = [
        ("videoStandard", wintypes.UINT, 16),
        ("vSyncFreqDivider", wintypes.UINT, 6),
        ("reserved", wintypes.UINT, 10)
    ]


class DISPLAYCONFIG_VIDEO_SIGNAL_INFO_UNION(ctypes.Union):
    _fields_ = [
        ("AdditionalSignalInfo", DISPLAYCONFIG_VIDEO_SIGNAL_INFO_UNION_STRUCT),
        ("videoStandard", wintypes.UINT)
    ]


class DISPLAYCONFIG_VIDEO_SIGNAL_INFO(ctypes.Structure):
    _fields_ = [
        ("pixelRate", wintypes.ULARGE_INTEGER),
        ("hSyncFreq", DISPLAYCONFIG_RATIONAL),
        ("vSyncFreq", DISPLAYCONFIG_RATIONAL),
        ("activeSize", DISPLAYCONFIG_2DREGION),
        ("totalSize", DISPLAYCONFIG_2DREGION),
        ("DUMMYUNIONNAME", DISPLAYCONFIG_VIDEO_SIGNAL_INFO_UNION),
        ("scanLineOrdering", wintypes.UINT)  # Replace with actual enum if necessary
    ]


class DISPLAYCONFIG_TARGET_MODE(ctypes.Structure):
    _fields_ = [
        ("targetVideoSignalInfo", DISPLAYCONFIG_VIDEO_SIGNAL_INFO)
    ]


class DISPLAYCONFIG_SOURCE_MODE(ctypes.Structure):
    _fields_ = [
        ("width", wintypes.UINT),
        ("height", wintypes.UINT),
        ("pixelFormat", DISPLAYCONFIG_PIXELFORMAT),
        ("position", POINTL)
    ]


class DISPLAYCONFIG_DESKTOP_IMAGE_INFO(ctypes.Structure):
    _fields_ = [
        ("PathSourceSize", POINTL),
        ("DesktopImageRegion", RECTL),
        ("DesktopImageClip", RECTL)
    ]


class DISPLAYCONFIG_MODE_INFO_UNION(ctypes.Union):
    _fields_ = [
        ("targetMode", DISPLAYCONFIG_TARGET_MODE),
        ("sourceMode", DISPLAYCONFIG_SOURCE_MODE),
        ("desktopImageInfo", DISPLAYCONFIG_DESKTOP_IMAGE_INFO),
    ]


class DISPLAYCONFIG_MODE_INFO(ctypes.Structure):
    _anonymous_ = ("DUMMYUNIONNAME",)
    _fields_ = [
        ("infoType", DISPLAYCONFIG_MODE_INFO_TYPE),  # DISPLAYCONFIG_MODE_INFO_TYPE
        ("id", wintypes.UINT),  # UINT32
        ("adapterId", LUID),  # LUID (64-bit integer)
        ("DUMMYUNIONNAME", DISPLAYCONFIG_MODE_INFO_UNION),
    ]


class DISPLAYCONFIG_PATH_SOURCE_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId", LUID),
        ("id", wintypes.UINT),  # UINT32
        ("modeInfoIdx", wintypes.UINT),  # UINT32
        ("statusFlags", wintypes.UINT)  # UINT32
    ]


class DISPLAYCONFIG_PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId", LUID),
        ("id", wintypes.UINT),  # UINT32
        ("modeInfoIdx", wintypes.UINT),  # UINT32
        ("outputTechnology", wintypes.UINT),  # UINT32
        ("rotation", wintypes.UINT),  # UINT32
        ("scaling", wintypes.UINT),  # UINT32
        ("refreshRate", wintypes.DWORD),  # Assuming it's a 32-bit value
        ("scanLineOrdering", wintypes.UINT),  # UINT32
        ("targetAvailable", wintypes.BOOL),
        ("statusFlags", wintypes.UINT)  # UINT32
    ]


class DISPLAYCONFIG_PATH_INFO(ctypes.Structure):
    _fields_ = [
        ("sourceInfo", DISPLAYCONFIG_PATH_SOURCE_INFO),
        ("targetInfo", DISPLAYCONFIG_PATH_TARGET_INFO),
        ("flags", wintypes.UINT)  # UINT32
    ]


def query_display_config():
    path_count = wintypes.UINT()
    mode_count = wintypes.UINT()

    # Get the size of the buffers required
    res = ctypes.windll.user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS,
                                                           ctypes.byref(path_count),
                                                           ctypes.byref(mode_count))
    if res != 0:
        print(f"Error in QueryDisplay: {ctypes.FormatError(res)}")
        return None, None

    # Allocate arrays for paths and modes
    paths = (DISPLAYCONFIG_PATH_INFO * path_count.value)()
    modes = (DISPLAYCONFIG_MODE_INFO * mode_count.value)()

    # Query active paths and modes
    res = ctypes.windll.user32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS,  # Query only active paths
                                                  ctypes.byref(path_count),  # Number of paths
                                                  paths,  # Array of paths
                                                  ctypes.byref(mode_count),  # Number of modes
                                                  modes,  # Array of modes
                                                  None)  # Reserved
    if res != ERROR_SUCCESS:
        print(f"Error in QueryDisplay: {ctypes.FormatError(res)}")
        return None, None

    return paths[:path_count.value], modes[:mode_count.value]
