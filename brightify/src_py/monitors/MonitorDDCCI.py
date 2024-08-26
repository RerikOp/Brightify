from typing import Optional

from brightify.src_py.monitors.MonitorBase import MonitorBase, logger
from brightify.src_py.monitors.vpc import VCP, VCPError, VCPCode, VCPCodeDefinition, parse_capabilities


class MonitorDDCCI(MonitorBase):
    def __init__(self, vcp: VCP):
        """
        Initializes the MonitorDDCCI instance.
        :param vcp: VCP instance for virtual control panel backend.
        """
        super().__init__(0, 100)
        self.vcp = vcp
        self.luminance_code = VCPCodeDefinition.image_luminance
        self.max_tries = 10
        self.code_max = {}

        if (name := self.vcp.name) is not None:
            self.__name = name
        else:
            self.__name = self.default_name()
            self.update_cap()

    def is_unknown(self) -> bool:
        """
        Checks if the monitor name is unknown.
        :return: True if unknown, False otherwise.
        """
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
            try:
                _, maximum = self.vcp.get_vcp_feature(code.value)
                self.code_max[code.value] = maximum
                return maximum
            except VCPError as e:
                logger.error(f"Error getting VCP feature: {e}")
                return 0

    def _set_vcp_feature(self, code: VCPCode, value: int):
        """
        Sets the value of a feature on the virtual control panel. This function must be run within the context manager.
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
        except VCPError as e:
            logger.error(f"Error setting VCP feature: {e}")

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
            self.code_max[code.value] = maximum
            return current
        except VCPError as e:
            logger.error(f"Error getting VCP feature: {e}")
            return None

    def update_cap(self, force: bool = False):
        """
        Updates the monitor capabilities.
        :param force: Force update if True.
        """
        num_tries = 1 if not force else self.max_tries
        with self.vcp:
            for _ in range(num_tries):
                try:
                    cap_str = self.vcp.get_vcp_capabilities()
                    vcp_cap = parse_capabilities(cap_str)
                    if (name := vcp_cap.model) is not None:
                        self.__name = name
                        break
                except VCPError as e:
                    logger.error(f"Error updating capabilities: {e}")

    def name(self) -> str:
        """
        Returns the name of the monitor.
        :return: Monitor name.
        """
        return self.__name

    @staticmethod
    def default_name() -> str:
        """
        Returns the default name of the monitor.
        :return: Default monitor name.
        """
        return "Monitor"

    @staticmethod
    def get_type() -> str:
        """
        Returns the type of the monitor.
        :return: Monitor type.
        """
        return "DDCCI"

    def get_brightness(self, blocking: bool = False, force: bool = False) -> Optional[int]:
        """
        Gets the brightness of the monitor.
        :param blocking: If True, block until the brightness is retrieved.
        :param force: If True, force the retrieval.
        :return: Brightness value.
        """
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
        """
        Sets the brightness of the monitor.
        :param brightness: Brightness value.
        :param blocking: If True, block until the brightness is set.
        :param force: If True, force the setting.
        """
        max_tries = 1 if not blocking and not force else self.max_tries
        for _ in range(max_tries):
            with self.vcp:
                try:
                    self._set_vcp_feature(self.luminance_code, brightness)
                    return
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
        logger.debug(f"Failed to set brightness of DDCCI monitor \"{self.name()}\"")