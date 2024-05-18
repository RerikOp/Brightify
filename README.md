# Getting started

1. Install brightify by running `pip install .` in the main directory. When developing, you can use `pip install -e .`
   to install the package in editable mode.
2. To start the app: `python -m brightify run`. You can exit either by right-clicking the icon in the taskbar and
   selecting "Exit" or by pressing `Ctrl+C` in the terminal.
3. There are several other arguments you can pass to the app, see `python -m brightify --help` for more information.
    1. To start the app at startup `python -m add startup`. By default, the terminal will be hidden, but you can change
       this by passing the `--force-console` argument.
       To remove the startup task, run `python -m remove startup`. On Windows you can also use the Task Scheduler, which
       requires elevated permissions to add the app to startup.
       For this, run `python -m brightify add startup --mode task_scheduler` and to remove it `python -m brightify
       remove startup --mode task_scheduler`.
    2. To add a menu icon `python -m brightify add menu-icon`. Again, you can pass the `--force-console` argument
       force the terminal.
       To remove the icon, run `python -m remove menu-icon`.

# Set up the brightness sensor

1. Modify the [SensorComm](brightify/SensorComm.py) class to match your device and firmware
2. Modify the code that is polling from the brightness sensor [Device Firmware](brightify/sensor_firmware/src)
3. Modify [platformio.ini](brightify/sensor_firmware/platformio.ini) and enter your board (
   see [supported boards](https://docs.platformio.org/en/latest/boards/index.html))
4. Run `pio run -t upload` in the terminal to upload the firmware to the board.
   If everything is working, the *Auto* Checkbox for each supported Monitor should now be clickable

# Remarks

+ Currently, only the Windows task bar icon is supported, the main part of this app is OS independent
+ Feel free to create a pull request and add your own USB Monitor


