import atexit
import dataclasses
import logging
import time
from dataclasses import field
from typing import Optional, List
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

import serial

from brightify import brightify_dir

logger = logging.getLogger("SensorComm")


def flash_firmware():
    """
    Flash the firmware to the sensor. This will run the PlatformIO command to flash the firmware to the sensor.
    :return: None
    """
    import subprocess
    logger.info("Flashing firmware")
    pio_command = ["pio", "run", "-t", "upload"]
    path = brightify_dir / "sensor_firmware"
    try:
        ret = subprocess.run(pio_command, cwd=path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if ret.returncode == 0:
            logger.info("Firmware flashed successfully")
        else:
            logger.error("Failed to flash firmware, check if the sensor is connected and the firmware")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error flashing firmware: {e}")


@dataclasses.dataclass
class SensorComm(QObject):
    sensor_serial_port: str = "COM3"  # FIXME: Make this a setting depending on the OS
    baud_rate: int = 9600
    read_timeout_ms: int = 1000
    write_timeout_ms: int = 1000
    num_measurements: int = 10
    measurements: List[int] = field(default_factory=list, init=False)
    ser: Optional[serial.Serial] = field(default=None, init=False)
    update_signal: pyqtSignal = dataclasses.field(default=pyqtSignal(), init=False)
    is_reading: bool = field(default=False, init=False)

    def __post_init__(self):
        super().__init__()
        self.update_signal.connect(self.update)
        atexit.register(self.__del__)

    def get_measurement(self) -> Optional[int]:
        """
        Get the next reading from the sensor.
        :return: the next reading from the sensor or None if sensor isn't ready.
        """
        try:
            data = self.ser.readline().strip().decode("utf-8")
            if data:
                return int(data)
        except (serial.SerialException, ValueError) as e:
            logger.error(f"Error reading measurement: {e}")
        return None

    def __cleanup(self):
        self.measurements.clear()
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                logger.info("Closed serial connection")
            except serial.SerialException as e:
                logger.error(f"Error closing serial connection: {e}")
        self.ser = None

    def reinit(self) -> bool:
        """
        Initialize the serial connection to the sensor.
        :return: True if the connection was successful, False otherwise
        """
        self.is_reading = True
        self.__cleanup()
        try:
            self.ser = serial.Serial(self.sensor_serial_port, self.baud_rate,
                                     timeout=self.read_timeout_ms / 1000,
                                     write_timeout=self.write_timeout_ms / 1000)
            logger.info(f"Connected to sensor on {self.sensor_serial_port}")
            return True
        except (serial.SerialException, PermissionError) as _:
            pass
        finally:
            self.is_reading = False
        return False

    @pyqtSlot()
    def update(self) -> None:
        if not self.has_serial():
            self.__cleanup()
            return

        self.is_reading = True
        try:
            if (reading := self.get_measurement()) is not None:
                self.measurements.append(reading)
                self.measurements = self.measurements[-self.num_measurements:]
        finally:
            self.is_reading = False

    def has_serial(self) -> bool:
        if self.ser and self.ser.is_open:
            try:
                _ = self.ser.in_waiting
                return True
            except serial.SerialException:
                pass
        return False

    def __del__(self):
        if self.has_serial():
            while self.is_reading:
                time.sleep(0.1)
            self.__cleanup()
