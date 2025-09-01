import logging
import sys

def setup_logging():
    """
    Set up a standardized logging configuration for the application.
    This function configures the root logger to stream logs to stdout
    with a consistent format.
    """
    # Define a more structured and padded log format
    log_format = "%(asctime)s - %(name)-12s - %(levelname)-8s - %(message)s"
    
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Set the minimum level of logs to capture
    root_logger.setLevel(logging.INFO)

    # Clear any existing handlers to prevent duplicate log entries
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Create a handler to stream logs to standard output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Create a formatter and apply it to the handler
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)

    # Add the configured handler to the root logger
    root_logger.addHandler(console_handler)

    # By default, logs from other libraries (like werkzeug) will now also
    # be captured and formatted by the root logger, standardizing the output.
