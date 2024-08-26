import logging
from types import TracebackType
from typing import List, Optional, Tuple, Type
import ctypes
from ctypes.wintypes import DWORD, RECT, BOOL, HMONITOR, HDC, LPARAM, HANDLE, BYTE, WCHAR

from brightify.src_py.monitors.vpc import VCP, VCPError

# Use OS specific logger
logger = logging.getLogger("Windows")


class PhysicalMonitor(ctypes.Structure):
    _fields_ = [("handle", HANDLE), ("description", WCHAR * 128)]


class WindowsVCP(VCP):
    """
    Windows API access to a monitor's virtual control panel.
    """

    def __init__(self, hmonitor: HMONITOR, name: Optional[str] = None):
        super().__init__(name=name)
        self.hmonitor = hmonitor
        self.handle = None
        self.in_context = False

    def __enter__(self):
        self.in_context = True
        num_physical = DWORD()
        try:
            if not ctypes.windll.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(self.hmonitor,
                                                                               ctypes.byref(num_physical)):
                raise VCPError("Call to GetNumberOfPhysicalMonitorsFromHMONITOR failed: " + ctypes.FormatError())
        except OSError as e:
            raise VCPError("Call to GetNumberOfPhysicalMonitorsFromHMONITOR failed") from e

        if num_physical.value == 0:
            raise VCPError("No physical monitor found")
        elif num_physical.value > 1:
            raise VCPError("More than one physical monitor per hmonitor")

        physical_monitors = PhysicalMonitor()
        try:
            if not ctypes.windll.dxva2.GetPhysicalMonitorsFromHMONITOR(self.hmonitor, 1, physical_monitors):
                raise VCPError("Call to GetPhysicalMonitorsFromHMONITOR failed: " + ctypes.FormatError())
        except OSError as e:
            raise VCPError("Failed to open physical monitor handle") from e

        self.handle = physical_monitors.handle
        return self

    def __exit__(self, exception_type: Optional[Type[BaseException]], exception_value: Optional[BaseException],
                 exception_traceback: Optional[TracebackType]) -> Optional[bool]:
        try:
            if not ctypes.windll.dxva2.DestroyPhysicalMonitor(self.handle):
                raise VCPError("Call to DestroyPhysicalMonitor failed: " + ctypes.FormatError())
        except OSError as e:
            raise VCPError("Failed to close handle") from e
        finally:
            self.in_context = False
        return False

    def set_vcp_feature(self, code: int, value: int):
        if not self.in_context:
            raise VCPError("Not in VCP context")
        try:
            if not ctypes.windll.dxva2.SetVCPFeature(HANDLE(self.handle), BYTE(code), DWORD(value)):
                raise VCPError("Failed to set VCP feature: " + ctypes.FormatError())
        except OSError as e:
            raise VCPError("Failed to set VCP feature") from e

    def get_vcp_feature(self, code: int) -> Tuple[int, int]:
        if not self.in_context:
            raise VCPError("Not in VCP context")
        feature_current = DWORD()
        feature_max = DWORD()
        try:
            if not ctypes.windll.dxva2.GetVCPFeatureAndVCPFeatureReply(HANDLE(self.handle), BYTE(code), None,
                                                                       ctypes.byref(feature_current),
                                                                       ctypes.byref(feature_max)):
                raise VCPError("Failed to get VCP feature: " + ctypes.FormatError())
        except OSError as e:
            raise VCPError("Failed to get VCP feature") from e
        return feature_current.value, feature_max.value

    def get_vcp_capabilities(self) -> str:
        if not self.in_context:
            raise VCPError("Not in VCP context")
        cap_length = DWORD()
        try:
            if not ctypes.windll.dxva2.GetCapabilitiesStringLength(HANDLE(self.handle), ctypes.byref(cap_length)):
                raise VCPError("Failed to get VCP capabilities: " + ctypes.FormatError())
            cap_string = (ctypes.c_char * cap_length.value)()
            if not ctypes.windll.dxva2.CapabilitiesRequestAndCapabilitiesReply(HANDLE(self.handle), cap_string,
                                                                               cap_length):
                raise VCPError("Failed to get VCP capabilities: " + ctypes.FormatError())
        except OSError as e:
            raise VCPError(f"Getting VCP capabilities failed with OSError: {e}")
        return cap_string.value.decode("ascii")


def get_vcps() -> List[WindowsVCP]:
    """ Return a list of VCPs for all monitors. Searches for the corresponding monitor name and populates the VCPs. """
    from brightify.src_py.windows.find_name_windows import display_to_handle_and_f_name_mapping
    mapping = display_to_handle_and_f_name_mapping()
    vcps = []
    hmonitors = []

    def _callback(hmonitor, hdc, lprect, lparam):
        hmonitors.append(HMONITOR(hmonitor))
        return True  # continue enumeration

    MONITORENUMPROC = ctypes.WINFUNCTYPE(BOOL, HMONITOR, HDC, ctypes.POINTER(RECT), LPARAM)
    callback = MONITORENUMPROC(_callback)
    try:
        if not ctypes.windll.user32.EnumDisplayMonitors(0, 0, callback, 0):
            raise VCPError("Call to EnumDisplayMonitors failed")
    except OSError as e:
        raise VCPError("Failed to enumerate VCPs") from e

    for logical in hmonitors:
        name = None
        for display, (f_name, handle) in mapping.items():
            if handle.value == logical.value:
                name = f_name
                break
        vcps.append(WindowsVCP(logical, name))
    return vcps
