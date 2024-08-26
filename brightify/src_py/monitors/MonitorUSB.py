import threading
import time
from abc import abstractmethod
from typing import Optional

import usb1
import atexit

from brightify.src_py.monitors.MonitorBase import MonitorBase
from brightify.src_py.monitors.MonitorBase import logger


class MonitorUSB(MonitorBase):
    def __init__(self, device: usb1.USBDevice, usb_delay_ms: Optional[float] = 25):

        if device.getProductID() != self.pid() or device.getVendorID() != self.vid():
            logger.warning("The device passed is not this monitor!")

        super().__init__()
        # make sure the device is closed on exit
        atexit.register(self.__del__)
        self.__device = device
        self.__has_delay = usb_delay_ms is not None

        if self.__has_delay:
            self.usb_delay_ns = usb_delay_ms * 1000000
            self.last_interaction_ns = time.time_ns()

        self.lock = threading.Lock()

    def is_ready(self):
        is_ready = True
        if self.__has_delay:
            is_ready = time.time_ns() - self.last_interaction_ns >= self.usb_delay_ns
        return is_ready

    def clamp_brightness(self, b: Optional[int]) -> Optional[int]:
        if b is None:
            return None
        return max(min(b, self.max_brightness), self.min_brightness)

    @staticmethod
    @abstractmethod
    def vid() -> int:
        pass

    @staticmethod
    @abstractmethod
    def pid() -> int:
        pass

    @property
    def device(self) -> usb1.USBDevice:
        return self.__device

    @staticmethod
    def get_type():
        return "USB"

    def __del__(self):
        if self.__device is not None:
            logger.info(f"Closing monitor {self.name()}")
            self.__device.close()
            self.__device = None
            super().__del__()
