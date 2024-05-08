import importlib
import inspect
import logging

from base.Config import Config
from typing import List, Tuple, Type, Iterable, Optional
import usb1
from monitors.MonitorUSB import MonitorUSB

logger = logging.getLogger(Config.app_name)


def convert_sensor_readings(self, readings: Iterable) -> Optional[int]:
    """
    Converts a number of sensor readings to the new brightness of this monitor
    :param readings: an Iterable that contains at least min_num_sensor_readings() of most recent readings.
     The first element is the oldest reading
    :return: an int representing a proposed new brightness between self.min_brightness and self.max_brightness
    or None if the sensor data doesn't indicate a brightness switch
    """
    cv_th = 3
    diff_th = 3

    def measurement_to_brightness(m):
        return self.clamp_brightness(int(m * 1.8))

    def mean(data) -> float:
        return sum(data) / len(data)

    def std_dev(data, _mean):
        squared_diff_sum = sum((x - _mean) ** 2 for x in data)
        variance = squared_diff_sum / len(data)
        return variance ** 0.5

    # https://en.wikipedia.org/wiki/Coefficient_of_variation
    def cv(data):
        _mean = mean(data)
        if _mean == 0:
            return cv_th
        _std_dev = std_dev(data, _mean)
        _cv = (_std_dev / _mean) * 100
        return _cv

    brightnesses = list(map(measurement_to_brightness, readings))
    potential_brightness = int(mean(brightnesses))
    if cv(brightnesses) <= cv_th:  # prevents the monitor from changing its brightness in steps
        current_brightness = self.get_brightness(force=True)
        if abs(current_brightness - potential_brightness) >= diff_th:  # prevents small changes
            return potential_brightness

    return None


def get_supported_monitors() -> List[MonitorUSB]:
    """
    Get all MonitorBase implementations that are supported by the connected USB devices.
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
                if inspect.isclass(obj) and issubclass(obj, MonitorUSB) and obj is not MonitorUSB:
                    monitor_impls.add(obj)
        except ImportError:
            pass

    logger.info(f"Found {len(monitor_impls)} monitor implementation(s): {monitor_impls}")

    monitor_inst: List[Tuple[Type[MonitorUSB], usb1.USBDevice]] = []

    context = usb1.USBContext()
    devices = context.getDeviceList(skip_on_error=True)

    logger.info(f"Found {len(devices)} USB device(s)")

    for d in devices:
        for impl in monitor_impls:
            if impl.vid() == d.getVendorID() and impl.pid() == d.getProductID():
                monitor_inst.append((impl, d))
                break

    return [impl(d) for impl, d in monitor_inst]
