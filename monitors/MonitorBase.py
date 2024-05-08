import dataclasses
import logging
from abc import ABC, abstractmethod
from typing import Optional, Iterable

from base.Config import Config

logger = logging.getLogger(Config.app_name)

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
