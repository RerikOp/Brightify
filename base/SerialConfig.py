import dataclasses
from typing import Optional

import serial


@dataclasses.dataclass
class SerialConfig:
    sensor_serial_port: str = "COM3"
    baud_rate: int = 9600
    read_timeout_ms: int = 1000
    write_timeout_ms: int = 1000

    @staticmethod
    def get_measurement(ser: serial.Serial) -> Optional[int]:
        """
        Get the next reading from the sensor.

        :param ser: A serial connection.
        :return: the next reading from the sensor or None if sensor isn't ready.
         Make sure to set timeout appropriately so this method doesn't stall too long if device isn't ready
        """
        data = ser.readline().strip().decode()
        if data != "":  # the readline will return an empty string if device is sleeping.
            try:
                return int(data)
            except ValueError:
                return None
        return None
