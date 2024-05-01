import dataclasses
import threading
from tkinter import ttk
import tkinter as tk
import time
import serial
from typing import Optional, List, Tuple
from contextlib import ExitStack
from config import Config
from base.misc import Point, get_supported_monitors
from monitors.monitor_base import MonitorBase
from base.ui_misc import hide, CheckBox, show


@dataclasses.dataclass
class Row:
    name_label: ttk.Label
    scale: ttk.Scale
    brightness_label: ttk.Label
    is_managed_tick: CheckBox
    monitor: MonitorBase


class Content(tk.Frame):
    def __init__(self, root: tk.Tk, config: Config, exit_stack: ExitStack):
        super().__init__(master=root)
        self.bg_color = "black"
        self.text_color = "white"
        self.heading_color = "grey"
        self.accent_color = "#007AD9"
        self.pad: int = 15
        self.config: Config = config
        self.exit_stack: ExitStack = exit_stack
        self.monitors: List[MonitorBase] = []

        # configure this frame
        self.root = root
        self.style = ttkthemes.ThemedStyle()
        self.configure(bg=self.bg_color)
        self.root.title(config.program_name)
        self.root.iconbitmap(str(config.icon_inv_path))
        self.root.bind("<FocusOut>", self.__on_outside_click)
        self.icon_clicked = False

        # styles
        self.default_font = ('Helvetica', 15)

        self.scale_style = "Scale.Horizontal.TScale"
        ttk.Style().configure(self.scale_style, background=self.bg_color)

        self.label_heading_style = "HeadingLabel.TLabel"
        ttk.Style().configure(self.label_heading_style, font=self.default_font,
                              foreground=self.heading_color, background=self.bg_color)

        self.label_default_style = "DefaultLabel.TLabel"
        ttk.Style().configure(self.label_default_style, font=self.default_font, foreground=self.text_color,
                              background=self.bg_color)

        self.rows: List[Row] = []

        # sensor stuff:
        self.sensor: Optional[serial.Serial] = None
        self.had_working_sensor = False
        self.sensor_lock = threading.Lock()
        self.sensor_thread_killed = False
        self.sensor_thread = threading.Thread(target=self.__poll_outside_brightness, daemon=True)
        self.sensor_thread.start()

    def __on_outside_click(self, event: tk.Event):
        if not self.root.overrideredirect(None):  # if root has buttons, outside click doesn't do anything
            return

        def hide_window():
            if not self.icon_clicked:
                hide(self.root)
            if self.icon_clicked and self.root.state() == "normal":
                hide(self.root)
            # else it is currently hidden and a click on the icon should make it visible again
            self.icon_clicked = False

        self.root.after(100, hide_window)

    def __poll_outside_brightness(self):
        measurements = []

        def append_next():
            if self.sensor is None or len(self.rows) == 0:
                return
            try:
                with self.sensor_lock:
                    measurement = self.config.get_measurement(self.sensor)
                if measurement is not None:
                    measurements.append(measurement)
                    max_row = max(self.rows, key=lambda r: r.monitor.min_num_sensor_readings())
                    max_num_readings = max_row.monitor.min_num_sensor_readings()
                    measurements[:] = measurements[-max_num_readings:]  # throw away old values
            except serial.SerialException:  # if unplugged
                self.sensor = None

        # main thread
        while not self.sensor_thread_killed:
            sensor_state_changed, sensor_is_working = self.__check_sensor()  # try to reconnect
            if sensor_state_changed:
                self.__on_sensor_changed(sensor_is_working)
            append_next()
            for row in self.rows:
                monitor_is_managed = row.is_managed_tick.is_checked and len(
                    measurements) >= row.monitor.min_num_sensor_readings()
                if monitor_is_managed and (brightness := row.monitor.convert_sensor_readings(measurements)) is not None:
                    row.scale.config(value=brightness)
                    row.brightness_label.config(text=brightness)
                    row.monitor.set_brightness(brightness, blocking=True)
            time.sleep(1)

        if self.sensor is not None:
            # clean up the resources
            self.sensor.close()

    def __on_sensor_changed(self, sensor_is_working: bool):
        for row in self.rows:
            row.is_managed_tick.disabled = not sensor_is_working
            if not sensor_is_working:  # switch to manual mode
                row.scale.config(state="normal")
            else:  # switch to managed mode
                old_state = "disabled" if row.is_managed_tick.is_checked else "normal"
                row.scale.config(state=old_state)

    def __link_row(self, row: Row):
        def scale_changed(new: str):
            brightness = round(float(new))
            row.brightness_label.config(text=brightness)
            row.monitor.set_brightness(brightness, blocking=False)

        def tick_changed(is_checked: bool):
            brightness = row.monitor.get_brightness(force=True)
            row.scale.set(brightness)
            row.scale.update()
            if is_checked:
                row.scale.config(state="disabled")
            else:
                row.scale.config(state="normal")

        _, is_enabled = self.__check_sensor()
        if row.is_managed_tick is not None:
            row.is_managed_tick.configure(command=lambda is_checked: tick_changed(is_checked))
            row.is_managed_tick.disabled = not is_enabled

        row.scale.configure(command=lambda new: scale_changed(new))

    def __check_sensor(self) -> Tuple[bool, bool]:
        import serial

        def init_new_sensor():
            try:
                self.sensor = serial.Serial(self.config.sensor_serial_port,
                                            self.config.baud_rate, timeout=self.config.timeout)
                time.sleep(1)
                return self.sensor.readable()
            except serial.SerialException:
                self.sensor = None
                return False

        is_enabled = self.sensor is not None and self.sensor.readable()
        state_changed = is_enabled != self.had_working_sensor
        if is_enabled:
            self.had_working_sensor = is_enabled
            return state_changed, is_enabled  # sensor didn't change and is working
        if self.sensor is None:  # if there is no sensor
            is_enabled = init_new_sensor()
        else:  # sensor not readable
            with self.sensor_lock:
                self.sensor.close()  # try reconnecting
            is_enabled = init_new_sensor()

        state_changed = is_enabled != self.had_working_sensor
        self.had_working_sensor = is_enabled
        return state_changed, is_enabled

    def __redraw(self, bottom_right: Optional[Point] = None):
        self.root.attributes("-alpha", 0)  # invisible
        self.pack()
        self.update()  # content size is now known
        if bottom_right is not None:
            x = bottom_right.x - self.winfo_width()
            y = bottom_right.y - self.winfo_height()
            self.root.geometry(f"+{x}+{y}")
        self.root.update()
        self.root.attributes("-alpha", 1)  # visible

    def __load_connected_monitors(self):
        self.exit_stack.pop_all()  # TODO what if the OS app put elements in here?
        self.monitors.clear()

        for m in get_supported_monitors(self.config.monitors_dir):
            self.monitors.append(m)
            self.exit_stack.push(m)

    def __remove_all_widgets(self):
        for widget in self.winfo_children():
            widget.destroy()
        self.__redraw()

    def redraw(self, bottom_right: Optional[Point] = None):
        self.__load_connected_monitors()
        if len(self.monitors) == 0:
            self.__remove_all_widgets()
            print("No monitor found")
            return

        rows = []

        # description in top most row
        name_desc_label = ttk.Label(text="DESC", justify="center", style=self.label_heading_style)
        name_desc_label.grid(in_=self, row=0, column=0)
        auto_desc_label = ttk.Label(text="AUTO", justify="center", style=self.label_heading_style)
        auto_desc_label.grid(in_=self, row=0, column=1)
        brightness_desc_label = ttk.Label(text="BRIGHTNESS", justify="left", style=self.label_heading_style)
        brightness_desc_label.grid(in_=self, row=0, column=2)

        for row, m in enumerate(self.monitors, start=1):
            brightness = m.get_brightness(force=True)
            brightness_label = ttk.Label(width=3, text=brightness, style=self.label_default_style)
            scale = ttk.Scale(from_=m.min_brightness, to=m.max_brightness, style=self.scale_style,
                              orient="horizontal", length=300, value=brightness)
            m_name = ttk.Label(text=m.name(), justify="center", style=self.label_default_style)
            is_managed_tick = CheckBox(None, checked_color=self.accent_color,
                                       unchecked_color=self.bg_color,
                                       disabled_color=self.heading_color)

            m_name.grid(in_=self, row=row, column=0, sticky=tk.W, padx=self.pad)
            scale.grid(in_=self, row=row, column=2, sticky=tk.W, padx=self.pad)
            brightness_label.grid(in_=self, row=row, column=3, padx=self.pad)
            is_managed_tick.grid(in_=self, row=row, column=1, padx=self.pad)

            rows.append(Row(m_name, scale, brightness_label, is_managed_tick, m))

        for row in rows:
            self.__link_row(row)

        self.grid_rowconfigure(0, pad=self.pad)
        self.grid_rowconfigure(len(self.monitors), pad=self.pad)
        self.rows = rows

        self.__redraw(bottom_right)

    def exit(self):
        self.sensor_thread_killed = True
        self.sensor_thread.join()
        self.root.destroy()  # Tkinter
