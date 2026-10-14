# Copyright NGGT.LightKeeper. All Rights Reserved.

from __future__ import annotations

import logging
import sys


# Logging setup

# Configure standardized application logging and prevent duplicate telebot log output.
def setup_logging() -> None:
    # Formatter and console stream handler (stderr).
    log_format = "%(asctime)s - %(name)-12s - %(levelname)-8s - %(message)s"
    formatter = logging.Formatter(log_format)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Configure root logger with shared console handler.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # Configure telebot logger and disable propagation to avoid duplicate console entries.
    telebot_logger = logging.getLogger("telebot")
    telebot_logger.setLevel(logging.INFO)
    telebot_logger.handlers.clear()
    telebot_logger.addHandler(console_handler)
    telebot_logger.propagate = False
