from typing import Optional, override, Dict

import monitorcontrol

from brightify.monitors.MonitorBase import MonitorBase
from brightify.monitors.MonitorBase import logger


# TODO is an internal Monitor also connected via DDCCI?
class MonitorDDCCI(MonitorBase):
    def __init__(self, device: monitorcontrol.Monitor):
        # monitorcontrol.Monitor always uses 0-100 as brightness range
        super().__init__(0, 100)
        self.monitor = device
        # DDC-CI is annoying, so we try multiple times
        self.max_tries = 10
        # Try to get the VCP capabilities
        self.vcp_cap = self.__vcp_cap()
        self.__name = self.vcp_cap.get('model', MonitorDDCCI.default_name())
        self.is_unknown = self.__name == MonitorDDCCI.default_name()
        logger.info(f"Found DDCCI Monitor {self.__name}")

    def __vcp_cap(self) -> Dict:
        with self.monitor:
            for _ in range(self.max_tries):
                try:
                    vcp_cap = self.monitor.get_vcp_capabilities()
                    # sometimes the dict is broken
                    if vcp_cap.get('model', None) is not None:
                        return vcp_cap
                except monitorcontrol.vcp.vcp_abc.VCPError:
                    pass
        return {}

    def name(self):
        return self.__name

    @staticmethod
    def default_name():
        return "Monitor"

    @override
    def get_brightness(self, blocking: bool = False, force: bool = False) -> Optional[int]:
        max_tries = 1 if not blocking and not force else self.max_tries
        for _ in range(max_tries):
            with self.monitor:
                try:
                    return self.monitor.get_luminance()
                except monitorcontrol.vcp.vcp_abc.VCPError:
                    pass
        logger.debug(f"Failed to get luminance of CCDDI monitor {self.name()}")
        return None

    @override
    def set_brightness(self, brightness: int, blocking: bool = False, force: bool = False) -> None:
        max_tries = 1 if not blocking and not force else self.max_tries
        for _ in range(max_tries):
            with self.monitor:
                try:
                    self.monitor.set_luminance(brightness)
                    return
                except monitorcontrol.vcp.vcp_abc.VCPError:
                    pass
        logger.debug(f"Failed to set luminance of CCDDI monitor {self.name()}")