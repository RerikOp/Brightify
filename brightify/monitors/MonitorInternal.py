from abc import abstractmethod
from typing import Optional, Callable

from brightify.monitors.MonitorBase import MonitorBase


class MonitorInternal(MonitorBase):
    def __init__(self, name: str,
                 get_brightness_cb: Callable[[], Optional[int]],
                 set_brightness_cb: Callable[[int], None],
                 min_brightness: int = 0,
                 max_brightness: int = 100):
        super().__init__(name, min_brightness, max_brightness)
        self.set_brightness_cb = set_brightness_cb
        self.get_brightness_cb = get_brightness_cb

    @abstractmethod
    def get_brightness(self, blocking=False, force: bool = False) -> Optional[int]:
        return self.get_brightness_cb()

    @abstractmethod
    def set_brightness(self, brightness: int, blocking=False, force: bool = False) -> None:
        self.set_brightness_cb(brightness)