import logging
from abc import ABC, abstractmethod
from typing import Optional, Iterable

from brightify import app_name

logger = logging.getLogger(app_name)


class MonitorBase(ABC):
    def __init__(self, name: str, min_brightness: int = 0, max_brightness: int = 100):
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.name = name

    @abstractmethod
    def get_brightness(self, blocking=False, force: bool = False) -> Optional[int]:
        """
        Provides thread safe access to get the monitors brightness
        :param blocking: if true, optionally stalls until a resource is ready
        :param force: can be implemented to enable some kind of redundancy etc.
        :return: the current brightness or None if device is blocked, etc.
        """
        pass

    @abstractmethod
    def set_brightness(self, brightness: int, blocking=False, force: bool = False) -> None:
        """
        Provides thread safe access to set the monitor's brightness.
        :param brightness: the value to set
        :param blocking: if true, optionally stalls until a resource is ready
        :param force: can be implemented to enable some kind of redundancy etc.
        :return: None
        """
        pass

    def convert_sensor_readings(self, readings: Iterable) -> Optional[int]:
        """
        Converts a number of sensor readings to the new brightness of this monitor
        :param readings: an Iterable that contains the most recent readings.
         The first element is the oldest reading
        :return: an int representing a proposed new brightness between self.min_brightness and self.max_brightness
        or None if the sensor data doesn't indicate a brightness switch
        """
        diff_th = 5

        def clamp_brightness(b):
            return max(min(b, self.max_brightness), self.min_brightness)

        def measurement_to_brightness(m):
            return clamp_brightness(int(m * 2))

        def mean(data) -> float:
            return sum(data) / len(data)

        brightnesses = list(map(measurement_to_brightness, readings))
        potential_brightness = int(mean(brightnesses))
        current_brightness = self.get_brightness(force=True)
        if abs(current_brightness - potential_brightness) >= diff_th:  # prevents small changes
            return potential_brightness

        return None

    def __del__(self):
        pass
