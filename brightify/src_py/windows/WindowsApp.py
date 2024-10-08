from brightify.src_py.windows.helpers import get_theme
from brightify import app_name, OSEvent
import ctypes
import win32con, win32api, win32gui, winerror, pywintypes
from brightify.src_py.windows import logger


class WindowsApp:

    # For documentation of objects, see http://timgolden.me.uk/pywin32-docs/objects.html
    # For documentation of functions, see http://timgolden.me.uk/pywin32-docs/win32gui.html
    def __init__(self, os_event: OSEvent):
        # Listen for taskbar restarts
        WM_TASKBAR_CREATED = win32gui.RegisterWindowMessage("TaskbarCreated")

        # to receive messages from the os
        self.WM_ICON = win32con.WM_USER + 42

        self.message_map = {
            # if taskbar is (re)started we must recreate the icon for this program
            WM_TASKBAR_CREATED: self._on_restart,
            # if the display changes, we must update the top left corner of the app
            win32con.WM_DISPLAYCHANGE: self._on_restart,
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
            1025: self.close
        }
        self.os_event = os_event
        self.primary_click = win32con.VK_LBUTTON

        self._on_restart()

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
        self.os_event.exit_requested = True
        return 0

    def _on_restart(self, hwnd=None, msg=None, wparam=None, lparam=None):
        logger.debug("Restart requested by OS")
        theme = get_theme()
        self.os_event.theme = theme
        self.os_event.force_redraw = True
        _, top, right, _ = win32gui.GetWindowRect(win32gui.FindWindow("Shell_TrayWnd", None))
        self.os_event.bottom_right = (right, top)
        self._create_icon(theme.icon_path)
        buttons_swapped = ctypes.windll.user32.GetSystemMetrics(win32con.SM_SWAPBUTTON) != 0
        self.primary_click = win32con.VK_RBUTTON if buttons_swapped else win32con.VK_LBUTTON
        return 0

    def _on_command(self, hwnd=None, msg=None, wparam=None, lparam=None):
        cmd = win32api.LOWORD(wparam)
        try:
            if cmd in self.cmd_id_map:
                # invoke corresponding function
                self.cmd_id_map[cmd]()
        finally:
            return 0

    def _on_icon_notify(self, hwnd=None, msg=None, wparam=None, lparam=None):
        if lparam == win32con.WM_LBUTTONUP:
            self.os_event.click_on_icon = True
            if self.os_event.last_click is not None:
                self.os_event.last_click = win32gui.GetCursorPos()
        elif lparam == win32con.WM_RBUTTONUP:
            x, y = win32gui.GetCursorPos()
            menu = win32gui.CreatePopupMenu()
            win32gui.AppendMenu(menu, win32con.MF_STRING, self.cmd_id_map["Exit"], "Exit")
            try:
                win32gui.SetForegroundWindow(self.hwnd)
            except pywintypes.error as e:
                logger.debug(f"Failed to set foreground window: {e}")
            # Use the determined flags in TrackPopupMenu
            win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN | win32con.TPM_RIGHTBUTTON, x, y, 0, self.hwnd, None)
            win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)
        return 0

    def _create_icon(self, icon_path):
        hinst = win32api.GetModuleHandle(None)
        if icon_path is not None and icon_path.exists():
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
            logger.debug("Failed to add the icon to the system tray, it may already be there")

    def close(self):
        """Idempotent function to destroy the window."""
        try:  # invoke the exit function
            if hasattr(self, "hwnd"):
                win32gui.DestroyWindow(self.hwnd)
                logger.debug("Exiting windows app")
                del self.hwnd
        except pywintypes.error as e:
            if e.winerror != 1400:  # ERROR_INVALID_WINDOW_HANDLE - already destroyed
                raise e
