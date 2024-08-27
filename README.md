<div align="center">
<br>
    <img src="brightify/res/icon_light.ico" alt="" width="150" height="auto"/>
    <h1>Brightify</h1>
    <div>
    <a href="https://www.codefactor.io/repository/github/rerikop/brightify"><img src="https://www.codefactor.io/repository/github/rerikop/brightify/badge" alt="CodeFactor" /></a>    
    </div>
<br>
</div>

This app allows you to set the brightness of your monitor(s). It is essentially a wrapper around
the [DDC/CI](https://en.wikipedia.org/wiki/Display_Data_Channel#DDC/CI) protocol, which is supported by most modern monitors.
It also supports adding custom communication protocols to control the brightness of Monitors connected via USB.
You can find an example implementation for the [Gigabyte M27Q](https://www.gigabyte.com/Monitor/M27Q)
in [here](brightify/src_py/monitors/m27q.py).
The app is designed to be run in the background and can be controlled via a taskbar icon. It also supports a brightness
sensor that can automatically adjust the brightness based on the ambient light.

## Getting started

1. Install brightify by running `pip install Brightify`. This package is regularly uploaded to PyPi. If you want to
   install the latest version, you can clone this repository from
   [GitHub](https://github.com/RerikOp/Brightify) and install it with `pip install -e .` in the root directory.
2. To start the app: `python -m brightify run`. You can exit either by right-clicking the icon in the taskbar and
   selecting "Exit" or by pressing `Ctrl+C` in the terminal.
3. To start the app at startup (or logon) and add a menu icon, run `python -m brightify add all`. To remove the both,
   run
   `python -m brightify remove all`.

### Additional requirements for Linux
As the DDC/CI protocol requires write access to the `/dev/i2c-*` devices, you need to add your user to the `i2c` group (or run the script as the root user).
- First, verify that the group exists by running `getent group i2c`. 
  - If it does not exist, you need to create it by running `sudo groupadd i2c` and also assign the `i2c` devices to the group by running `sudo chown root:i2c /dev/i2c-*`.
- Now you can add your user to the group by running `sudo usermod -aG i2c $USER`. Verify that the user is in the group by running
`groups $USER` and checking if `i2c` is listed. If running `groups` does not show `i2c`, you need restart the system.
- Finally, you might need to change the permissions of the `/dev/i2c-*` so that the group has read/write access. You can do this by running `sudo chmod g+rw /dev/i2c-*`.
  - If this change is not permanent you can create a udev rule by creating a file in `/etc/udev/rules.d/` with the content `KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660"`.
  - After creating the file, you need to reload the udev rules by running `sudo udevadm control --reload-rules && sudo udevadm trigger`.
- To remove the user from the group, run `sudo deluser $USER i2c`.

## Optional arguments

There are several other arguments you can pass to the app, see `python -m brightify --help` for more information.

- To target add/remove only the startup run `python -m brightify add/remove startup`.
    - To add a task to the task scheduler on Windows, pass `--use-scheduler`. It will request elevated permissions.
- To add/remove only the menu icon run `python -m brightify add/remove menu-icon`.
- By default, the terminal will be hidden, but you can change this by passing the `--force-console` argument to the `run` or `add` action.
- To disable animations, pass the `--no-animations` argument to the `run` or `add` action.

## Set up the brightness sensor

- Modify the [SensorComm](brightify/src_py/SensorComm.py) class to match your device and firmware
- Modify the code that is polling from the brightness sensor [Device Firmware](brightify/sensor_firmware/src)
- Modify [platformio.ini](brightify/sensor_firmware/platformio.ini) and enter your board (
  see [supported boards](https://docs.platformio.org/en/latest/boards/index.html))
- Run `pio run -t upload` in the terminal to upload the firmware to the board.
  If everything is working, the *Auto* Checkbox for each supported Monitor should now be clickable

## Remarks

- Currently, only the Windows task bar icon is supported, the main part of this app is OS independent.
- Feel free to create a pull request and add your own USB Monitor
- Note that a USB Monitor will replace a DDC/CI Monitor with the same name. If you want to use both, you need to change
  the name of your USB Monitor implementation.
  In case a monitor is found but does not send its name, we cannot distinguish between DDC/CI and USB Monitors. In this
  case, both will be added.


