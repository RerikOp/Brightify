from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication

from brightify import host_os, app_name
from brightify.BaseApp import BaseApp
import logging
import atexit

if host_os != "Windows":
    raise RuntimeError("This code is designed to run on Windows only")
try:
    import win32con, win32api, win32gui, win32ui, winerror, pywintypes
except ModuleNotFoundError:
    raise RuntimeError("This code is designed to run with pywin32")
except ImportError as e:
    raise RuntimeError("Failed importing pywin32: \n" + e.msg)

# Use OS specific logger
logger = logging.getLogger("Windows")


class WindowsApp:
    # For documentation of objects, see http://timgolden.me.uk/pywin32-docs/objects.html
    # For documentation of functions, see http://timgolden.me.uk/pywin32-docs/win32gui.html
    def __init__(self, base_app: BaseApp):
        WM_TASKBAR_CREATED = win32gui.RegisterWindowMessage("TaskbarCreated")
        # TODO listen for USB connected
        # to receive messages from the os
        self.WM_ICON = win32con.WM_USER + 42
        self.base_app = base_app

        self.message_map = {
            # if taskbar is (re)started we must recreate the icon for this program
            WM_TASKBAR_CREATED: self._on_restart,
            # on destroy message
            win32con.WM_DESTROY: self._on_destroy,
            # parses the commands that are registers throughout this program
            win32con.WM_COMMAND: self._on_command,
            # if the icon is interacted with
            self.WM_ICON: self._on_icon_notify
        }

        # Register a window class and use its instance (hinst)
        wc = self._window_class()
        try:
            win32gui.RegisterClass(wc)
        except win32gui.error as err_info:
            if err_info.winerror != winerror.ERROR_CLASS_ALREADY_EXISTS:  # ERROR_CLASS_ALREADY_EXISTS is okay
                raise RuntimeError(err_info)

        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow(
            wc.lpszClassName,  # className
            app_name,  # windowTitle
            style,  # style
            0,  # x
            0,  # y
            win32con.CW_USEDEFAULT,  # width
            win32con.CW_USEDEFAULT,  # height
            0,  # parent
            0,  # menu
            0,  # hinstance
            None  # reserved
        )

        # maps command strings to ids and ids to functions that should be invoked when called
        self.cmd_id_map = {
            "Exit": 1025,
            1025: lambda: win32gui.DestroyWindow(self.hwnd)
        }

        # initialize the icon
        self._on_restart()

        atexit.register(self.exit)

    def _window_class(self):
        # Configuration for the window
        wc = win32gui.WNDCLASS()
        wc.lpszClassName = app_name
        wc.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW
        wc.hCursor = win32api.LoadCursor(0, win32con.IDC_ARROW)
        wc.hbrBackground = win32con.COLOR_WINDOW
        wc.lpfnWndProc = self.message_map

        return wc

    def _on_destroy(self, hwnd=None, msg=None, wparam=None, lparam=None):
        import win32gui
        nid = (self.hwnd, 0)
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        win32gui.PostQuitMessage(0)  # Terminate the app
        QApplication.exit(0)
        return 0

    def _update_top_left(self):
        _, top, right, _ = win32gui.GetWindowRect(win32gui.FindWindow("Shell_TrayWnd", None))
        ratio = QApplication.primaryScreen().devicePixelRatio()
        x, y = (int((right / ratio - self.base_app.minimumSizeHint().width())),
                int((top / ratio - self.base_app.minimumSizeHint().height())))
        self.base_app.top_left = QPoint(x, y)

    def _on_restart(self, hwnd=None, msg=None, wparam=None, lparam=None):
        logger.debug("Taskbar restarted")
        self._update_top_left()
        self.base_app.redraw()
        self._create_icon()
        self.base_app.change_state("hide")
        return 0

    def _on_command(self, hwnd=None, msg=None, wparam=None, lparam=None):
        cmd = win32api.LOWORD(wparam)
        if cmd in self.cmd_id_map:
            # invoke corresponding function
            self.cmd_id_map[cmd]()
        return 0

    def _on_icon_notify(self, hwnd=None, msg=None, wparam=None, lparam=None):
        x, y = win32gui.GetCursorPos()
        if lparam == win32con.WM_LBUTTONUP:
            self._update_top_left()
            self.base_app.change_state("invert")
        elif lparam == win32con.WM_RBUTTONUP:
            menu = win32gui.CreatePopupMenu()
            win32gui.AppendMenu(menu, win32con.MF_STRING, self.cmd_id_map["Exit"], "Exit")
            win32gui.SetForegroundWindow(self.hwnd)
            win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN, x, y, 0, self.hwnd, None)
            win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)

        return 0

    def _create_icon(self):
        hinst = win32api.GetModuleHandle(None)
        icon_path = self.base_app.ui_config.icon_path
        if icon_path.exists():
            # specify that icon is loaded from a file and should be the default size
            icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            # load the image and get handle
            hicon = win32gui.LoadImage(hinst, str(icon_path), win32con.IMAGE_ICON, 0, 0, icon_flags)
        else:
            # get default icon
            hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
            logger.critical("Failed to load icon")

        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
        nid = (self.hwnd, 0, flags, self.WM_ICON, hicon, app_name)

        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
        except win32gui.error:
            logger.critical("Failed to add the icon to the system tray")
            pass

    def exit(self):
        exit_id = self.cmd_id_map["Exit"]
        try:  # invoke the exit function
            self.cmd_id_map[exit_id]()
        except pywintypes.error as e:
            if e.winerror != 1400:  # ERROR_INVALID_WINDOW_HANDLE
                raise e
