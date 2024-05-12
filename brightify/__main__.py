import atexit
import threading
import logging
import logging.config
import tomllib as toml
import sys

from PyQt6.QtWidgets import QApplication

from brightify import app_name, root_dir, host_os
from brightify.BaseApp import BaseApp

# use global logger
logger = logging.getLogger(app_name)


def excepthook(exc_type, exc_value, exc_tb):
    if exc_type is KeyboardInterrupt:
        logger.info("User interrupted the program, exiting...")
        exit(0)
    logger.exception("An unhandled exception occurred", exc_info=(exc_type, exc_value, exc_tb))


def main_win():
    import win32gui
    global ret_code
    from brightify.windows.WindowsApp import WindowsApp
    from brightify.windows.helpers import get_theme #, get_internal_monitor

    base_app = BaseApp(get_theme)
    WindowsApp(base_app)
    threading.Thread(target=win32gui.PumpMessages, daemon=True).start()
    base_app.show()
    ret_code = app.exec()
    logger.info(f"Exiting with code {ret_code}")
    exit(ret_code)


def main_linux():
    raise NotImplementedError("Linux not supported yet")


def main_darwin():
    raise NotImplementedError("MacOS not supported yet")


def configure_logging():
    # make sure logs dir exists
    log_dir = root_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    with open(root_dir / "log_config.toml", "rb") as f:
        config = toml.load(f)
        logging.config.dictConfig(config)
    queue_handler = logging.getHandlerByName("queue_handler")
    if queue_handler is not None:
        queue_handler.listener.start()
        atexit.register(queue_handler.listener.stop)
    logger.debug("Logging configured")


"""def find_ddcci_monitors():
    import monitorcontrol
    monitors = monitorcontrol.get_monitors()
    set_to = 100
    for monitor in monitors:
        with monitor:
            try:
                print(monitor.get_vcp_capabilities())
                while monitor.get_luminance() != set_to:
                    monitor.set_luminance(set_to)
                while (caps := monitor.get_vcp_capabilities()) is None:
                    pass
                print(caps)
            except Exception as e:
                print(e)"""


if __name__ == '__main__':
    configure_logging()
    sys.excepthook = excepthook
    try:
        app = QApplication(sys.argv)
        match host_os:
            case "Windows":
                logger.debug("Running on Windows")
                main_win()
            case "Linux":
                logger.debug("Running on Linux")
                main_linux()
            case "Darwin":
                logger.debug("Running on MacOS")
                main_darwin()
            case _:
                logger.error(f"Unsupported OS: {host_os}")
                exit(1)
    except KeyboardInterrupt:
        logger.info("User interrupted the program, exiting...")
        exit()
