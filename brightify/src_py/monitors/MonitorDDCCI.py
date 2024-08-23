from typing import Optional

import monitorcontrol

from brightify.src_py.monitors.MonitorBase import MonitorBase
from brightify.src_py.monitors.MonitorBase import logger


class MonitorDDCCI(MonitorBase):
    def __init__(self, device: monitorcontrol.Monitor):
        # monitorcontrol.Monitor always uses 0-100 as brightness range
        super().__init__(0, 100)
        self.monitor = device
        # DDC/CI is annoying, so we try multiple times
        self.max_tries = 10
        # VCP capabilities
        self.vcp_cap, self.__name, self.is_unknown = {}, MonitorDDCCI.default_name(), True
        # Try to get the VCP capabilities
        self.update_cap()

    def update_cap(self):
        with self.monitor:
            try:
                vcp_cap = self.monitor.get_vcp_capabilities()
                # sometimes the dict is broken
                if vcp_cap.get('model', None) is not None:
                    self.vcp_cap, self.__name, self.is_unknown = vcp_cap, vcp_cap['model'], False
            except monitorcontrol.vcp.vcp_abc.VCPError:
                pass

    def name(self):
        return self.__name

    @staticmethod
    def default_name():
        return "Monitor"

    @staticmethod
    def get_type():
        return "DDCCI"

    def get_brightness(self, blocking: bool = False, force: bool = False) -> Optional[int]:
        max_tries = 1 if not blocking and not force else self.max_tries
        for _ in range(max_tries):
            with self.monitor:
                try:
                    return self.monitor.get_luminance()
                except monitorcontrol.vcp.vcp_abc.VCPError:
                    pass
        logger.debug(f"Failed to get luminance of DDCCI monitor \"{self.name()}\"")
        return None

    def set_brightness(self, brightness: int, blocking: bool = False, force: bool = False) -> None:
        max_tries = 1 if not blocking and not force else self.max_tries
        for _ in range(max_tries):
            with self.monitor:
                try:
                    self.monitor.set_luminance(brightness)
                    return
                except monitorcontrol.vcp.vcp_abc.VCPError:
                    pass
        logger.debug(f"Failed to set luminance of DDCCI monitor \"{self.name()}\"")
