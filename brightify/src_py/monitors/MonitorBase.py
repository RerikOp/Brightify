import logging
from abc import ABC, abstractmethod
from typing import Optional, Iterable, Union

from brightify import app_name

logger = logging.getLogger(app_name)


class MonitorBase(ABC):
    def __init__(self, min_brightness: int = 0, max_brightness: int = 100):
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.last_set_brightness: Optional[int] = None
        self.last_get_brightness: Optional[int] = None

    @abstractmethod
    def get_brightness(self, blocking: bool = False, force: bool = False) -> Optional[int]:
        """
        Provides thread safe access to get the monitors' brightness. Must not raise exceptions.
        On any failure, return None and, optionally, log the error.
        Must return in a reasonable time frame as it is called from the main thread.
        Must set self.last_get_brightness to the returned value.
        :param blocking: if true, optionally stalls until a resource is ready
        :param force: block until resource is ready and use additional methods to get the brightness
        :return: the current brightness or None if device is blocked, an error occurred or the brightness is unknown
        """
        pass

    @abstractmethod
    def set_brightness(self, brightness: int, blocking: bool = False, force: bool = False) -> None:
        """
        Provides thread safe access to set the monitor's brightness. Must not raise exceptions.
        Must return in a reasonable time frame as it is called from the main thread.
        Must set self.last_set_brightness to the value that was set.
        :param brightness: the value to set
        :param blocking: if true, optionally stalls until a resource is ready
        :param force: block until resource is ready and use additional methods to set the brightness
        :return: None
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """
        :return: the name of the monitor
        """
        pass

    @staticmethod
    def get_type() -> str:
        """
        :return: the type of the monitor (e.g. "DDCCI", "USB") as a string
        """
        return "ANY"

    def clamp_brightness(self, b: Optional[int]) -> Optional[int]:
        """
        Clamps the brightness value within the allowed range.
        :param b: Brightness value.
        :return: Clamped brightness value.
        """
        try:
            if b is None:
                return None
            return max(min(b, self.max_brightness), self.min_brightness)
        except Exception as e:
            logger.error(f"Error clamping brightness: {e}", exc_info=True)
            return None

    def convert_sensor_readings(self, readings: Iterable[Union[int, float]]) -> Optional[int]:
        """
        Converts a number of sensor readings to the new brightness of this monitor. Must not raise exceptions.
        :param readings: an Iterable that contains the most recent readings. Must not contain None.
        The first element is the oldest reading
        :return: an int representing a proposed new brightness between self.min_brightness and self.max_brightness
        or None if the sensor data doesn't indicate a brightness switch or the sensor data is invalid.
        """
        diff_th = 5

        def measurement_to_brightness(m):
            return self.clamp_brightness(int(m * 2))

        def mean(data) -> float:
            return sum(data) / len(data)

        brightnesses = list(map(measurement_to_brightness, readings))
        if not brightnesses:
            return None
        potential_brightness = int(mean(brightnesses))
        current_brightness = self.last_get_brightness  # use cached value
        if current_brightness is None:
            return None
        if abs(current_brightness - potential_brightness) >= diff_th:  # prevents small changes
            return potential_brightness

        return None

    def __del__(self):
        """ Clean up resources. Must be idempotent. """
        logger.debug(f"Closing monitor {self.name()}. Type: {self.get_type()}")
