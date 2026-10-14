# Copyright NGGT.LightKeeper. All Rights Reserved.

import telebot
import json
import os
import logging
import time
from datetime import datetime
import config
from config import *
import downloader

# --- Basic Setup ---
# Logger is configured in 'main.py' via 'log_config.py'.
logger = logging.getLogger(__name__)

# --- Globals & Constants ---
# Initialize the Telegram bot instance.
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# --- Path Definitions ---
# Use the script's directory as a base to ensure paths are correct.
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
# JSON file where the collector script stores incoming URLs.
JSON_FILE_PATH = os.path.join(BOT_DIR, JSON_FILE_NAME)
# Directory to move processed JSON files to, preventing re-sends.
ARCHIVE_DIR = os.path.join(BOT_DIR, ARCHIVE_DIR_NAME)


# --- Telegram Bot Logic ---

@bot.message_handler(commands=['start'])
def get_chat_id(message):
    """
    Command handler for /start.
    Replies with the current chat's ID and instructions on how to set it in the config.
    """
    chat_id = message.chat.id
    bot.reply_to(
        message,
        "Welcome! To configure this bot, you need to set your chat ID in the configuration file.\n\n"
        f"Your Chat ID is: `{chat_id}`\n\n"
        "Please copy this ID, paste it into the `TARGET_CHAT_ID` variable in the `bot/config.py` file, and restart the bot.",
        parse_mode='Markdown'
    )

# --- Item Type Handlers ---

def handle_video_item(item, chat_id):
    """Handles downloading and optionally sending a video item."""
    url = item.get('url')
    if not url:
        logger.error(f"Video item is missing 'url'. Item: {item}")
        return False

    video_path = None
    try:
        video_path = downloader.download_video(item)
        if not video_path:
            return False

        # If sending is disabled, act purely as a downloader
        if getattr(config, 'DISABLE_VIDEO_SENDING', False):
            logger.info(f"Video downloaded successfully (sending disabled): {video_path}")
            return True

        with open(video_path, 'rb') as video:
            bot.send_video(chat_id, video, timeout=120)

        logger.info(f"Successfully sent video from URL: {url}")
        return True
    except Exception as e:
        logger.error(f"Failed to process and send video for {url}: {e}", exc_info=True)
        if not getattr(config, 'DISABLE_ERROR_MESSAGES', False):
            bot.send_message(chat_id, f"Could not process video from URL:\n{url}\nError: {e}")
        return False
    finally:
        downloader.cleanup_video(video_path)

def handle_photo_video_item(item, chat_id):
    """
    Handles a 'photo_video' item by downloading its images and sending them as a media group.
    """
    item_id = item.get('itemId')
    temp_dir = None
    try:
        temp_dir, downloaded_paths = downloader.download_photos(item)

        if not downloaded_paths:
            if not getattr(config, 'DISABLE_ERROR_MESSAGES', False):
                bot.send_message(chat_id, f"Could not find images for post: {item.get('url')}")
            return False

        media_group = []
        for path in downloaded_paths:
            with open(path, 'rb') as photo_file:
                media_group.append(telebot.types.InputMediaPhoto(photo_file.read()))

        if media_group:
            bot.send_media_group(chat_id, media_group, timeout=120)
            logger.info(f"Successfully sent {len(media_group)} photos for item {item_id}.")
            return True
        else:
            logger.warning(f"Media group was empty for item {item_id}, nothing to send.")
            return False

    except Exception as e:
        logger.error(f"An unexpected error occurred while handling photo_video item {item_id}: {e}", exc_info=True)
        if not getattr(config, 'DISABLE_ERROR_MESSAGES', False):
            bot.send_message(chat_id, f"An error occurred while processing a photo post: {item.get('url')}")
        return False
    finally:
        downloader.cleanup_photos(temp_dir)

def handle_message_item(item, chat_id):
    """Handles formatting and sending a text message item."""
    author = item.get('author')
    text = item.get('text')
    item_id = item.get('itemId')

    if not all([author, text, item_id]):
        logger.error(f"Message item is missing required fields. Item ID: {item_id}")
        return False

    try:
        # Format the message: **Author:** Text
        formatted_message = f"*{author}:* {text}"

        bot.send_message(chat_id, formatted_message, parse_mode='Markdown')
        logger.info(f"Successfully sent message item: {item_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send message item {item_id}: {e}", exc_info=True)
        # Optionally, send a plain text version if formatting fails
        if not getattr(config, 'DISABLE_ERROR_MESSAGES', False):
            try:
                bot.send_message(chat_id, f"Failed to send formatted message from {author}:\n{text}")
            except Exception as fallback_e:
                logger.error(f"Failed to send fallback message for item {item_id}: {fallback_e}")
        return False

@bot.message_handler(commands=['send'])
def send_collected_items(message):
    """
    Command handler for /send.
    Reads items from the JSON file, processes them based on their type,
    sends or downloads the content, and archives the JSON file.
    """
    # Check if the target chat ID is configured.
    if not TARGET_CHAT_ID:
        bot.reply_to(
            message,
            "Error: Target chat ID is not configured.\n"
            "Please run the /start command in the target chat, get the ID, "
            "and set it in the `bot/config.py` file."
        )
        logger.warning("Send command aborted: TARGET_CHAT_ID is not set in config.py.")
        return

    if not os.path.exists(JSON_FILE_PATH):
        bot.reply_to(message, "No items in the queue to send.")
        return

    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            items = json.load(f)

        if not isinstance(items, list) or not items:
            bot.reply_to(message, "The item queue is empty or invalid.")
            return

        bot.reply_to(message, f"Starting to send {len(items)} items. This may take a while...")

        sent_count = 0
        total_count = len(items)

        # Order items according to INVERT_PROCESS_ORDER configuration:
        # Default order is reverse chronological (newest first).
        # Inverted order is chronological (oldest first).
        invert_order = getattr(config, 'INVERT_PROCESS_ORDER', False) or getattr(config, 'INVERT_SEND_ORDER', False)
        ordered_items = items if invert_order else list(reversed(items))

        for item in ordered_items:
            item_type = item.get('type')
            success = False

            if item_type == 'video':
                success = handle_video_item(item, TARGET_CHAT_ID)
            elif item_type == 'photo_video':
                success = handle_photo_video_item(item, TARGET_CHAT_ID)
            elif item_type == 'message':
                success = handle_message_item(item, TARGET_CHAT_ID)
            else:
                # Handle legacy string-based URLs for backward compatibility
                if isinstance(item, str):
                    legacy_item = {'type': 'video', 'url': item}
                    success = handle_video_item(legacy_item, TARGET_CHAT_ID)
                else:
                    logger.warning(f"Unknown or missing item type: {item_type}. Item: {item}")
                    if not getattr(config, 'DISABLE_ERROR_MESSAGES', False):
                        bot.send_message(TARGET_CHAT_ID, f"Unknown item type: {item_type}. Skipping.")

            if success:
                sent_count += 1
                # If this was a video and sending is disabled, no Telegram API request was made,
                # so skip delay to allow fast downloading.
                if not (item_type == 'video' and getattr(config, 'DISABLE_VIDEO_SENDING', False)):
                    time.sleep(ASE_DELAY_TIME)
            elif not getattr(config, 'DISABLE_ERROR_MESSAGES', False):
                # Pause after sending an error message to avoid hitting Telegram's rate limits.
                time.sleep(ASE_DELAY_TIME)

        logger.info(f"Successfully sent {sent_count} out of {total_count} items.")
        bot.send_message(TARGET_CHAT_ID, f"Finished sending. Processed {sent_count}/{total_count} items.")

        # --- Archive Processed File ---
        if not os.path.exists(ARCHIVE_DIR):
            os.makedirs(ARCHIVE_DIR)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_file_path = os.path.join(ARCHIVE_DIR, f"sent_links_{timestamp}.json")
        os.rename(JSON_FILE_PATH, archive_file_path)
        logger.info(f"Archived processed file to '{archive_file_path}'.")

    except json.JSONDecodeError:
        logger.error(f"Failed to decode {JSON_FILE_PATH}")
        if not getattr(config, 'DISABLE_ERROR_MESSAGES', False):
            bot.reply_to(message, "Error: Could not read the item file. It might be corrupted.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the send process: {e}", exc_info=True)
        if not getattr(config, 'DISABLE_ERROR_MESSAGES', False):
            bot.reply_to(message, f"An unexpected error occurred: {e}")

# --- Main Execution ---

def main():
    """Start the bot's polling loop."""
    logger.info("Telegram bot is starting...")
    # Start listening for messages from Telegram. non_stop=True ensures it runs continuously.
    bot.polling(non_stop=True)

if __name__ == '__main__':
    main()
