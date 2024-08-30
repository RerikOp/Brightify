import fcntl
import os
import struct
import time
import pyudev
from types import TracebackType
from typing import List, Optional, Tuple, Type, Literal
from brightify.src_py.monitors.vpc import VCP, VCPIOError, VCPPermissionError, VCPError
from brightify.src_py.linux import logger

# Constants
GET_VCP_HEADER_LENGTH = 2  # Header packet length
PROTOCOL_FLAG = 0x80  # Protocol flag is bit 7 of the length byte

# VCP commands
GET_VCP_CMD = 0x01  # Get VCP feature command
GET_VCP_REPLY = 0x02  # Get VCP feature reply code
SET_VCP_CMD = 0x03  # Set VCP feature command
GET_VCP_CAPS_CMD = 0xF3  # Capabilities Request command
GET_VCP_CAPS_REPLY = 0xE3  # Capabilities Request reply

# Timeouts
GET_VCP_TIMEOUT_SEC = 0.04  # At least 40ms per the DDCCI specification

# Addresses
DDCCI_ADDR = 0x37  # DDC-CI command address on the I2C bus
EDID_ADDR = 0x50  # EDID address on the I2C bus
HOST_ADDRESS = 0x51  # Virtual I2C slave address of the host
I2C_SLAVE = 0x0703  # I2C bus slave address

# VCP result codes
GET_VCP_RESULT_CODES = {
    0: "No Error",
    1: "Unsupported VCP code",
}


def secure_unpack(fmt: str, data: bytes) -> Tuple:
    """
    Securely unpacks data using the given format, catching struct.error.
    :param fmt: Format string.
    :param data: Data to unpack.
    :return: Unpacked data as a tuple.
    :raises VCPIOError: If unpacking fails.
    """
    try:
        return struct.unpack(fmt, data)
    except struct.error as e:
        raise VCPIOError(f"Failed to unpack data: {e}") from e

class LinuxVCP(VCP):
    """
    Linux API access to a monitor's virtual control panel.
    """

    def __init__(self, bus_number: int, checksum_errors: Literal["ignore", "strict"] = "ignore"):
        """
        Initializes the LinuxVCP class.
        :param bus_number: I2C bus number.
        :param checksum_errors: How to handle checksum errors.
        """
        super().__init__()
        self.bus_number = bus_number
        self.fd: Optional[int] = None
        self.fp: str = f"/dev/i2c-{self.bus_number}"
        self.checksum_errors = checksum_errors
        self.max_tries = 10
        self.in_context = False
        self.verify_permissions()

    def close(self):
        """
        Closes the file descriptor.
        """
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass

    def __enter__(self):
        self.in_context = True
        try:
            self.fd = os.open(self.fp, os.O_RDWR)
            fcntl.ioctl(self.fd, I2C_SLAVE, DDCCI_ADDR)
            self.read_bytes(1)
        except PermissionError as e:
            raise VCPPermissionError(f"Permission error for {self.fp}") from e
        except OSError as e:
            raise VCPIOError(f"Unable to open VCP at {self.fp}") from e
        except Exception as e:
            raise VCPIOError(f"Unknown error opening VCP at {self.fp}") from e
        return self

    def __exit__(
            self,
            exception_type: Optional[Type[BaseException]],
            exception_value: Optional[BaseException],
            exception_traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        self.in_context = False
        return False

    def verify_permissions(self) -> bool:
        """
        Verifies if the current process has the necessary permissions.
        :return: True if permissions are sufficient, False otherwise.
        """
        import grp
        if os.geteuid() == 0:
            return True
        try:
            file_stat = os.stat(self.fp)
        except FileNotFoundError:
            logger.error(f"File not found: {self.fp}")
            return False
        grp_info = grp.getgrgid(file_stat.st_gid)
        grp_name = grp_info.gr_name
        grp_id = grp_info.gr_gid

        if grp_name != "i2c":
            logger.warning(f"File {self.fp} is not owned by the i2c group and you are not root. Refer to README.")
            return False

        if not (file_stat.st_mode & 0o660):
            logger.warning(f"File {self.fp} does not have read/write permissions for the i2c group. Refer to README.")
            return False

        if grp_id not in os.getgroups():
            logger.warning(f"Process is not in the i2c group. This will most likely not work."
                           f" If running 'groups $USER' does show i2c but this fails, try restarting your system.")
            return False
        return True

    def set_vcp_feature(self, code: int, value: int):
        """
        Sets the value of a feature on the virtual control panel.
        :param code: Feature code.
        :param value: Feature value.
        :raises VCPIOError: Failed to set VCP feature.
        """
        if not self.in_context:
            raise VCPError("Not in VCP context")

        self.wait()

        data = self._prepare_data(SET_VCP_CMD, code, value)
        self.write_bytes(data)

    def get_vcp_feature(self, code: int) -> Tuple[int, int]:
        """
        Gets the value of a feature from the virtual control panel.
        :param code: Feature code.
        :return: Current feature value, maximum feature value.
        :raises VCPIOError: Failed to get VCP feature.
        """
        if not self.in_context:
            raise VCPError("Not in VCP context")

        self.wait()

        data = self._prepare_data(GET_VCP_CMD, code)
        self.write_bytes(data)

        time.sleep(GET_VCP_TIMEOUT_SEC)

        header, payload = self._read_response()
        self._validate_response(header, payload, GET_VCP_REPLY, code)

        reply_code, result_code, vcp_opcode, vcp_type_code, feature_max, feature_current =\
            secure_unpack(">BBBBHH", payload)

        if result_code > 0:
            message = GET_VCP_RESULT_CODES.get(result_code, f"Received result with unknown code: {result_code}")
            raise VCPIOError(message)

        return feature_current, feature_max

    def get_vcp_capabilities(self) -> str:
        """
        Gets capabilities string from the virtual control panel.
        :return: Capabilities string.
        :raises VCPIOError: Failed to get VCP feature.
        """
        if not self.in_context:
            raise VCPError("Not in VCP context")
        self.wait()
        caps_str = ""
        offset = 0
        for loop_count in range(self.max_tries):
            data = self._prepare_data(GET_VCP_CAPS_CMD, offset)
            self.write_bytes(data)

            time.sleep(GET_VCP_TIMEOUT_SEC)

            header, payload = self._read_response()
            self._validate_response(header, payload, GET_VCP_CAPS_REPLY)

            offset, payload = secure_unpack(f">H{len(payload) - 2}s", payload)

            if len(payload) > 0:
                caps_str += payload.decode("ascii")
            else:
                break
            offset += len(payload)
        else:
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

    def read_null_message(self) -> bytes:
        """
        Reads a NULL message from the display at the 0x6F I2C slave address.
        :return: The response from the display.
        :raises VCPIOError: If unable to read from the I2C bus.
        """
        if not self.in_context:
            raise VCPError("Not in VCP context")

        self.wait()

        # Prepare the NULL message data packet
        data = bytearray()
        data.append(0x80)  # Length byte with protocol flag
        data.insert(0, 0x6E)  # Source address
        data.insert(0, 0x6F)  # Destination address
        data.append(self.get_checksum(data))  # Checksum

        # Write the data packet to the I2C bus
        self.write_bytes(data)

        # Read the response from the I2C bus
        try:
            response = self.read_bytes(4)  # Adjust the number of bytes as needed
        except OSError as e:
            raise VCPIOError("Unable to read from I2C bus") from e

        return response

    def read_bytes(self, num_bytes: int) -> bytes:
        """
        Reads bytes from the I2C bus.
        :param num_bytes: Number of bytes to read.
        :raises VCPIOError: Unable to read data.
        """
        try:
            return os.read(self.fd, num_bytes)
        except OSError as e:
            raise VCPIOError("Unable to read from I2C bus") from e

    def write_bytes(self, data: bytes):
        """
        Writes bytes to the I2C bus.
        :param data: Data to write to the I2C bus.
        :raises VCPIOError: Unable to write data.
        """
        try:
            os.write(self.fd, data)
        except OSError as e:
            raise VCPIOError("Unable to write to I2C bus") from e

    def _prepare_data(self, cmd: int, *args) -> bytearray:
        """
        Prepares the data packet to be sent.
        :param cmd: Command byte.
        :param args: Additional arguments for the command.
        :return: Prepared data packet.
        """
        data = bytearray()
        data.append(cmd)
        for arg in args:
            low_byte, high_byte = struct.pack("H", arg)
            data.append(high_byte)
            data.append(low_byte)
        data.insert(0, (len(data) | PROTOCOL_FLAG))
        data.insert(0, HOST_ADDRESS)
        data.append(self.get_checksum(bytearray([DDCCI_ADDR << 1]) + data))
        return data

    def _read_response(self) -> Tuple[bytes, bytes]:
        """
        Reads the response from the I2C bus.
        :return: Header and payload of the response.
        :raises VCPIOError: Failed to read response.
        """
        header = self.read_bytes(GET_VCP_HEADER_LENGTH)
        source, length = secure_unpack("=BB", header)

        length &= ~PROTOCOL_FLAG
        payload = self.read_bytes(length + 1)
        return header, payload

    def _validate_response(self, header: bytes, payload: bytes, expected_reply_code: int, expected_opcode: Optional[int] = None):
        """
        Validates the response from the I2C bus.
        :param header: Header of the response.
        :param payload: Payload of the response.
        :param expected_reply_code: Expected reply code.
        :param expected_opcode: Expected opcode (if any).
        :raises VCPIOError: Validation failed.
        """
        payload, checksum = secure_unpack(f"={len(payload) - 1}sB", payload)

        calculated_checksum = self.get_checksum(header + payload)
        checksum_xor = checksum ^ calculated_checksum
        if checksum_xor:
            if self.checksum_errors == "strict":
                raise VCPIOError(f"Checksum does not match: {checksum_xor}")

        reply_code, result_code, vcp_opcode, vcp_type_code = secure_unpack(">BBBB", payload[:4])

        if reply_code != expected_reply_code:
            raise VCPIOError(f"Received unexpected response code: {reply_code}")

        if expected_opcode is not None and vcp_opcode != expected_opcode:
            raise VCPIOError(f"Received unexpected opcode: {vcp_opcode}")

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
                print(vcp.read_null_message())
        except (OSError, VCPIOError):
            pass
        except VCPPermissionError:
            logger.warning(f"Permission error for {vcp.fp}. Refer to README.md.")
        else:
            logger.debug(f"Found DDC-CI device at {vcp.fp}")
            vcps.append(vcp)
    return vcps