# Brightify
This app allows you to set the brightness of your monitor(s). It is essentially a wrapper around the [DDC/CI](https://en.wikipedia.org/wiki/Display_Data_Channel#DDC/CI) protocol, which is supported by most monitors.
It also supports adding custom communication protocols to control the brightness of USB monitors. For this, you most likely need to reverse engineer the communication protocol of the monitor. In my experience, this provides a more stable experience than using the DDC/CI protocol.
You can find an example implementation for the [Gigabyte M27Q](https://www.gigabyte.com/Monitor/M27Q) in [here](brightify/monitors/m27q.py).
The app is designed to be run in the background and can be controlled via a taskbar icon. It also supports a brightness sensor that can automatically adjust the brightness based on the ambient light.

## Getting started
1. Install brightify by running `pip install Brightify`. This package is regularly uploaded to PyPi. If you want to install the latest version, you can clone this repository from 
[GitHub](https://github.com/RerikOp/Brightify) and install it with `pip install -e .` in the root directory.
2. To start the app: `python -m brightify run`. You can exit either by right-clicking the icon in the taskbar and
   selecting "Exit" or by pressing `Ctrl+C` in the terminal.
3. To start the app at startup (or logon) and add a menu icon, run `python -m add all`. To remove the both, run
   `python -m remove all`.

## Optional arguments
There are several other arguments you can pass to the app, see `python -m brightify --help` for more information.
- To target add/remove only the startup run `python -m brightify add/remove startup`.
   - To add a task to the task scheduler on Windows, pass `--use-scheduler`. It will request elevated permissions.
   - By default, the terminal will be hidden, but you can change this by passing the `--force-console` argument.
- To add/remove only the menu icon run `python -m brightify add/remove menu-icon`.
   - You can again force the console to be shown by passing the `--force-console` argument.

## Set up the brightness sensor
- Modify the [SensorComm](brightify/SensorComm.py) class to match your device and firmware
- Modify the code that is polling from the brightness sensor [Device Firmware](brightify/sensor_firmware/src)
- Modify [platformio.ini](brightify/sensor_firmware/platformio.ini) and enter your board (
   see [supported boards](https://docs.platformio.org/en/latest/boards/index.html))
- Run `pio run -t upload` in the terminal to upload the firmware to the board.
   If everything is working, the *Auto* Checkbox for each supported Monitor should now be clickable

## Remarks
- Currently, only the Windows task bar icon is supported, the main part of this app is OS independent.
- Feel free to create a pull request and add your own USB Monitor


