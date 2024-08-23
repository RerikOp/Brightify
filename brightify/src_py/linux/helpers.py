import logging
import os
from typing import Literal

from brightify import host_os
from brightify.src_py.ui_config import Theme

# Use OS specific logger
logger = logging.getLogger("Linux")

if host_os != "Linux":
    raise RuntimeError("This code is designed to run on Linux only")


def get_mode() -> Literal["light", "dark"]:
    logger.debug("Requested Theme from OS")
    # on Linux, there is no fixed way to determine the theme, this can only be the best effort
    session_manager = os.environ.get("XDG_SESSION_DESKTOP")
    if session_manager is None:
        logger.warning("Could not determine the session manager. Assuming dark theme.")
        return "dark"
    if session_manager.lower() == "gnome":
        # check the gsettings
        try:
            from gi.repository import Gio
            settings = Gio.Settings.new("org.gnome.desktop.interface")
            is_dark = settings.get_boolean("gtk-theme-name").endswith("-dark")
            return "dark" if is_dark else "light"
        except ImportError as e:
            logger.error(f"Failed to import gi.repository: {e}")
        except Exception as e:
            logger.error(f"Failed to get theme from GSettings: {e}")
    elif session_manager.lower() == "kde":
        # check the kde config
        try:
            with open(os.path.expanduser("~/.config/kdeglobals"), "r") as f:
                for line in f:
                    if line.startswith("[KDE]"):
                        break
                for line in f:
                    if line.startswith("ColorScheme="):
                        return "dark" if line.endswith("-dark") else "light"
        except FileNotFoundError as e:
            logger.error(f"Failed to find KDE config file: {e}")
        except Exception as e:
            logger.error(f"Failed to get theme from KDE config: {e}")
    elif session_manager.lower() == "xfce":
        # check the xfce config
        try:
            with open(os.path.expanduser("~/.config/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml"), "r") as f:
                for line in f:
                    if "<property name=\"Net/ThemeName\" type=\"string\" value=\"" in line:
                        return "dark" if line.endswith("-dark") else "light"
        except FileNotFoundError as e:
            logger.error(f"Failed to find XFCE config file: {e}")
        except Exception as e:
            logger.error(f"Failed to get theme from XFCE config: {e}")
    return "dark"


def get_theme(no_animations) -> Theme:
    logger.info("Using Theme from Linux, callback not yet implemented")
    return Theme(has_animations=not no_animations)
