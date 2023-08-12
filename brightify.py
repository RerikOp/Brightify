import threading
import tkinter as tk
from contextlib import ExitStack
import platform

from config import Config


def main_win32(config: Config, root: tk.Tk):
    from windows_app import WindowsApp
    with ExitStack() as exit_stack:
        WindowsApp(root, config, exit_stack)
        import win32gui
        threading.Thread(target=win32gui.PumpMessages, daemon=True).start()
        root.mainloop()


if __name__ == '__main__':
    try:
        root = tk.Tk()
        root.overrideredirect(True)
        root.wm_attributes('-toolwindow', 'True')

        run_windows = any(platform.win32_ver())
        if run_windows:
            main_win32(Config(), root)
    except KeyboardInterrupt:
        exit()
