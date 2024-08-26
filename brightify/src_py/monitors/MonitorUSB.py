import threading
import time
from abc import abstractmethod
from typing import Optional

import usb1
import atexit

from brightify.src_py.monitors.MonitorBase import MonitorBase
from brightify.src_py.monitors.MonitorBase import logger


class MonitorUSB(MonitorBase):
    def __init__(self, device: usb1.USBDevice, usb_delay_ms: Optional[float] = 25):
        """
        Initializes the MonitorUSB instance.
        :param device: USB device instance.
        :param usb_delay_ms: Optional delay in milliseconds between USB interactions.
        """
        try:
            if device.getProductID() != self.pid() or device.getVendorID() != self.vid():
                logger.warning("The device passed is not this monitor!")

            super().__init__()
            # make sure the device is closed on exit
            atexit.register(self.__del__)
            self.__device = device
            self.__has_delay = usb_delay_ms is not None

            if self.__has_delay:
                self.usb_delay_ns: int = int(usb_delay_ms * 1000000)
                self.last_interaction_ns = time.time_ns()

            self.lock = threading.Lock()
        except Exception as e:
            logger.error(f"Error initializing MonitorUSB: {e}", exc_info=True)

    def time_to_wait_sec(self) -> float:
        """
        Calculates the time to wait in seconds until the next interaction.
        :return: Time to wait in seconds.
        """
        try:
            return (self.last_interaction_ns + self.usb_delay_ns - time.time_ns()) / 1e9
        except Exception as e:
            logger.error(f"Error calculating time to wait: {e}", exc_info=True)
            return 0

    def is_ready(self) -> bool:
        """
        Checks if the monitor is ready for interaction.
        :return: True if ready, False otherwise.
        """
        try:
            if self.__has_delay:
                return time.time_ns() - self.last_interaction_ns >= self.usb_delay_ns
            return True
        except Exception as e:
            logger.error(f"Error checking readiness: {e}", exc_info=True)
            return False

    def clamp_brightness(self, b: Optional[int]) -> Optional[int]:
        """
        Clamps the brightness value within the allowed range.
        :param b: Brightness value.
        :return: Clamped brightness value.
        """
        try:
            if b is None:
                return None
            return max(min(b, self.max_brightness), self.min_brightness)
        except Exception as e:
            logger.error(f"Error clamping brightness: {e}", exc_info=True)
            return None

    @staticmethod
    @abstractmethod
    def vid() -> int:
        """
        Returns the vendor ID of the monitor.
        :return: Vendor ID.
        """
        pass

    @staticmethod
    @abstractmethod
    def pid() -> int:
        """
        Returns the product ID of the monitor.
        :return: Product ID.
        """
        pass

    @property
    def device(self) -> usb1.USBDevice:
        """
        Returns the USB device instance.
        :return: USB device.
        """
        return self.__device

    @staticmethod
    def get_type() -> str:
        """
        Returns the type of the monitor.
        :return: Monitor type.
        """
        return "USB"

    def __del__(self):
        """
        Destructor to ensure the USB device is properly closed.
        """
        try:
            if self.__device is not None:
                logger.info(f"Closing monitor {self.name()}")
                self.__device.close()
                self.__device = None
                super().__del__()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
