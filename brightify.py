import pprint
import sys
import threading
from contextlib import ExitStack
import logging
import logging.config
import tomllib as toml

from PyQt6.QtWidgets import QApplication

from base.BaseApp import BaseApp
from base.Config import Config

# use global logger
logger = logging.getLogger(Config.app_name)


def main_win(config: Config):
    from windows.WindowsApp import WindowsApp
    from windows.helpers import get_mode

    with ExitStack() as exit_stack:
        base_app = BaseApp(config, exit_stack, get_mode)
        WindowsApp(base_app, config, exit_stack)
        import win32gui
        threading.Thread(target=win32gui.PumpMessages, daemon=True).start()
        base_app.show()
        app.exec()


def main_linux(config: Config):
    raise NotImplementedError("Linux not supported yet")


def main_darwin(config: Config):
    raise NotImplementedError("MacOS not supported yet")


def configure_logging():
    with open(Config.root_dir / "res" / "configs" / "log_config.toml", "rb") as f:
        config = toml.load(f)
        pprint.pprint(config)
        logging.config.dictConfig(config)
    logger.debug("Logging configured")


if __name__ == '__main__':
    _config: Config = Config()
    configure_logging()
    exit()
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
