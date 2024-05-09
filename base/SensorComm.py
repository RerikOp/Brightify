import dataclasses
import logging
from typing import Optional, List, Dict
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

import serial
import atexit

from base.Config import Config

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

    def __post_init__(self):
        super().__init__()
        atexit.register(self.__del__)
        #self.flash_firmware()
        self.update_signal.connect(self.update)

    def get_measurement(self) -> Optional[int]:
        """
        Get the next reading from the sensor.
        :return: the next reading from the sensor or None if sensor isn't ready.
         Make sure to set timeout appropriately so this method doesn't stall too long if device isn't ready
        """
        if not self.has_serial():
            return None
        data = self.ser.readline().strip().decode("utf-8")
        if data != "":  # the readline will return an empty string if device is sleeping.
            try:
                return int(data)
            except ValueError:
                return None
        return None

    @pyqtSlot()
    def update(self):
        if not self.has_serial():
            logger.info("Trying to connect to sensor")
            self.ser = serial.Serial(self.sensor_serial_port, self.baud_rate,
                                     timeout=self.read_timeout_ms / 1000,
                                     write_timeout=self.write_timeout_ms / 1000)
            if self.ser.is_open:
                logger.info(f"Connected to sensor on {self.sensor_serial_port}")
            else:
                logger.error("Failed to connect to sensor")
                self.measurements.clear()
                return

        # Get the next reading from the sensor
        if (reading := self.get_measurement()) is not None:
            self.measurements.append(reading)
        # trim the list of measurements to the last num_measurements
        self.measurements = self.measurements[-self.num_measurements:]

    def has_serial(self) -> bool:
        return self.ser is not None and self.ser.is_open

    def flash_firmware(self):
        import subprocess
        logger.info("Flashing firmware")
        pio_command = ["pio", "run", "-t", "upload"]
        path = Config.root_dir / "sensor_firmware"
        # run the PlatformIO command in the sensor_firmware directory and wait for it to finish. Don't print the output
        ret = subprocess.run(pio_command, cwd=path, check=True, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        if ret.returncode == 0:
            logger.info("Firmware flashed successfully")
        else:
            logger.error("Failed to flash firmware, check if the sensor is connected and the firmware")

    def __del__(self):
        if self.has_serial():
            try:
                self.ser.close()
                logger.info("Closed serial connection")
            except Exception as e:
                logger.error(f"Error while closing serial connection: {e}")
