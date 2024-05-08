import importlib
import inspect
import platform
from base.Config import Config
from typing import List, Tuple, Type
import usb1
from monitors.MonitorBase import MonitorBase


def get_supported_monitors(force_libusb: bool = True) -> List[MonitorBase]:
    """
    :param force_libusb: if True, force the use of libusb backend
    :return: a list of all MonitorBase implementations instantiated with the corresponding USB Device
    """
    import os
    monitor_impls = set()
    directory = "monitors"
    for filename in os.listdir(Config.root_dir / directory):
        if not filename.endswith(".py"):
            continue
        module_name = filename.replace(".py", "")
        full_module_name = f"{directory}.{module_name}"
        try:
            module = importlib.import_module(full_module_name)
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, MonitorBase) and obj is not MonitorBase:
                    monitor_impls.add(obj)
        except ImportError:
            pass

    monitor_inst: List[Tuple[Type[MonitorBase], usb1.USBDevice]] = []

    if force_libusb:
        from usb.backend import libusb1

        backend = libusb1.get_backend()
        if backend is None:
            raise ImportError("libusb backend not found")
        devices = usb.core.find(find_all=True, backend=backend)
    else:
        devices = usb.core.find(find_all=True)

    for d in devices:
        for impl in monitor_impls:
            if impl.vid() == d.idVendor and impl.pid() == d.idProduct:
                monitor_inst.append((impl, d))
                break

    return [impl(d) for impl, d in monitor_inst]