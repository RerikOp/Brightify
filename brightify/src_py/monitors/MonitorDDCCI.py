from typing import Optional

from brightify.src_py.monitors.MonitorBase import MonitorBase, logger
from brightify.src_py.monitors.vpc import VCP, VCPError, VCPCode, VCPCodeDefinition, parse_capabilities, Capabilities


class MonitorDDCCI(MonitorBase):
    def __init__(self, vcp: VCP):
        """
        Initializes the MonitorDDCCI instance.
        :param vcp: VCP instance for virtual control panel backend.
        """
        super().__init__(0, 100)
        self.vcp = vcp
        self.luminance_code = VCPCodeDefinition.image_luminance
        self.max_tries = 3
        self.code_max = {}

        if (name := self.vcp.name) is not None:
            self.__name = name
        else:
            self.__name = self.default_name()
        # May take a while to get capabilities, so only do it on demand
        self.capabilities: Optional[Capabilities] = None

    def is_unknown(self) -> bool:
        """
        Checks if the monitor name is unknown.
        :return: True if unknown, False otherwise.
        """
        return self.__name == self.default_name()

    def _get_code_maximum(self, code: VCPCode) -> Optional[int]:
        """
        Gets the maximum values for a given code, and caches it in the class dictionary if not already found.
        :param code: Feature code definition class.
        :returns: Maximum value for the given code if found or requested successfully, None otherwise.
        """
        if not code.readable:
            logger.error(f"Code is not readable: {code}")
            return None
        if code.value in self.code_max:
            return self.code_max[code.value]
        else:
            try:
                _, maximum = self.vcp.get_vcp_feature(code.value)
                self.code_max[code.value] = maximum
                return maximum
            except VCPError as _:
                return None
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return None

    def _set_vcp_feature(self, code: VCPCode, value: int) -> bool:
        """
        Sets the value of a feature on the virtual control panel without raising exceptions.
        This function must be run within the context manager.
        :param code: Feature code.
        :param value: Feature value.
        :returns: True if successful, False otherwise.
        """
        if code.type == "ro":
            logger.error(f"Cannot write read-only code: {code}")
            return False
        elif code.type == "rw" and code.function == "c":
            maximum = self._get_code_maximum(code)
            if maximum is None:
                return False
            elif value > maximum:
                logger.error(f"Cannot set value greater than maximum: {code}")
                return False
        try:
            self.vcp.wait()
            self.vcp.set_vcp_feature(code.value, value)
            return True
        except VCPError as _:
            pass
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        return False

    def _get_vcp_feature(self, code: VCPCode) -> Optional[int]:
        """
        Gets the value of a feature from the virtual control panel without raising exceptions.
        This function must be run within the context manager.
        :param code: Feature code.
        :returns: Current feature value if successful, None otherwise.
        """
        if code.type == "wo":
            logger.error(f"Cannot read write-only code: {code}")
            return None
        try:
            self.vcp.wait()
            current, maximum = self.vcp.get_vcp_feature(code.value)
            self.code_max[code.value] = maximum
            return current
        except VCPError as _:
            pass
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
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
                    capabilities = parse_capabilities(cap_str)
                    if (name := capabilities.model) is not None:
                        self.__name = name
                    if self.capabilities is None:
                        self.capabilities = capabilities
                except VCPError as _:
                    pass
        logger.debug(f"Failed to get capabilities of DDCCI monitor \"{self.name()}\"")

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
        :return: Brightness value if successful, None otherwise.
        """
        max_tries = 1 if not blocking and not force else self.max_tries
        brightness_values = []
        for _ in range(max_tries):
            with self.vcp:
                if (brightness := self._get_vcp_feature(self.luminance_code)) is not None:
                    brightness_values.append(brightness)
                    if not force:
                        self.last_get_brightness = brightness
                        return brightness

        if force and brightness_values:
            # Determine the majority value
            majority_brightness = max(set(brightness_values), key=brightness_values.count)
            self.last_get_brightness = majority_brightness
            return majority_brightness

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
        with self.vcp:
            for _ in range(max_tries):
                if self._set_vcp_feature(self.luminance_code, brightness):
                    self.last_set_brightness = brightness
                    return
        logger.debug(f"Failed to set brightness of DDCCI monitor \"{self.name()}\"")

    def __del__(self):
        """
        Destructor to ensure the VCP instance is properly closed.
        """
        try:
            self.vcp.close()
            super().__del__()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)

