# Getting started
1. Create virtual environment `python -m venv venv`
2. Activate the virtual environment
   1. On Windows run `./venv/Scripts/activate`
   2. On Mac or Linux run  `source .venv/bin/activate`
3. Install dependencies `pip install -r requirements.txt`
4. (Optional) Add your own implementation of [MonitorBase](monitors/monitor_base.py) for your Monitor
5. Run `python brightify.py`
6. To exit either right-click the icon and press **Exit** or press **CRTL + C** in the Terminal

# Set up the brightness sensor
1. Modify the [config](config.py) to match your device and firmware
2. Modify the code that is polling from the brightness sensor [Device Firmware](firmware/src)
3. Modify [platformio.ini](firmware/platformio.ini) and enter your board (see [supported boards](https://docs.platformio.org/en/latest/boards/index.html))
4. Run `pio run -t upload` in the terminal to upload the firmware to the board.
If everything is working, the *Auto* Checkbox for each supported Monitor should now be clickable 

# Remarks
+ Currently, only the Windows task bar icon is supported, the main part of this app is OS independent
+ Feel free to create a pull request and add your own Monitor ;)
+ In case your Monitor is not found, try to enable the `use_libusb` flag in the get_supported_monitors function in [misc.py](misc.py)
For further information see this [FAQ](https://github.com/pyusb/pyusb/blob/master/docs/faq.rst)


