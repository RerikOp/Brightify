import atexit
import dataclasses
import logging
import time
from typing import Optional, List
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

import serial

from brightify import root_dir

logger = logging.getLogger("SensorComm")


@dataclasses.dataclass
class SensorComm(QObject):
    sensor_serial_port: str = "COM3"
    baud_rate: int = 9600
    read_timeout_ms: int = 1000
    write_timeout_ms: int = 1000
    num_measurements: int = 10
    measurements: List[int] = dataclasses.field(default_factory=list, init=False)
    ser: Optional[serial.Serial] = dataclasses.field(default=None, init=False)
    update_signal: pyqtSignal = dataclasses.field(default=pyqtSignal(), init=False)
    is_reading: bool = dataclasses.field(default=False, init=False)

    def __post_init__(self):
        super().__init__()
        # self.flash_firmware()
        self.update_signal.connect(self.update)
        atexit.register(self.__del__)

    def get_measurement(self) -> Optional[int]:
        """
        Get the next reading from the sensor.
        :return: the next reading from the sensor or None if sensor isn't ready.
         Make sure to set timeout appropriately so this method doesn't stall too long if device isn't ready
        """
        # check if serial is ready to read
        data = self.ser.readline().strip().decode("utf-8")
        if data != "":  # the readline will return an empty string if device is sleeping.
            try:
                return int(data)
            except ValueError:
                return None
        return None

    def __update(self):
        if not self.has_serial():
            self.ser = serial.Serial(self.sensor_serial_port, self.baud_rate,
                                     timeout=self.read_timeout_ms / 1000,
                                     write_timeout=self.write_timeout_ms / 1000)
            if self.ser.is_open:
                logger.info(f"Connected to sensor on {self.sensor_serial_port}")
            else:
                return

        # Get the next reading from the sensor
        if (reading := self.get_measurement()) is not None:
            self.measurements.append(reading)
            # trim the list of measurements to the last num_measurements
        self.measurements = self.measurements[-self.num_measurements:]

    @pyqtSlot()
    def update(self):
        self.is_reading = True
        try:
            self.__update()
        # it appears that SerialException or PermissionError is raised when the device is not connected
        except (serial.SerialException, PermissionError) as _:
            self.measurements.clear()
        except Exception as e:
            logger.error(f"Error while updating sensor: {e}", exc_info=e)
            self.measurements.clear()
        finally:
            self.is_reading = False

    def has_serial(self) -> bool:
        if self.ser is not None and self.ser.is_open:
            try:
                self.ser.in_waiting  # attempt to read from the serial port
                return True
            except serial.SerialException:
                return False
        return False

    def flash_firmware(self):
        import subprocess
        logger.info("Flashing firmware")
        pio_command = ["pio", "run", "-t", "upload"]
        path = root_dir / "sensor_firmware"
        # run the PlatformIO command in the sensor_firmware directory and wait for it to finish. Don't print the output
        ret = subprocess.run(pio_command, cwd=path, check=True, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        if ret.returncode == 0:
            logger.info("Firmware flashed successfully")
        else:
            logger.error("Failed to flash firmware, check if the sensor is connected and the firmware")

    def __del__(self):
        if self.has_serial():
            while self.is_reading:
                time.sleep(0.1)
            try:
                self.ser.close()
                logger.info("Closed serial connection")
            except Exception as e:
                logger.error(f"Error while closing serial connection: {e}")
