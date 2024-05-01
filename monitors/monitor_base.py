import sys
import threading
import time
from abc import ABC, abstractmethod
from typing import Optional, Iterable

import usb


class MonitorBase(ABC):
    def __init__(self, device: usb.Device, usb_delay_ms: Optional[float] = 100):
        if device.idProduct != self.pid() or device.idVendor != self.vid():
            raise RuntimeError("The device passed is not this monitor!")
        self.__device = device
        self.__was_attached = False
        device: usb.core.Device
        if sys.platform != "win32" and device.is_kernel_driver_active(0):
            device.detach_kernel_driver(0)
            self.__was_attached = True
        device.set_configuration()

        if usb_delay_ms is not None:
            self.usb_delay_ns = usb_delay_ms * 1000000
            self.last_interaction_ns = time.time_ns()
        else:
            self.usb_delay_ns = None

        self.max_brightness: int = 100
        self.min_brightness: int = 0
        self.lock = threading.Lock()

    def reattach(self):
        # re-attach the driver if it was attached before
        if self.__was_attached:
            self.device.attach_kernel_driver(0)

    def is_ready(self):
        is_ready = True
        if self.usb_delay_ns is not None:
            is_ready = time.time_ns() - self.last_interaction_ns >= self.usb_delay_ns
        return is_ready

    def clamp_brightness(self, b):
        return max(min(b, self.max_brightness), self.min_brightness)

    @abstractmethod
    def convert_sensor_readings(self, readings: Iterable) -> Optional[int]:
        """
        Converts a number of sensor readings to the new brightness of this monitor
        :param readings: an Iterable that contains at least min_num_sensor_readings() of most recent readings.
         The first element is the oldest reading
        :return: an int representing a proposed new brightness between self.min_brightness and self.max_brightness
        or None if the sensor data doesn't indicate a brightness switch
        """
        pass

    @staticmethod
    @abstractmethod
    def min_num_sensor_readings() -> int:
        """
        Returns the minimum number of readings the convert_sensor_readings function requires to return a brightness value
        :return:
        """
        pass

    @staticmethod
    @abstractmethod
    def vid() -> int:
        pass

    @staticmethod
    @abstractmethod
    def pid() -> int:
        pass

    @staticmethod
    @abstractmethod
    def name() -> str:
        pass

    @property
    def device(self) -> usb.core.Device:
        return self.__device

    @abstractmethod
    def get_brightness(self, blocking=False, force: bool = False) -> Optional[int]:
        """
        Provides thread safe access to get the monitors brightness
        :param blocking: if true, stalls until is_ready() returns True
        :param force: Can be implemented to enable some kind of redundancy etc.
        :return: the current brightness or None if blocking and is_ready() are False
        """
        pass

    @abstractmethod
    def set_brightness(self, brightness: int, blocking=False, force: bool = False) -> None:
        """
        Provides thread safe access to set the monitor's brightness.
        If blocking and is_ready() are False, does nothing
        :param brightness: the value to set
        :param blocking: if true, stalls until is_ready() returns True
        :param force: Can be implemented to enable some kind of redundancy etc.
        :return: None
        """
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.reattach()
