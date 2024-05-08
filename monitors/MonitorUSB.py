import logging
import threading
import time
from abc import abstractmethod
from typing import Optional, Iterable

import usb1

from base.Config import Config
from monitors.MonitorBase import MonitorBase

logger = logging.getLogger(Config.app_name)


class MonitorUSB(MonitorBase):
    def __init__(self, device: usb1.USBDevice, usb_delay_ms: Optional[float] = 100):

        if device.getProductID() != self.pid() or device.getVendorID() != self.vid():
            logger.warning("The device passed is not this monitor!")

        super().__init__(self.name())

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

    def clamp_brightness(self, b):
        return max(min(b, self.max_brightness), self.min_brightness)

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
    def name():
        pass

    @property
    def device(self) -> usb1.USBDevice:
        return self.__device
