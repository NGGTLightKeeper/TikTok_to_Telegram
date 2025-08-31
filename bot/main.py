import sys
import threading
import time
import logging
import bot, collector

# --- Basic Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def run_bot():
    """Target function to run the Telegram bot."""
    logger.info("Starting Telegram bot thread.")
    try:
        bot.main()
    except Exception as e:
        logger.error(f"Error in Telegram bot thread: {e}", exc_info=True)

def run_collector():
    """Target function to run the Flask collector."""
    logger.info("Starting Flask collector thread.")
    try:
        collector.main()
    except Exception as e:
        logger.error(f"Error in Flask collector thread: {e}", exc_info=True)

if __name__ == "__main__":
    # Check for the 'runserver' command
    if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
        logger.info("Initializing application...")

        # Create thread for the Telegram bot
        bot_thread = threading.Thread(target=run_bot, name="BotThread", daemon=True)

        # Create thread for the Flask collector
        collector_thread = threading.Thread(target=run_collector, name="CollectorThread", daemon=True)

        # Start the threads
        bot_thread.start()
        collector_thread.start()

        logger.info("Both threads have been started.")

        # Keep the main thread alive to allow daemon threads to run
        # and to gracefully handle shutdown.
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutdown signal received. Exiting main thread.")
            # Daemon threads will be terminated automatically
    else:
        # If the command is not 'runserver', print usage instructions
        print("Usage: python main.py runserver")
        sys.exit(1)