import dataclasses
from pathlib import Path
from typing import Optional

import serial


@dataclasses.dataclass
class Config:
    program_name: str = "Brightify"
    current_dir: Path = Path(__file__).parent
    monitors_dir: Path = current_dir.joinpath("monitors")
    icon_path: Path = current_dir.joinpath("icon.ico")
    icon_inv_path: Path = current_dir.joinpath("icon_inv.ico")
    # Serial config:
    sensor_serial_port = "COM3"
    baud_rate = 9600
    timeout = 1

    @staticmethod
    def get_measurement(ser: serial.Serial) -> Optional[int]:
        """
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
