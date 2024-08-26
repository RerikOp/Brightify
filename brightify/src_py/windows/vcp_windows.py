import logging

from brightify.src_py.monitors.vpc import VCP, VCPError
from types import TracebackType
from typing import List, Optional, Tuple, Type
import ctypes

from ctypes.wintypes import (
    DWORD,
    RECT,
    BOOL,
    HMONITOR,
    HDC,
    LPARAM,
    HANDLE,
    BYTE,
    WCHAR
)

# Use OS specific logger
logger = logging.getLogger("Windows")

class PhysicalMonitor(ctypes.Structure):
    _fields_ = [("handle", HANDLE), ("description", WCHAR * 128)]


class WindowsVCP(VCP):
    """
    Windows API access to a monitor's virtual control panel.

    References:
        https://stackoverflow.com/questions/16588133/
    """

    def __init__(self, hmonitor: HMONITOR, name: Optional[str] = None):
        """
        Initializes the WindowsVCP instance.
        :param hmonitor: logical monitor handle.
        Each physical display is represented by a monitor handle of type HMONITOR.
        A valid HMONITOR is guaranteed to be non-NULL.
        A physical display has the same HMONITOR as long as it is part of the desktop
        """
        super().__init__(name=name)
        self.hmonitor = hmonitor
        self.handle = None

    def __enter__(self):
        """
        Enters the runtime context related to this object.
        :return: self
        """
        num_physical = DWORD()
        try:
            if not ctypes.windll.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(self.hmonitor,
                                                                               ctypes.byref(num_physical)):
                raise VCPError(
                    "Call to GetNumberOfPhysicalMonitorsFromHMONITOR failed: " + ctypes.FormatError())
        except OSError as e:
            raise VCPError("Call to GetNumberOfPhysicalMonitorsFromHMONITOR failed") from e
        if num_physical.value == 0:
            raise VCPError("no physical monitor found")
        elif num_physical.value > 1:
            raise VCPError("more than one physical monitor per hmonitor")
        physical_monitors = PhysicalMonitor()
        try:
            if not ctypes.windll.dxva2.GetPhysicalMonitorsFromHMONITOR(self.hmonitor, 1, physical_monitors):
                raise VCPError("Call to GetPhysicalMonitorsFromHMONITOR failed: " + ctypes.FormatError())
        except OSError as e:
            raise VCPError("failed to open physical monitor handle") from e
        self.handle = physical_monitors.handle
        return self

    def __exit__(self, exception_type: Optional[Type[BaseException]], exception_value: Optional[BaseException],
                 exception_traceback: Optional[TracebackType],
                 ) -> Optional[bool]:
        """
        Exits the runtime context related to this object.
        :param exception_type: exception type
        :param exception_value: exception value
        :param exception_traceback: exception traceback
        :return: False
        """
        try:
            if not ctypes.windll.dxva2.DestroyPhysicalMonitor(self.handle):
                raise VCPError("Call to DestroyPhysicalMonitor failed: " + ctypes.FormatError())
        except OSError as e:
            raise VCPError("failed to close handle") from e
        return False

    def set_vcp_feature(self, code: int, value: int):
        """
        Sets the value of a feature on the virtual control panel.
        :param code: Feature code.
        :param value: Feature value.
        :raises VCPError: Failed to set VCP feature.
        """
        try:
            if not ctypes.windll.dxva2.SetVCPFeature(HANDLE(self.handle), BYTE(code), DWORD(value)):
                raise VCPError("failed to set VCP feature: " + ctypes.FormatError())
        except OSError as e:
            raise VCPError("failed to close handle") from e

    def get_vcp_feature(self, code: int) -> Tuple[int, int]:
        """
        Gets the value of a feature from the virtual control panel.
        :param code: Feature code.
        :return: Current feature value, maximum feature value.
        :raises VCPError: Failed to get VCP feature.
        """
        feature_current = DWORD()
        feature_max = DWORD()
        try:
            if not ctypes.windll.dxva2.GetVCPFeatureAndVCPFeatureReply(
                    HANDLE(self.handle),
                    BYTE(code),
                    None,
                    ctypes.byref(feature_current),
                    ctypes.byref(feature_max),
            ):
                raise VCPError("failed to get VCP feature: " + ctypes.FormatError())
        except OSError as e:
            raise VCPError("failed to get VCP feature") from e
        return feature_current.value, feature_max.value

    def get_vcp_capabilities(self) -> str:
        """
        Gets capabilities string from the virtual control panel.
        :return: Capabilities string.
        :raises VCPError: Failed to get VCP feature.
        """
        cap_length = DWORD()
        try:
            if not ctypes.windll.dxva2.GetCapabilitiesStringLength(HANDLE(self.handle), ctypes.byref(cap_length)):
                raise VCPError("Failed to get VCP capabilities: " + ctypes.FormatError())
            cap_string = (ctypes.c_char * cap_length.value)()
            if not ctypes.windll.dxva2.CapabilitiesRequestAndCapabilitiesReply(
                    HANDLE(self.handle), cap_string, cap_length):
                raise VCPError("Failed to get VCP capabilities: " + ctypes.FormatError())
        except OSError as e:
            raise VCPError(f"Getting VCP capabilities failed with OSError: {e}")
        return cap_string.value.decode("ascii")


def get_vcps() -> List[WindowsVCP]:
    """
    Opens handles to all physical VCPs.
    :return: List of all VCPs detected.
    :raises VCPError: Failed to enumerate VCPs.
    """
    from brightify.src_py.windows.find_name_windows import display_to_handle_and_f_name_mapping
    mapping = display_to_handle_and_f_name_mapping()
    vcps = []
    hmonitors = []
    try:
        def _callback(hmonitor, hdc, lprect, lparam):
            hmonitors.append(HMONITOR(hmonitor))
            del hmonitor, hdc, lprect, lparam
            return True  # continue enumeration
        MONITORENUMPROC = ctypes.WINFUNCTYPE(BOOL, HMONITOR, HDC, ctypes.POINTER(RECT), LPARAM)
        callback = MONITORENUMPROC(_callback)
        if not ctypes.windll.user32.EnumDisplayMonitors(0, 0, callback, 0):
            raise VCPError("Call to EnumDisplayMonitors failed")
    except OSError as e:
        raise VCPError("failed to enumerate VCPs") from e

    for logical in hmonitors:
        # find the physical monitor handle in the mapping:
        name = None
        for display, (f_name, handle) in mapping.items():
            try:
                if handle.value == logical.value:
                    name = f_name
                    break
            except Exception as e:
                logger.error(f"Failed to get handle value: {e}")
        vcps.append(WindowsVCP(logical, name))
    return vcps
