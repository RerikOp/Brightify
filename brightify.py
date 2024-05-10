import atexit
import sys
import threading
from contextlib import ExitStack
import logging
import logging.config
import tomllib as toml
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from base.BaseApp import BaseApp
from base.Config import Config

# use global logger
logger = logging.getLogger(Config.app_name)


def excepthook(exc_type, exc_value, exc_tb):
    global ret_code
    logger.exception("An unhandled exception occurred", exc_info=(exc_type, exc_value, exc_tb))
    ret_code = 1

def main_win(config: Config):
    global ret_code
    from windows.WindowsApp import WindowsApp
    from windows.helpers import get_theme, get_internal_monitor
    base_app = BaseApp(config, get_theme, get_internal_monitor)
    WindowsApp(base_app, config)
    import win32gui
    threading.Thread(target=win32gui.PumpMessages, daemon=True).start()
    base_app.show()
    ret_code = app.exec()
    logger.info(f"Exiting with code {ret_code}")
    exit(ret_code)


def main_linux(config: Config):
    raise NotImplementedError("Linux not supported yet")


def main_darwin(config: Config):
    raise NotImplementedError("MacOS not supported yet")


def configure_logging():
    # make sure logs dir exists
    log_dir = Path(Config.root_dir) / "logs"
    log_dir.mkdir(exist_ok=True)
    with open(Config.root_dir / "res" / "configs" / "log_config.toml", "rb") as f:
        config = toml.load(f)
        logging.config.dictConfig(config)

    queue_handler = logging.getHandlerByName("queue_handler")
    if queue_handler is not None:
        queue_handler.listener.start()
        atexit.register(queue_handler.listener.stop)

    logger.debug("Logging configured")

def find_ddcci_monitors():
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
                    print(e)


if __name__ == '__main__':
    #find_ddcci_monitors()
    _config: Config = Config()
    configure_logging()
    ret_code = 0
    sys.excepthook = excepthook
    try:
        app = QApplication(sys.argv)
        match _config.host_os:
            case "Windows":
                logger.debug("Running on Windows")
                main_win(_config)
            case "Linux":
                logger.debug("Running on Linux")
                main_linux(_config)
            case "Darwin":
                logger.debug("Running on MacOS")
                main_darwin(_config)
            case _:
                logger.error(f"Unsupported OS: {_config.host_os}")
                exit(1)
    except KeyboardInterrupt:
        logger.info("User interrupted the program, exiting...")
        exit()
