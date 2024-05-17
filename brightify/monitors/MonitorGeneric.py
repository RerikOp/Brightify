from typing import Optional, Callable

from brightify.monitors.MonitorBase import MonitorBase


class MonitorGeneric(MonitorBase):
    def __init__(self,
                 name_cb: Callable[[], str] | str,
                 get_brightness_cb: Callable[[bool, bool], Optional[int]],
                 set_brightness_cb: Callable[[int, bool, bool], None],
                 min_brightness: int = 0,
                 max_brightness: int = 100):
        super().__init__(min_brightness, max_brightness)
        self.set_brightness_cb = set_brightness_cb
        self.get_brightness_cb = get_brightness_cb
        if isinstance(name_cb, str):
            self.name_cb = lambda: name_cb
        else:
            self.name_cb = name_cb

    def name(self):
        return self.name_cb()

    def get_brightness(self, blocking: bool = False, force: bool = False) -> Optional[int]:
        return self.get_brightness_cb(blocking, force)

    def set_brightness(self, brightness: int, blocking: bool = False, force: bool = False) -> None:
        self.set_brightness_cb(brightness, blocking, force)
