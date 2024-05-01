from typing import List, Optional
import time
import usb

from monitors.monitor_base import MonitorBase


class M27Q(MonitorBase):

    def __init__(self, device: usb.core.Device):
        super().__init__(device)

    @staticmethod
    def vid():
        return 0x2109

    @staticmethod
    def pid():
        return 0x8883

    @staticmethod
    def name():
        return "M27Q"

    @staticmethod
    def min_num_sensor_readings():
        return 10

    def usb_write(self, b_request: int, w_value: int, w_index: int, message: bytes):
        bm_request_type = 0x40
        if self.device.ctrl_transfer(bm_request_type, b_request, w_value, w_index, message) != len(message):
            raise IOError("Transferred message length mismatch")
        self.last_interaction_ns = time.time_ns()

    def usb_read(self, b_request: int, w_value: int, w_index: int, msg_length: int):
        bm_request_type = 0xC0
        data = self.device.ctrl_transfer(bm_request_type, b_request, w_value, w_index, msg_length)
        self.last_interaction_ns = time.time_ns()
        return data

    def convert_sensor_readings(self, readings) -> Optional[int]:
        print(readings)
        cv_th = 3
        diff_th = 3

        def measurement_to_brightness(m):
            return self.clamp_brightness(int(m * 1.8))

        def mean(data) -> float:
            return sum(data) / len(data)

        def std_dev(data, _mean):
            squared_diff_sum = sum((x - _mean) ** 2 for x in data)
            variance = squared_diff_sum / len(data)
            return variance ** 0.5

        # https://en.wikipedia.org/wiki/Coefficient_of_variation
        def cv(data):
            _mean = mean(data)
            if _mean == 0:
                return cv_th
            _std_dev = std_dev(data, _mean)
            _cv = (_std_dev / _mean) * 100
            return _cv

        brightnesses = list(map(measurement_to_brightness, readings))
        potential_brightness = int(mean(brightnesses))
        if cv(brightnesses) <= cv_th:  # prevents the monitor from changing its brightness in steps
            current_brightness = self.get_brightness(force=True)
            if abs(current_brightness - potential_brightness) >= diff_th:  # prevents small changes
                return potential_brightness

        return None

    def get_osd(self, data: List[int] | bytearray):
        self.usb_write(
            b_request=178,
            w_value=0,
            w_index=0,
            message=bytearray([0x6E, 0x51, 0x81 + len(data), 0x01]) + bytearray(data)
        )
        data = self.usb_read(b_request=162, w_value=0, w_index=111, msg_length=12)
        return data[10]

    def set_osd(self, data: List[int] | bytearray):
        self.usb_write(
            b_request=178,
            w_value=0,
            w_index=0,
            message=bytearray([0x6E, 0x51, 0x81 + len(data), 0x03]) + bytearray(data)
        )

    def set_brightness(self, brightness: int, blocking=False, force: bool = False):
        if not blocking and not self.is_ready():
            return
        with self.lock:
            brightness = self.clamp_brightness(brightness)
            if blocking:
                while not self.is_ready():
                    continue
                self.set_osd([0x10, 0x00, brightness])
            else:
                self.set_osd([0x10, 0x00, brightness])
                # else don't set and ignore

    def get_brightness(self, blocking=False, force: bool = False):

        def wait():
            while not self.is_ready():
                continue

        with self.lock:
            if force:
                num_responses = 3
                responses = []
                for _ in range(num_responses):
                    wait()
                    responses.append(self.get_osd([0x10]))
                resp = min(responses)  # For this monitor seems to be correct
            elif blocking:
                wait()
                resp = self.get_osd([0x10])
            else:
                if self.is_ready():
                    resp = self.get_osd([0x10])
                else:
                    return None
            return self.clamp_brightness(resp)