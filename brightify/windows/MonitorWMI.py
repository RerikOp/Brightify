from brightify.monitors.MonitorBase import MonitorBase
from brightify.monitors.MonitorBase import logger
import wmi


class WMIMonitor(MonitorBase):
    def __init__(self):
        super().__init__(0, 100)
        self.wmi = wmi.WMI(namespace='wmi')
        self.methods = None
        try:
            self.methods = self.wmi.WmiMonitorBrightnessMethods()[0]
        except wmi.x_wmi as _:
            logger.error("Internal monitor not found.")
            return

    @staticmethod
    def has_wmi_monitor() -> bool:
        try:
            wmi.WMI(namespace='wmi').WmiMonitorBrightnessMethods()[0]
            return True
        except wmi.x_wmi as _:
            return False
    @staticmethod
    def get_type():
        return "WMI"

    def get_brightness(self, blocking: bool = False, force: bool = False) -> int | None:
        if self.methods is None:
            return None
        return self.methods.WmiGetBrightness()[0]

    def set_brightness(self, brightness: int, blocking: bool = False, force: bool = False) -> None:
        if self.methods is None:
            return
        self.methods.WmiSetBrightness(brightness, 0)

    def name(self):
        return "Internal"
