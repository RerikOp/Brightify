from typing import List, Type, Tuple
from pathlib import Path
import importlib
import inspect
import usb1

from brightify import host_os
from brightify.src_py.monitors.MonitorBase import MonitorBase
from brightify.src_py.monitors.MonitorDDCCI import MonitorDDCCI
from brightify.src_py.monitors.MonitorUSB import MonitorUSB
from brightify.src_py.monitors.MonitorBase import logger
from brightify.src_py.monitors.vpc import VCPError


def _supported_usb_impls() -> List[Type[MonitorUSB]]:
    """
    Finds all user implemented MonitorUSB classes in the monitors directory.
    :return: a list of all MonitorUSB implementations
    """
    monitor_impls = set()
    for filename in Path(__file__).parent.glob("*.py"):
        module_name = filename.stem
        full_module_name = f"{__package__}.{module_name}"
        try:
            module = importlib.import_module(full_module_name)
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, MonitorUSB) and obj is not MonitorUSB:
                    monitor_impls.add(obj)
        except ImportError as e:
            logger.error(f"Failed to import module {full_module_name}: {e}", exc_info=True)
    return list(monitor_impls)


def _usb_monitors(monitor_impls: List[Type[MonitorUSB]]) -> List[MonitorUSB]:
    """
    Finds all USB devices connected to the system and instantiates the corresponding MonitorUSB classes.
    :param monitor_impls: a list of all MonitorUSB implementations
    :return: a list of all MonitorUSB implementations with a connected USB device
    """
    monitor_inst: List[Tuple[Type[MonitorUSB], usb1.USBDevice]] = []
    try:
        with usb1.USBContext() as context:
            devices = context.getDeviceList(skip_on_error=True)
            for dev in devices:
                for impl in monitor_impls:
                    if impl.vid() == dev.getVendorID() and impl.pid() == dev.getProductID():
                        monitor_inst.append((impl, dev))
                        break
    except usb1.USBError as e:
        logger.error(f"USB error: {e}", exc_info=True)

    return [impl(dev) for impl, dev in monitor_inst]


def _ddcci_monitors() -> List[MonitorDDCCI]:
    """
    Finds all monitors connected to the system and instantiates the MonitorDDCCI class.
    As DDC/CI is not always reliable, we try to connect multiple times.
    :return: a list of all MonitorDDCCI implementations
    """
    if host_os == "Windows":
        from brightify.src_py.windows.vcp_windows import get_vcps
    elif host_os == "Linux":
        from brightify.src_py.linux.vcp_linux import get_vcps
    else:
        logger.warning(f"Trying to connect to DDCCI monitor on unsupported OS: {host_os}")
        return []

    vcps = get_vcps()
    impls = []
    for vcp in vcps:
        try:
            m_impl = MonitorDDCCI(vcp)
            if m_impl.is_unknown():
                logger.debug(f"Found unknown DDCCI Monitor. Trying to force name from VCP capabilities")
                m_impl.update_cap(force=True)
            if m_impl.is_unknown():
                logger.info(f"Found unknown DDCCI Monitor")
            m_impl.get_brightness(force=True)
            impls.append(m_impl)
        except VCPError as e:
            logger.error(f"Failed to connect to DDCCI monitor: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Failed to get brightness of DDCCI monitor \"{m_impl.name()}\": {e}", exc_info=True)
    return impls


def _internal_monitors() -> List[MonitorBase]:
    """
    Finds all internal monitors connected to the system and instantiates the MonitorBase class.
    :return: a list of all MonitorBase implementations
    """
    if host_os == "Windows":
        from brightify.src_py.windows.MonitorWMI import WMIMonitor, has_wmi_monitor
        if has_wmi_monitor():
            return [WMIMonitor()]
    return []


def get_supported_monitors() -> List[MonitorBase]:
    """
    Finds all user implemented MonitorUSB classes and instantiates them with the corresponding USB device.
    If a monitor without a USB device is found or an implementation is missing, we try to connect to the monitor via DDC-CI.
    :return: a list of all MonitorBase implementations
    """
    monitor_impls = _supported_usb_impls()
    usb_monitors = _usb_monitors(monitor_impls)
    logger.info(f"Found {len(usb_monitors)} USB monitor(s) with implementation: {[m.name() for m in usb_monitors]}")

    all_ddcci_monitors = _ddcci_monitors()
    internal_monitors = _internal_monitors()
    logger.info(f"Found {len(internal_monitors)} internal monitor(s)")

    # remove DD/CCI monitors if they are already connected via USB
    ddcci_monitors = [m for m in all_ddcci_monitors if not any(m.name() == usb_m.name() for usb_m in usb_monitors)]
    if (diff := len(all_ddcci_monitors) - len(ddcci_monitors)) > 0:
        logger.debug(f"Removed {diff} DDCCI monitor(s) already connected via USB")

    return usb_monitors + ddcci_monitors + internal_monitors