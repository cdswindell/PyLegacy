import logging
import sys
from logging import INFO


class Logger(object):
    loggers = set()

    def __init__(
        self,
        name: str = __name__,
        formatter: str = "%(asctime)s | %(levelname)s | %(message)s",
        level: int = INFO,
    ):
        # Initial construct.
        self.format = formatter
        self.level = level
        self.name = name

        # Logger configuration.
        self.console_formatter = logging.Formatter(self.format)
        self.console_logger = logging.StreamHandler(sys.stdout)
        self.console_logger.setFormatter(self.console_formatter)

        # Complete logging config.
        self.logger = logging.getLogger(name)
        print(name)
        if name not in self.loggers:
            self.loggers.add(name)
            self.logger.setLevel(self.level)
            self.logger.addHandler(self.console_logger)

    def info(self, msg: str | Exception, *args, **kwargs) -> None:
        msg = str(msg) if isinstance(msg, Exception) else msg
        self.logger.info(msg, *args, **kwargs)

    def error(self, msg: str | Exception, *args, **kwargs) -> None:
        msg = str(msg) if isinstance(msg, Exception) else msg
        self.logger.error(msg, *args, **kwargs)

    def debug(self, msg: str | Exception, *args, **kwargs) -> None:
        msg = str(msg) if isinstance(msg, Exception) else msg
        self.logger.debug(msg, *args, **kwargs)

    def warning(self, msg: str | Exception, *args, **kwargs) -> None:
        msg = str(msg) if isinstance(msg, Exception) else msg
        self.logger.warning(msg, *args, **kwargs)
