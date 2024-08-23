import atexit
import copy
import datetime as dt
import json
import logging
import sys
from logging import handlers
import logging.config

from brightify import res_dir, log_dir

LOG_RECORD_BUILTIN_ATTRS = {
    "args",  # The tuple of arguments merged into msg to produce message, or a dict whose values are used for the merge.
    "asctime",
    # Human-readable time when the LogRecord was created. By default, this is of the form '2003-07-08 16:49:45,896'.
    "created",  # Time when the LogRecord was created (as returned by time.time()).
    "exc_info",  # Exception tuple (à la sys.exc_info) or, if no exception has occurred, None.
    "exc_text",  # Text rendering of the exception info, if available, otherwise None.
    "filename",  # Filename portion of pathname.
    "funcName",  # Name of function containing the logging call.
    "levelname",  # Text logging level for the message ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
    "levelno",  # Numeric logging level for the message (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    "lineno",  # Source line number where the logging call was made.
    "module",  # Module (name portion of filename).
    "msecs",  # Millisecond portion of the time when the LogRecord was created.
    "message",  # The logged message, computed as msg % args.
    "msg",  # The format string passed in the original logging call.
    "name",  # Name of the logger used to log the call.
    "pathname",  # Full pathname of the source file where the logging call was made.
    "process",  # Process ID (if available).
    "processName",  # Process name (if available).
    "relativeCreated",
    # Time in milliseconds when the LogRecord was created, relative to the time the logging module was loaded.
    "stack_info",  # Stack frame information (where available) corresponding to where the logging call was made.
    "thread",  # Thread ID (if available).
    "threadName",  # Thread name (if available).
    "taskName",  # Task name (if available).
}


class BrightifyLogQueueHandler(handlers.QueueHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        formatter = logging.Formatter()
        self.setFormatter(formatter)

    def prepare(self, record):
        exc_info = record.exc_info
        record = copy.copy(record)
        # Don't add the exc_info to the message
        record.exc_info = None
        # format the message
        msg = self.format(record)
        record.message = msg
        # format the exc_info
        record.exc_text = self.formatter.formatException(exc_info) if exc_info else None

        return record


class BrightifyLog(logging.Formatter):
    def __init__(self, *, fmt_keys: dict[str, str] | None = None):
        super().__init__()
        self.fmt_keys = fmt_keys if fmt_keys is not None else {}

    def format(self, record: logging.LogRecord) -> str:
        message = self._prepare_log_dict(record)
        return json.dumps(message, default=str)

    def _prepare_log_dict(self, record: logging.LogRecord):
        basic_info = {
            "message": record.getMessage(),
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
        }

        if record.exc_info is not None:
            basic_info["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info is not None:
            basic_info["stack_info"] = self.formatStack(record.stack_info)

        message = {
            key: msg_val if (msg_val := basic_info.pop(val, None)) is not None else getattr(record, val)
            for key, val in self.fmt_keys.items()
        }
        message.update(basic_info)

        for key, val in record.__dict__.items():
            if key not in LOG_RECORD_BUILTIN_ATTRS:
                message[key] = val

        return message


class WarningAndAbove(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool | logging.LogRecord:
        return record.levelno <= logging.INFO


class InfoAndBelow(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool | logging.LogRecord:
        return record.levelno > logging.INFO


def remove_queue_handler(config: dict):
    # pop the queue handler from the handlers
    queue_handler = config["handlers"].pop("queue_handler")
    queue_handler.pop("class")  # remove the class key
    # add the level to the root logger
    queue_handler["level"] = "DEBUG"
    # link the handlers to the root logger
    config["loggers"]["root"] = queue_handler


def modify_log_config(config: dict):
    # if python version is < 3.12, remove the queue handler and link everything to the root logger
    if sys.version_info < (3, 12):
        remove_queue_handler(config)

    # update the filename to the logs dir
    for handler, handler_config in config["handlers"].items():
        if "filename" in handler_config.keys():
            filename = handler_config["filename"]
            abs_path = log_dir / filename
            config["handlers"][handler]["filename"] = str(abs_path)


def start_logging():
    if (3, 12) <= sys.version_info:
        queue_handler = logging.getHandlerByName("queue_handler")
        if queue_handler is not None and hasattr(queue_handler, "listener"):
            queue_handler.listener.start()
            atexit.register(queue_handler.listener.stop)


def configure_logging():
    import tomllib as toml
    # make sure logs dir exists
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(res_dir / "log_config.toml", "rb") as f:
        config = toml.load(f)
    modify_log_config(config)
    logging.config.dictConfig(config)
