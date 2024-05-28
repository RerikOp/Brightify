import timeit
from typing import List, Type, Tuple
from pathlib import Path

from brightify import host_os
from brightify.monitors.MonitorBase import MonitorBase
from brightify.monitors.MonitorDDCCI import MonitorDDCCI
from brightify.monitors.MonitorUSB import MonitorUSB
from brightify.monitors.MonitorBase import logger


def _supported_usb_impls() -> List[Type[MonitorUSB]]:
    """
    Finds all user implemented MonitorUSB classes in the monitors directory.
    :return: a list of all MonitorUSB implementations
    """
    import importlib, inspect
    monitor_impls = set()
    for filename in Path(__file__).parent.glob("*.py"):
        module_name = filename.stem
        full_module_name = f"{__package__}.{module_name}"
        try:
            module = importlib.import_module(full_module_name)
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, MonitorUSB) and obj is not MonitorUSB:
                    monitor_impls.add(obj)
        except ImportError:
            pass
    return list(monitor_impls)


def _usb_monitors(monitor_impls: List[Type[MonitorUSB]]) -> List[MonitorUSB]:
    """
    Finds all USB devices connected to the system and instantiates the corresponding MonitorUSB classes.
    :param monitor_impls: a list of all MonitorUSB implementations
    :return: a list of all MonitorUSB implementations with a connected USB device
    """
    import usb1
    context = usb1.USBContext()
    devices = context.getDeviceList(skip_on_error=True)
    monitor_inst: List[Tuple[Type[MonitorUSB], usb1.USBDevice]] = []
    for dev in devices:
        for impl in monitor_impls:
            if impl.vid() == dev.getVendorID() and impl.pid() == dev.getProductID():
                monitor_inst.append((impl, dev))
                break

    return [impl(dev) for impl, dev in monitor_inst]


def _ddcci_monitors() -> List[MonitorDDCCI]:
    """
    Finds all monitors connected to the system and instantiates the MonitorDDCCI class.
    :return: a list of all MonitorDDCCI implementations
    """
    import monitorcontrol
    # time the operation
    monitors = monitorcontrol.get_monitors()
    # print the time it took in milliseconds
    return [MonitorDDCCI(monitor) for monitor in monitors]


def _internal_monitors() -> List[MonitorBase]:
    """
    Finds all internal monitors connected to the system and instantiates the MonitorBase class.
    :return: a list of all MonitorBase implementations
    """
    if host_os == "Windows":
        from brightify.windows.MonitorWMI import WMIMonitor
        if WMIMonitor.has_wmi_monitor():
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
        logger.info(f"Removed {diff} DDCCI monitor(s) already connected via USB")


    return usb_monitors + ddcci_monitors
