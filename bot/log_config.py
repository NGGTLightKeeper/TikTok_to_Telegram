import logging
import sys

def setup_logging():
    """
    Set up a standardized logging configuration for the application.
    This function configures the root logger and explicitly handles
    the telebot logger to prevent conflicts.
    """
    log_format = "%(asctime)s - %(name)-12s - %(levelname)-8s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Create a shared handler for stderr
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # Explicitly configure the 'telebot' logger to use our handler
    # This prevents telebot from setting up its own conflicting handlers.
    telebot_logger = logging.getLogger('telebot')
    telebot_logger.setLevel(logging.INFO)
    telebot_logger.handlers.clear()
    telebot_logger.addHandler(console_handler)
    # Stop telebot logs from propagating to the root logger to avoid duplicates
    telebot_logger.propagate = False
