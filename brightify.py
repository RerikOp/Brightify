import threading
import tkinter as tk
from contextlib import ExitStack
import platform

import base.base_app
from config import Config


def main_win32(config: Config, root: tk.Tk):
    from windows.taskbar_icon import WindowsApp
    root.wm_attributes('-toolwindow', 'True')
    root.overrideredirect(True)
    with ExitStack() as exit_stack:
        WindowsApp(root, config, exit_stack)
        import win32gui
        threading.Thread(target=win32gui.PumpMessages, daemon=True).start()
        root.mainloop()


def main_any(config: Config, root: tk.Tk):
    with ExitStack() as exit_stack:
        c = base.base_app.Content(root, config, exit_stack)
        c.redraw()
        root.mainloop()


if __name__ == '__main__':
    try:
        root = tk.Tk()
        root.resizable(False, False)
        run_windows = any(platform.win32_ver())
        if run_windows:
            main_win32(Config(), root)
        else:
            main_any(Config(), root)
    except KeyboardInterrupt:
        exit()
