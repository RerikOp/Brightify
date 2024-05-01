import importlib
import inspect
import platform
from collections import namedtuple
from pathlib import Path
from typing import List, Tuple, Type
import usb
from monitors.monitor_base import MonitorBase

Point = namedtuple('Point', 'x y')


def invert_ico(icon_path: Path):
    from PIL import Image
    image = Image.open(icon_path)
    assert image.mode == "LA", 'This function converts an image with mode "LA"'

    def invert_la(img):
        inverted_pixels = [(255 - pixel[0], pixel[1]) for pixel in img.getdata()]
        inverted_img = Image.new(img.mode, img.size)
        inverted_img.putdata(inverted_pixels)
        return inverted_img

    output_path = f"{icon_path.stem}_inv{icon_path.suffix}"

    inverted_image = invert_la(image)
    inverted_image.save(output_path, format='ICO', sizes=[image.size])


def get_supported_monitors(directory: Path, force_libusb: bool = False) -> List[MonitorBase]:
    """

    :param directory: the path where the MonitorBase implementations lie
    :param force_libusb: if True, force the use of libusb backend
    :return: a list of all MonitorBase implementations instantiated with the corresponding USB Device
    """
    import os
    monitor_impls = set()

    for filename in os.listdir(directory):
        if not filename.endswith(".py"):
            continue
        module_name = filename.replace(".py", "")
        full_module_name = f"{directory.name}.{module_name}"
        try:
            module = importlib.import_module(full_module_name)
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, MonitorBase) and obj is not MonitorBase:
                    monitor_impls.add(obj)
        except ImportError:
            pass

    monitor_inst: List[Tuple[Type[MonitorBase], usb.core.Device]] = []

    if force_libusb or any(platform.win32_ver()):
        from usb.backend import libusb1
        backend = libusb1.get_backend()
        if backend is None:
            # try using the libusb_package package
            import libusb_package
            backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
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
