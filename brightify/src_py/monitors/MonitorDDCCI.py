from typing import Optional

from brightify.src_py.monitors.MonitorBase import MonitorBase, logger
from brightify.src_py.monitors.vpc import VCP, VCPError, VCPCode, VCPCodeDefinition, parse_capabilities


class MonitorDDCCI(MonitorBase):
    def __init__(self, vcp: VCP):
        # monitorcontrol.Monitor always uses 0-100 as brightness range
        super().__init__(0, 100)
        # The virtual control panel backend
        self.vcp = vcp
        # The luminance code
        self.luminance_code = VCPCodeDefinition.image_luminance
        # Getting the capabilities can fail, so we try multiple times
        self.max_tries = 10
        # Store the max value of the codes
        self.code_max = {}

        # Check if VCP provides a name
        if (name := self.vcp.name) is not None:
            self.__name = name
        else:
            self.__name = self.default_name()
            # Try to get the name from the VCP capabilities
            self.update_cap()

    def is_unknown(self):
        return self.__name == self.default_name()

    def _get_code_maximum(self, code: VCPCode) -> int:
        """
        Gets the maximum values for a given code, and caches it in the class dictionary if not already found.

        :param code: Feature code definition class.
        :returns: Maximum value for the given code.
        """
        if not code.readable:
            logger.error(f"Code is not readable: {code}")
        if code.value in self.code_max:
            return self.code_max[code.value]
        else:
            _, maximum = self.vcp.get_vcp_feature(code.value)
            self.code_max[code.value] = maximum
            return maximum

    def _set_vcp_feature(self, code: VCPCode, value: int):
        """
        Sets the value of a feature on the virtual control panel. This function must be run within the context manager

        :param code: Feature code.
        :param value: Feature value.
        """
        if code.type == "ro":
            logger.error(f"Cannot write read-only code: {code}")
            return
        elif code.type == "rw" and code.function == "c":
            maximum = self._get_code_maximum(code)
            if value > maximum:
                logger.error(f"Cannot set value greater than maximum: {code}")
                return
        try:
            self.vcp.set_vcp_feature(code.value, value)
        except VCPError:
            pass

    def _get_vcp_feature(self, code: VCPCode) -> Optional[int]:
        """
        Gets the value of a feature from the virtual control panel without raising exceptions.

        :param code: Feature code.
        :returns: Current feature value.
        """
        if code.type == "wo":
            logger.error(f"Cannot read write-only code: {code}")
            return None
        try:
            current, maximum = self.vcp.get_vcp_feature(code.value)
            self.code_max[code] = maximum
            return current
        except VCPError:
            return None

    def update_cap(self, force: bool = False):
        num_tries = 1 if not force else self.max_tries
        with self.vcp:
            for _ in range(num_tries):
                try:
                    cap_str = self.vcp.get_vcp_capabilities()
                    vcp_cap = parse_capabilities(cap_str)
                    # sometimes the dict is broken
                    if (name := vcp_cap.model) is not None:
                        self.__name = name
                        break
                except VCPError as _:
                    pass  # The monitor does not send capabilities

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
            with self.vcp:
                try:
                    if (brightness := self._get_vcp_feature(self.luminance_code)) is not None:
                        return brightness
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
        logger.debug(f"Failed to get brightness of DDCCI monitor \"{self.name()}\"")
        return None

    def set_brightness(self, brightness: int, blocking: bool = False, force: bool = False) -> None:
        max_tries = 1 if not blocking and not force else self.max_tries
        for _ in range(max_tries):
            with self.vcp:
                try:
                    self._set_vcp_feature(self.luminance_code, brightness)
                    return
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
        logger.debug(f"Failed to set brightness of DDCCI monitor \"{self.name()}\"")
