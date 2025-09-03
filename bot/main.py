# Copyright NGGT.LightKeeper. All Rights Reserved.

import sys
import threading
import time
import logging
import bot
import collector
from log_config import setup_logging

# --- Application Entry Point ---

# Set up centralized logging for the entire application.
# This ensures all modules use a consistent logging format.
setup_logging()
logger = logging.getLogger(__name__)

def run_bot():
    """Wrapper function to run the Telegram bot's main loop in a dedicated thread."""
    logger.info("Starting Telegram bot thread.")
    try:
        bot.main()
    except Exception as e:
        # Log any critical errors that cause the bot thread to crash.
        logger.critical(f"Fatal error in Telegram bot thread: {e}", exc_info=True)

def run_collector():
    """Wrapper function to run the Flask collector server in a dedicated thread."""
    logger.info("Starting Flask collector thread.")
    try:
        collector.main()
    except Exception as e:
        # Log any critical errors that cause the collector thread to crash.
        logger.critical(f"Fatal error in Flask collector thread: {e}", exc_info=True)

if __name__ == "__main__":
    # This script requires a 'runserver' argument to start.
    # This prevents it from running accidentally.
    if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
        logger.info("Initializing application...")

        # --- Threading Setup ---
        # Create a thread for the Telegram bot.
        # It's a daemon thread, so it will exit when the main thread exits.
        bot_thread = threading.Thread(target=run_bot, name="BotThread", daemon=True)

        # Create a thread for the Flask URL collector.
        collector_thread = threading.Thread(target=run_collector, name="CollectorThread", daemon=True)

        # Start both threads. They will run in parallel.
        bot_thread.start()
        collector_thread.start()

        logger.info("Bot and collector threads have been started.")

        # --- Main Loop ---
        # Keep the main thread alive. This is necessary because the other threads
        # are daemons. If the main thread were to exit, the daemon threads would be
        # terminated abruptly.
        try:
            while True:
                # This loop does nothing but sleep, waiting for a shutdown signal.
                time.sleep(1)
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully.
            logger.info("Shutdown signal (KeyboardInterrupt) received. Exiting.")
            # The daemon threads will be terminated automatically when the main program exits.
    else:
        # If the 'runserver' argument is missing, show usage instructions.
        print("Usage: python main.py runserver")
        sys.exit(1)
