import platform
import subprocess
import tkinter as tk
from contextlib import ExitStack
from base_app import Content
from config import Config
from misc import Point
from ui_misc import show, hide

if not any(platform.win32_ver()):
    raise RuntimeError("This code is designed to run on Windows only")
try:
    import win32con, win32api, win32gui, win32ui, winerror
except ModuleNotFoundError:
    raise RuntimeError("This code is designed to run with pywin32")
except ImportError as e:
    raise RuntimeError("Failed importing pywin32: \n" + e.msg)


class WindowsApp:
    # For documentation of objects, see http://timgolden.me.uk/pywin32-docs/objects.html
    # For documentation of functions, see http://timgolden.me.uk/pywin32-docs/win32gui.html
    def __init__(self, root: tk.Tk, config: Config, exit_stack: ExitStack):
        msg_tb_restart = win32gui.RegisterWindowMessage("TaskbarCreated")
        # TODO listen for USB connected
        # to receive messages from the os
        self.icon_id = win32con.WM_USER + 42
        self.config = config
        # set up the content
        self.exit_stack = exit_stack
        self.root = root
        self.content = None

        self.message_map = {
            # if taskbar is (re)started we must recreate the icon for this program
            msg_tb_restart: self._on_restart,
            # on destroy message
            win32con.WM_DESTROY: self._on_destroy,
            # parses the commands that are registers throughout this program
            win32con.WM_COMMAND: self._on_command,
            # if the icon is interacted with
            self.icon_id: self._on_icon_notify
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
            self.config.program_name,  # windowTitle
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

        self._on_restart()

    def _window_class(self):
        # Configuration for the window
        wc = win32gui.WNDCLASS()
        wc.lpszClassName = self.config.program_name
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
        self.content.exit()
        return 0

    def _init_content(self):
        _, top, right, _ = win32gui.GetWindowRect(win32gui.FindWindow("Shell_TrayWnd", None))
        bottom_right = Point(right, top)

        content = Content(self.root, self.config, self.exit_stack) if self.content is None else self.content

        content.redraw(bottom_right)
        return content

    def _on_restart(self, hwnd=None, msg=None, wparam=None, lparam=None):
        self._create_icon()
        self.content = self._init_content()  # the new or updated content
        return 0

    def _on_command(self, hwnd=None, msg=None, wparam=None, lparam=None):
        cmd = win32api.LOWORD(wparam)
        if cmd in self.cmd_id_map:
            # invoke corresponding function
            self.cmd_id_map[cmd]()
        return 0

    def _on_icon_notify(self, hwnd=None, msg=None, wparam=None, lparam=None):
        x, y = win32gui.GetCursorPos()
        if lparam == win32con.WM_LBUTTONUP and self.content is not None:
            self.content.icon_clicked = True
            if self.root.state() != "normal":
                show(self.root)
            else:
                hide(self.root)
        elif lparam == win32con.WM_RBUTTONUP:
            menu = win32gui.CreatePopupMenu()
            win32gui.AppendMenu(menu, win32con.MF_STRING, self.cmd_id_map["Exit"], "Exit")
            win32gui.SetForegroundWindow(self.hwnd)
            win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN, x, y, 0, self.hwnd, None)
            win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)

        return 0

    def _create_icon(self):
        hinst = win32api.GetModuleHandle(None)
        if self.config.icon_path.exists():
            # specify that icon is loaded from a file and should be the default size
            icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            # load the image and get handle
            hicon = win32gui.LoadImage(hinst, str(self.config.icon_path), win32con.IMAGE_ICON, 0, 0, icon_flags)
        else:
            # get default icon
            hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
        nid = (self.hwnd, 0, flags, self.icon_id, hicon, self.config.program_name)

        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
        except win32gui.error:
            pass

    def exit(self):
        exit_id = self.cmd_id_map["Exit"]
        # invoke default exit behavior
        self.cmd_id_map[exit_id]()
