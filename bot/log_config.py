# Copyright NGGT.LightKeeper. All Rights Reserved.

import logging
import sys

def setup_logging():
    """
    Set up a standardized logging configuration for the entire application.

    This function configures the root logger to ensure all modules use a
    consistent format. It also specifically handles the 'telebot' logger
    to prevent it from creating duplicate handlers, which can lead to
    redundant log messages.
    """
    # Define a standard format for all log messages.
    log_format = "%(asctime)s - %(name)-12s - %(levelname)-8s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Create a handler to output log messages to the console (stderr).
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)  # Set the minimum level of messages to handle.
    console_handler.setFormatter(formatter)

    # Get the root logger and configure it.
    # All other loggers in the application will inherit this configuration.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear any existing handlers to avoid conflicts or multiple outputs.
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    
    # Add our configured handler to the root logger.
    root_logger.addHandler(console_handler)

    # --- Special Handling for Telebot Logger ---
    # Get the logger used by the 'telebot' library.
    telebot_logger = logging.getLogger('telebot')
    telebot_logger.setLevel(logging.INFO)
    
    # Clear any default handlers that telebot might add.
    telebot_logger.handlers.clear()
    
    # Add our shared handler to the telebot logger.
    telebot_logger.addHandler(console_handler)
    
    # Prevent telebot log messages from being passed up to the root logger.
    # This is crucial to avoid duplicate log entries.
    telebot_logger.propagate = False
