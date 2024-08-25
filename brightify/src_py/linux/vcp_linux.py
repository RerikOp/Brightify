from brightify.src_py.monitors.vpc import VCP, VCPIOError, VCPPermissionError
from types import TracebackType
from typing import List, Optional, Tuple, Type
import os
import struct
import time
import logging
import fcntl
import pyudev


class LinuxVCP(VCP):
    """
    Linux API access to a monitor's virtual control panel.

    References:
        https://github.com/Informatic/python-ddcci
        https://github.com/siemer/ddcci/

    Code adapted from:
        https://github.com/newAM/monitorcontrol
    """

    GET_VCP_HEADER_LENGTH = 2  # header packet length
    PROTOCOL_FLAG = 0x80  # protocol flag is bit 7 of the length byte

    # VCP commands
    GET_VCP_CMD = 0x01  # get VCP feature command
    GET_VCP_REPLY = 0x02  # get VCP feature reply code
    SET_VCP_CMD = 0x03  # set VCP feature command
    GET_VCP_CAPS_CMD = 0xF3  # Capabilities Request command
    GET_VCP_CAPS_REPLY = 0xE3  # Capabilities Request reply

    # timeouts
    GET_VCP_TIMEOUT = 0.04  # at least 40ms per the DDCCI specification
    CMD_RATE = 0.05  # at least 50ms between messages

    # addresses
    DDCCI_ADDR = 0x37  # DDC-CI command address on the I2C bus
    HOST_ADDRESS = 0x51  # virtual I2C slave address of the host
    I2C_SLAVE = 0x0703  # I2C bus slave address

    GET_VCP_RESULT_CODES = {
        0: "No Error",
        1: "Unsupported VCP code",
    }

    CHECKSUM_ERRORS: str = "ignore"

    def __init__(self, bus_number: int):
        """
        Initializes the LinuxVCP class.
        :param bus_number: I2C bus number.
        """
        self.logger = logging.getLogger(__name__)
        self.bus_number = bus_number
        self.fd: Optional[str] = None
        self.fp: str = f"/dev/i2c-{self.bus_number}"
        self.last_set: Optional[float] = None

    def __enter__(self):
        """
        Enters the runtime context related to this object.
        :return: self
        """
        def cleanup(fd: Optional[int]):
            if fd is not None:
                try:
                    os.close(self.fd)
                except OSError:
                    pass

        try:
            self.fd = os.open(self.fp, os.O_RDWR)
            fcntl.ioctl(self.fd, self.I2C_SLAVE, self.DDCCI_ADDR)
            self.read_bytes(1)
        except PermissionError as e:
            cleanup(self.fd)
            raise VCPPermissionError(f"permission error for {self.fp}") from e
        except OSError as e:
            cleanup(self.fd)
            raise VCPIOError(f"unable to open VCP at {self.fp}") from e
        except Exception as e:
            cleanup(self.fd)
            raise e
        return self

    def __exit__(
        self,
        exception_type: Optional[Type[BaseException]],
        exception_value: Optional[BaseException],
        exception_traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        """
        Exits the runtime context related to this object.
        :param exception_type: exception type
        :param exception_value: exception value
        :param exception_traceback: exception traceback
        :return: False
        """
        try:
            os.close(self.fd)
        except OSError as e:
            raise VCPIOError("unable to close descriptor") from e
        self.fd = None

        return False

    def set_vcp_feature(self, code: int, value: int):
        """
        Sets the value of a feature on the virtual control panel.
        :param code: feature code
        :param value: feature value
        :raises VCPIOError: failed to set VCP feature
        """
        self.rate_limt()

        data = bytearray()
        data.append(self.SET_VCP_CMD)
        data.append(code)
        low_byte, high_byte = struct.pack("H", value)
        data.append(high_byte)
        data.append(low_byte)

        data.insert(0, (len(data) | self.PROTOCOL_FLAG))
        data.insert(0, self.HOST_ADDRESS)
        data.append(self.get_checksum(bytearray([self.DDCCI_ADDR << 1]) + data))

        self.logger.debug("data=" + " ".join([f"{x:02X}" for x in data]))
        self.write_bytes(data)

        self.last_set = time.time()

    def get_vcp_feature(self, code: int) -> Tuple[int, int]:
        """
        Gets the value of a feature from the virtual control panel.
        :param code: Feature code.
        :return: Current feature value, maximum feature value.
        :raises VCPIOError: Failed to get VCP feature.
        """
        self.rate_limt()

        data = bytearray()
        data.append(self.GET_VCP_CMD)
        data.append(code)

        data.insert(0, (len(data) | self.PROTOCOL_FLAG))
        data.insert(0, self.HOST_ADDRESS)
        data.append(self.get_checksum(bytearray([self.DDCCI_ADDR << 1]) + data))

        self.logger.debug("data=" + " ".join([f"{x:02X}" for x in data]))
        self.write_bytes(data)

        time.sleep(self.GET_VCP_TIMEOUT)

        header = self.read_bytes(self.GET_VCP_HEADER_LENGTH)
        self.logger.debug("header=" + " ".join([f"{x:02X}" for x in header]))
        source, length = struct.unpack("=BB", header)
        length &= ~self.PROTOCOL_FLAG
        payload = self.read_bytes(length + 1)
        self.logger.debug("payload=" + " ".join([f"{x:02X}" for x in payload]))

        payload, checksum = struct.unpack(f"={length}sB", payload)
        calculated_checksum = self.get_checksum(header + payload)
        checksum_xor = checksum ^ calculated_checksum
        if checksum_xor:
            message = f"checksum does not match: {checksum_xor}"
            if self.CHECKSUM_ERRORS.lower() == "strict":
                raise VCPIOError(message)
            elif self.CHECKSUM_ERRORS.lower() == "warning":
                self.logger.warning(message)

        reply_code, result_code, vcp_opcode, vcp_type_code, feature_max, feature_current = struct.unpack(">BBBBHH", payload)

        if reply_code != self.GET_VCP_REPLY:
            raise VCPIOError(f"received unexpected response code: {reply_code}")

        if vcp_opcode != code:
            raise VCPIOError(f"received unexpected opcode: {vcp_opcode}")

        if result_code > 0:
            try:
                message = self.GET_VCP_RESULT_CODES[result_code]
            except KeyError:
                message = f"received result with unknown code: {result_code}"
            raise VCPIOError(message)

        return feature_current, feature_max

    def get_vcp_capabilities(self) -> str:
        """
        Gets capabilities string from the virtual control panel.
        :return: Capabilities string.
        :raises VCPIOError: Failed to get VCP feature.
        """
        caps_str = ""
        self.rate_limt()
        offset = 0
        loop_count = 0
        loop_count_limit = 40

        while loop_count < loop_count_limit:
            loop_count += 1

            data = bytearray()
            data.append(self.GET_VCP_CAPS_CMD)
            low_byte, high_byte = struct.pack("H", offset)
            data.append(high_byte)
            data.append(low_byte)

            data.insert(0, (len(data) | self.PROTOCOL_FLAG))
            data.insert(0, self.HOST_ADDRESS)
            data.append(self.get_checksum(data))

            self.write_bytes(data)

            time.sleep(self.GET_VCP_TIMEOUT)

            header = self.read_bytes(self.GET_VCP_HEADER_LENGTH)
            self.logger.debug("header=" + " ".join([f"{x:02X}" for x in header]))
            source, length = struct.unpack("BB", header)
            length &= ~self.PROTOCOL_FLAG
            payload = self.read_bytes(length + 1)
            self.logger.debug("payload=" + " ".join([f"{x:02X}" for x in payload]))

            if length < 3 or length > 35:
                raise VCPIOError(f"received unexpected response length: {length}")

            payload, checksum = struct.unpack(f"{length}sB", payload)
            calculated_checksum = self.get_checksum(header + payload)
            checksum_xor = checksum ^ calculated_checksum
            if checksum_xor:
                message = f"checksum does not match: {checksum_xor}"
                if self.CHECKSUM_ERRORS.lower() == "strict":
                    raise VCPIOError(message)
                elif self.CHECKSUM_ERRORS.lower() == "warning":
                    self.logger.warning(message)

            reply_code, payload = struct.unpack(f">B{length-1}s", payload)
            length -= 1

            if reply_code != self.GET_VCP_CAPS_REPLY:
                raise VCPIOError(f"received unexpected response code: {reply_code}")

            offset, payload = struct.unpack(f">H{length-2}s", payload)
            length -= 2

            if length > 0:
                caps_str += payload.decode("ASCII")
            else:
                break

            offset += length

        self.logger.debug(f"caps str={caps_str}")

        if loop_count >= loop_count_limit:
            raise VCPIOError("Capabilities string incomplete or too long")

        return caps_str

    @staticmethod
    def get_checksum(data: bytearray) -> int:
        """
        Computes the checksum for a set of data, with the option to
        use the virtual host address (per the DDC-CI specification).
        :param data: Data array to transmit.
        :return: Checksum for the data.
        """
        checksum = 0x00
        for data_byte in data:
            checksum ^= data_byte
        return checksum

    def rate_limt(self):
        """
        Rate limits messages to the VCP.
        """
        if self.last_set is None:
            return

        rate_delay = self.CMD_RATE - time.time() - self.last_set
        if rate_delay > 0:
            time.sleep(rate_delay)

    def read_bytes(self, num_bytes: int) -> bytes:
        """
        Reads bytes from the I2C bus.
        :param num_bytes: number of bytes to read
        :raises VCPIOError: unable to read data
        """
        try:
            return os.read(self.fd, num_bytes)
        except OSError as e:
            raise VCPIOError("unable to read from I2C bus") from e

    def write_bytes(self, data: bytes):
        """
        Writes bytes to the I2C bus.
        :param data: data to write to the I2C bus
        :raises VCPIOError: unable to write data
        """
        try:
            os.write(self.fd, data)
        except OSError as e:
            raise VCPIOError("unable write to I2C bus") from e


def get_vcps() -> List[LinuxVCP]:
    """
    Interrogates I2C buses to determine if they are DDC-CI capable.
    :return: List of all VCPs detected.
    """
    vcps = []

    for device in pyudev.Context().list_devices(subsystem="i2c"):
        vcp = LinuxVCP(device.sys_number)
        try:
            with vcp:
                pass
        except (OSError, VCPIOError):
            pass
        else:
            vcps.append(vcp)

    return vcps