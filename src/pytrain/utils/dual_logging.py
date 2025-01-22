#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

# -------------------------------------------------------------------------------
#                                                                               -
#  Python dual-logging setup (console and log file),                            -
#  supporting different log levels and colorized output                         -
#                                                                               -
#  Created by Fonic <https://github.com/fonic>                                  -
#  Date: 04/05/20 - 02/07/23                                                    -
#                                                                               -
#  Based on:                                                                    -
#  https://stackoverflow.com/a/13733863/1976617                                 -
#  https://uran198.github.io/en/python/2016/07/12/colorful-python-logging.html  -
#  https://en.wikipedia.org/wiki/ANSI_escape_code#Colors                        -
#                                                                               -
# -------------------------------------------------------------------------------

import logging
import logging.handlers
import os

# Imports
import sys


# Logging formatter supporting colorized output
class LogFormatter(logging.Formatter):
    COLOR_CODES = {
        logging.CRITICAL: "\033[1;35m",  # bright/bold magenta
        logging.ERROR: "\033[1;31m",  # bright/bold red
        logging.WARNING: "\033[1;33m",  # bright/bold yellow
        logging.INFO: "\033[40;37m",  # white / light gray
        logging.DEBUG: "\033[1;30m",  # bright/bold dark gray
    }

    RESET_CODE = "\033[0m"

    def __init__(self, color, *args, **kwargs):
        super(LogFormatter, self).__init__(*args, **kwargs)
        self.color = color

    def format(self, record, *args, **kwargs):
        if self.color is True and record.levelno in self.COLOR_CODES:
            record.color = self.COLOR_CODES[record.levelno]
            record.no_color = self.RESET_CODE
        else:
            record.color = ""
            record.no_color = ""
        return super(LogFormatter, self).format(record)


class ConsoleFormatter(LogFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def formatException(self, exc_info):
        return ""

    def formatStack(self, stack_trace):
        return ""


# Set up logging
def set_up_logging(
    console_log_output: str = "stdout",
    console_log_level: str = "INFO",
    console_log_color: bool = True,
    console_template: str = "%(color)s%(message)s%(no_color)s",
    logfile_file: str = "pytrain.log",
    logfile_log_level: str = "INFO",
    logfile_log_color: bool = False,
    logfile_template: str = "%(color)s[%(asctime)s] [%(name)s] [%(levelname)-8s] %(message)s%(no_color)s",
) -> bool:
    # Create logger
    # For simplicity, we use the root logger, i.e. call 'logging.getLogger()'
    # without name argument. This way we can simply use module methods for
    # logging throughout the script. An alternative would be exporting the
    # logger, i.e. 'global logger; logger = logging.getLogger("<name>")'
    logger = logging.getLogger()

    # Set global log level to 'debug' (required for handler levels to work)
    logger.setLevel(logging.DEBUG)

    # Create console handler
    console_log_output = console_log_output.lower()
    if console_log_output == "stdout":
        console_log_output = sys.stdout
    elif console_log_output == "stderr":
        console_log_output = sys.stderr
    else:
        print("Failed to set console output: invalid output: '%s'" % console_log_output)
        return False
    console_handler = logging.StreamHandler(console_log_output)

    # Set console log level
    try:
        console_handler.setLevel(console_log_level.upper())  # only accepts uppercase level names
    except Exception as e:
        print(f"Failed to set console log level: invalid level: '{console_log_level}': {e}")
        return False

    # Create and set formatter, add console handler to logger
    console_formatter = ConsoleFormatter(fmt=console_template, color=console_log_color)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Create log file handler
    try:
        should_roll_over = os.path.isfile(logfile_file)
        logfile_handler = logging.handlers.RotatingFileHandler(logfile_file, backupCount=4)
        if should_roll_over:  # log already exists, roll over!
            logfile_handler.doRollover()
    except Exception as exception:
        print(f"Failed to set up log file: {str(exception)}")
        return False

    # Set log file log level
    try:
        logfile_handler.setLevel(logfile_log_level.upper())  # only accepts uppercase level names
    except Exception as e:
        print(f"Failed to set log file log level: invalid level: '{logfile_log_level}': {e}")
        return False

    # Create and set formatter, add log file handler to logger
    logfile_formatter = LogFormatter(fmt=logfile_template, color=logfile_log_color)
    logfile_handler.setFormatter(logfile_formatter)
    logger.addHandler(logfile_handler)

    # Success
    return True


# Main function
def main():
    # Set up logging
    if not set_up_logging():
        print("Failed to set up logging, aborting.")
        return 1

    # Log some messages
    logging.debug("Debug message")
    logging.info("Info message")
    logging.warning("Warning message")
    logging.error("Error message")
    logging.critical("Critical message")


# Call main function
if __name__ == "__main__":
    sys.exit(main())
