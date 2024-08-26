from brightify.src_py.monitors.MonitorBase import MonitorBase
from brightify.src_py.monitors.MonitorBase import logger
import wmi


def has_wmi_monitor() -> bool:
    try:
        _ = wmi.WMI(namespace='wmi').WmiMonitorBrightnessMethods()[0].WmiSetBrightness
        _ = wmi.WMI(namespace='wmi').WmiMonitorBrightness()[0].CurrentBrightness
        return True
    except AttributeError:
        return False
    except wmi.x_wmi as _:
        return False


class WMIMonitor(MonitorBase):
    def __init__(self):
        super().__init__(0, 100)
        self.wmi = wmi.WMI(namespace='wmi')
        self.__set_brightness = None
        self.__get_brightness = None
        try:
            self.__set_brightness = lambda value: self.wmi.WmiMonitorBrightnessMethods()[0].WmiSetBrightness(value, 0)
            self.__get_brightness = lambda: self.wmi.WmiMonitorBrightness()[0].CurrentBrightness
        except wmi.x_wmi as _:
            logger.error("Internal monitor not found.")
            return

    @staticmethod
    def get_type():
        return "WMI"

    def get_brightness(self, blocking: bool = False, force: bool = False) -> int | None:
        return self.__get_brightness()

    def set_brightness(self, brightness: int, blocking: bool = False, force: bool = False) -> None:
        self.__set_brightness(brightness)

    def name(self):
        return "Internal"
