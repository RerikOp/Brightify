from typing import List, Optional
import time
import usb1

from brightify.src_py.monitors.MonitorUSB import MonitorUSB
from brightify.src_py.monitors.MonitorBase import logger
from brightify.src_py.monitors.vpc import VCPCodeDefinition


class M27Q(MonitorUSB):

    def __init__(self, device: usb1.USBDevice):
        """
        Initializes the M27Q monitor instance.
        :param device: USB device instance.
        """
        super().__init__(device)
        self.max_tries = 9
        self.luminance_code = VCPCodeDefinition.image_luminance.value

    @staticmethod
    def vid() -> int:
        """
        Returns the vendor ID of the monitor.
        :return: Vendor ID.
        """
        return 0x2109

    @staticmethod
    def pid() -> int:
        """
        Returns the product ID of the monitor.
        :return: Product ID.
        """
        return 0x8883

    def name(self) -> str:
        """
        Returns the name of the monitor.
        :return: Monitor name.
        """
        return "M27Q"

    def usb_write(self, b_request: int, w_value: int, w_index: int, message: bytes):
        """
        Writes data to the USB device.
        :param b_request: Request type.
        :param w_value: Value.
        :param w_index: Index.
        :param message: Message to send.
        """
        bm_request_type = 0x40

        try:
            with usb1.USBContext() as context:
                handle = context.openByVendorIDAndProductID(self.vid(), self.pid())
                if handle is None:
                    logger.error("Could not open device")
                    return
                bytes_sent = handle.controlWrite(bm_request_type, b_request, w_value, w_index, message)
                if bytes_sent != len(message):
                    logger.error("Transferred message length mismatch")
        except usb1.USBError as e:
            logger.error(f"USB write error: {e}")

        self.last_interaction_ns = time.time_ns()

    def usb_read(self, b_request: int, w_value: int, w_index: int, msg_length: int) -> Optional[bytearray]:
        """
        Reads data from the USB device.
        :param b_request: Request type.
        :param w_value: Value.
        :param w_index: Index.
        :param msg_length: Length of the message to read.
        :return: Data read from the device.
        """
        bm_request_type = 0xC0

        try:
            with usb1.USBContext() as context:
                handle = context.openByVendorIDAndProductID(self.vid(), self.pid())
                if handle is None:
                    logger.error("Could not open device")
                    return None
                data: bytearray = handle.controlRead(bm_request_type, b_request, w_value, w_index, msg_length)
        except usb1.USBError as e:
            logger.error(f"USB read error: {e}")
            return None

        self.last_interaction_ns = time.time_ns()
        return data

    def get_osd(self, data: List[int] | bytearray) -> Optional[int]:
        """
        Gets the On-Screen Display (OSD) value.
        :param data: Data to send.
        :return: OSD value.
        """
        self.usb_write(
            b_request=178,
            w_value=0,
            w_index=0,
            message=bytearray([0x6E, 0x51, 0x81 + len(data), 0x01]) + bytearray(data)
        )
        data = self.usb_read(b_request=162, w_value=0, w_index=111, msg_length=12)
        if data is None:
            return None
        return data[10]

    def set_osd(self, data: List[int] | bytearray):
        """
        Sets the On-Screen Display (OSD) value.
        :param data: Data to send.
        """
        self.usb_write(
            b_request=178,
            w_value=0,
            w_index=0,
            message=bytearray([0x6E, 0x51, 0x81 + len(data), 0x03]) + bytearray(data)
        )

    def set_brightness(self, brightness: int, blocking=False, force: bool = False):
        """
        Sets the brightness of the monitor.
        :param brightness: Brightness value.
        :param blocking: If True, block until the brightness is set.
        :param force: If True, force the setting.
        """
        max_tries = 1 if not blocking and not force else self.max_tries
        blocking = blocking or force  # force implies blocking

        def _set() -> bool:
            try:
                with self.lock:
                    self.set_osd([self.luminance_code, 0x00, brightness])
                return True
            except Exception as e:
                logger.error(f"Failed to set brightness: {e}")
                return False

        brightness = self.clamp_brightness(brightness)
        for _ in range(max_tries):
            if blocking:
                self.wait()
                if _set():
                    self.last_set_brightness = brightness
                    return
            else:
                if self.is_ready() and _set():
                    self.last_set_brightness = brightness
                    return

    def get_brightness(self, blocking=False, force: bool = False) -> Optional[int]:
        """
        Gets the brightness of the monitor.
        :param blocking: If True, block until the brightness is retrieved.
        :param force: If True, force the retrieval.
        :return: Brightness value.
        """
        max_tries = 1 if not blocking and not force else self.max_tries
        brightness_values = []
        blocking = blocking or force  # force implies blocking

        def _get() -> Optional[int]:
            try:
                with self.lock:
                    return self.get_osd([self.luminance_code])
            except Exception as e:
                logger.error(f"Failed to get brightness: {e}")
                return None

        for _ in range(max_tries):
            if blocking:
                self.wait()
                if (brightness := _get()) is not None:
                    brightness_values.append(brightness)
                    if not force:
                        self.last_get_brightness = brightness
                        return brightness
            else:
                if self.is_ready() and (brightness := _get()) is not None:
                    brightness_values.append(brightness)
                    if not force:
                        self.last_get_brightness = brightness
                        return brightness

        if force and brightness_values:
            # Determine the majority value
            majority_brightness = max(set(brightness_values), key=brightness_values.count)
            self.last_get_brightness = majority_brightness
            return majority_brightness

        return None
