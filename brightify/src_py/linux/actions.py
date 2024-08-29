import argparse


def run(app, runtime_args):
    from brightify.src_py.BrightifyApp import BrightifyApp
    brightify_app = BrightifyApp(None, runtime_args)
    running = True

    logger.warning("Linux not tested yet")
    brightify_app.ui_config.theme.has_animations = False
    brightify_app.redraw()
    brightify_app.change_state("show")

    def cleanup():
        nonlocal running
        if not running:
            return
        running = False
        brightify_app.close()

    app.aboutToQuit.connect(cleanup)
    try:
        app.exec()
    finally:
        cleanup()


def add_startup_task(runtime_args):
    raise NotImplementedError("Not implemented yet")


def remove_startup_task():
    raise NotImplementedError("Not implemented yet")


def add_menu_icon(runtime_args: argparse.Namespace):
    raise NotImplementedError("Not implemented yet")


def remove_menu_icon():
    raise NotImplementedError("Not implemented yet")


def add_startup_icon(runtime_args: argparse.Namespace):
    raise NotImplementedError("Not implemented yet")


def remove_startup_icon():
    raise NotImplementedError("Not implemented yet")
