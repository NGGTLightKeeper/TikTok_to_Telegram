# Copyright NGGT.LightKeeper. All Rights Reserved.

from __future__ import annotations

import logging
import sys
import threading
import time

import bot
import collector
from log_config import setup_logging

# Initialize centralized application logging.
setup_logging()
logger = logging.getLogger(__name__)


# Thread runner routines

# Run the Telegram bot event polling loop in a dedicated thread.
def run_bot() -> None:
    logger.info("Starting Telegram bot thread.")
    try:
        bot.main()
    except Exception as e:
        logger.critical(f"Fatal error in Telegram bot thread: {e}", exc_info=True)


# Run the Flask collector HTTP server in a dedicated thread.
def run_collector() -> None:
    logger.info("Starting Flask collector thread.")
    try:
        collector.main()
    except Exception as e:
        logger.critical(f"Fatal error in Flask collector thread: {e}", exc_info=True)


# Application entry point

if __name__ == "__main__":
    # Validate command-line arguments to prevent unintended executions.
    if len(sys.argv) <= 1 or sys.argv[1] != "runserver":
        print("Usage: python main.py runserver")
        sys.exit(1)

    logger.info("Initializing application...")

    # Spawn daemon worker threads for the Telegram bot and Flask collector.
    bot_thread = threading.Thread(target=run_bot, name="BotThread", daemon=True)
    collector_thread = threading.Thread(target=run_collector, name="CollectorThread", daemon=True)

    bot_thread.start()
    collector_thread.start()
    logger.info("Bot and collector threads have been started.")

    # Keep main thread alive until shutdown signal is received.
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown signal (KeyboardInterrupt) received. Exiting.")
