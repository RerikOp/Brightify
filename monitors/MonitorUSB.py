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

        super().__init__()

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

    @property
    def device(self) -> usb1.USBDevice:
        return self.__device
