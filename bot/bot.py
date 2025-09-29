# Copyright NGGT.LightKeeper. All Rights Reserved.

import telebot
import json
import os
import logging
import time
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN
import yt_dlp

# --- Basic Setup ---
# Logger is configured in 'main.py' via 'log_config.py'.
logger = logging.getLogger(__name__)

# --- Globals & Constants ---
# Initialize the Telegram bot instance.
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# --- Path Definitions ---
# Use the script's directory as a base to ensure paths are correct.
BOT_DIR = os.path.dirname(__file__)
import requests
from telebot.types import InputMediaPhoto

# --- Path Definitions ---
# Use the script's directory as a base to ensure paths are correct.
BOT_DIR = os.path.dirname(__file__)
# File to store the ID of the target chat for sending content.
CHAT_ID_FILE = os.path.join(BOT_DIR, 'chat_id.txt')
# JSON file where the collector script stores incoming data.
JSON_FILE_PATH = os.path.join(BOT_DIR, 'collected_data.json')
# Directory to move processed JSON files to, preventing re-sends.
ARCHIVE_DIR = os.path.join(BOT_DIR, 'sent_archive')
# Directory for temporary downloads like images.
TEMP_DIR = os.path.join(BOT_DIR, 'temp')

# This global variable will hold the target chat ID after it's loaded.
TARGET_CHAT_ID = None

# --- Telegram Bot Logic ---

def load_chat_id():
    """
    Load the target chat ID from the 'chat_id.txt' file at startup.
    This allows the bot to remember the target chat across restarts.
    """
    global TARGET_CHAT_ID
    if os.path.exists(CHAT_ID_FILE):
        try:
            with open(CHAT_ID_FILE, 'r') as f:
                TARGET_CHAT_ID = int(f.read().strip())
            logger.info(f"Loaded target chat ID: {TARGET_CHAT_ID}")
        except (ValueError, TypeError, IOError) as e:
            logger.error(f"Could not read or parse chat ID from file '{CHAT_ID_FILE}': {e}")
    else:
        logger.warning(f"Chat ID file '{CHAT_ID_FILE}' not found. Use /start to set it.")

def save_chat_id(chat_id):
    """Save the provided chat ID to the 'chat_id.txt' file."""
    global TARGET_CHAT_ID
    TARGET_CHAT_ID = chat_id
    try:
        with open(CHAT_ID_FILE, 'w') as f:
            f.write(str(chat_id))
        logger.info(f"Saved new target chat ID: {chat_id}")
    except IOError as e:
        logger.error(f"Could not write to chat ID file '{CHAT_ID_FILE}': {e}")

@bot.message_handler(commands=['start'])
def set_target_chat(message):
    """
    Command handler for /start.
    Sets the chat where this command is issued as the target for receiving content.
    """
    save_chat_id(message.chat.id)
    bot.reply_to(
        message,
        "This chat has been set as the target for sending content. "
        "Use the /send command to process and send all collected items."
    )

def handle_video(item_data):
    """Processes and sends a single video item."""
    url = item_data.get('url')
    if not url:
        logger.error("Video item has no URL.")
        return

    video_path = None
    try:
        ydl_opts = {
            'outtmpl': os.path.join(TEMP_DIR, 'temp_video_%(id)s.%(ext)s'),
            'format': 'best[ext=mp4][height<=1080]/best[ext=mp4]/best'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info_dict)

        with open(video_path, 'rb') as video:
            bot.send_video(TARGET_CHAT_ID, video, timeout=120)
        logger.info(f"Successfully sent video from {url}")

    except Exception as e:
        logger.error(f"Failed to process video from {url}: {e}", exc_info=True)
        bot.send_message(TARGET_CHAT_ID, f"Could not process video from URL:\n{url}\nError: {e}")
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)

def handle_slideshow(item_data):
    """Processes and sends a slideshow item as a media group."""
    image_urls = item_data.get('images')
    if not image_urls:
        logger.error("Slideshow item has no image URLs.")
        return

    media = []
    temp_files = []
    try:
        for i, url in enumerate(image_urls):
            # Limit to 10 images per group, as per Telegram's limit.
            if i >= 10:
                logger.warning("Slideshow has more than 10 images. Sending only the first 10.")
                break

            response = requests.get(url, stream=True)
            response.raise_for_status()

            # Create a temporary file path.
            temp_path = os.path.join(TEMP_DIR, f"temp_image_{i}.jpg")
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            temp_files.append(temp_path)
            media.append(InputMediaPhoto(open(temp_path, 'rb')))

        if media:
            bot.send_media_group(TARGET_CHAT_ID, media, timeout=60)
            logger.info(f"Successfully sent slideshow with {len(media)} images.")

    except Exception as e:
        logger.error(f"Failed to process slideshow: {e}", exc_info=True)
        bot.send_message(TARGET_CHAT_ID, f"Could not process slideshow. Error: {e}")
    finally:
        # Clean up all temporary image files.
        for file_path in temp_files:
            if os.path.exists(file_path):
                os.remove(file_path)

def handle_chat_message(item_data):
    """Processes and sends a chat message item."""
    text = item_data.get('text')
    if not text:
        logger.error("Chat message item has no text.")
        return

    try:
        bot.send_message(TARGET_CHAT_ID, f"**New Message:**\n\n{text}", parse_mode="Markdown")
        logger.info("Successfully sent chat message.")
    except Exception as e:
        logger.error(f"Failed to send chat message: {e}", exc_info=True)

@bot.message_handler(commands=['send'])
def send_collected_data(message):
    """
    Command handler for /send. Reads items from the JSON file, processes each
    based on its type, and archives the file.
    """
    if not TARGET_CHAT_ID:
        bot.reply_to(message, "Target chat is not set. Use /start in the desired chat first.")
        return

    if not os.path.exists(JSON_FILE_PATH):
        bot.reply_to(message, "No items in the queue to send.")
        return

    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            items = json.load(f)

        if not items:
            bot.reply_to(message, "The item queue is empty.")
            return

        bot.reply_to(message, f"Starting to send {len(items)} items. This may take a while...")

        # A map to dispatch items to the correct handler function.
        handler_map = {
            "video": handle_video,
            "slideshow": handle_slideshow,
            "chat_message": handle_chat_message,
        }

        sent_count = 0
        for item in reversed(items):  # Process oldest items first.
            item_type = item.get("type")
            item_data = item.get("data")

            handler = handler_map.get(item_type)
            if handler and item_data:
                try:
                    handler(item_data)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Error processing item of type '{item_type}': {e}", exc_info=True)
                finally:
                    # Pause between sends to avoid hitting Telegram's rate limits.
                    time.sleep(5)
            else:
                logger.warning(f"Skipping unknown or malformed item: {item}")

        logger.info(f"Successfully processed {sent_count} out of {len(items)} items.")
        bot.send_message(TARGET_CHAT_ID, f"Finished processing. Sent {sent_count} items.")

        # --- Archive Processed File ---
        if not os.path.exists(ARCHIVE_DIR):
            os.makedirs(ARCHIVE_DIR)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_file_path = os.path.join(ARCHIVE_DIR, f"sent_data_{timestamp}.json")
        os.rename(JSON_FILE_PATH, archive_file_path)
        logger.info(f"Archived processed file to '{archive_file_path}'.")

    except json.JSONDecodeError:
        bot.reply_to(message, "Error: Could not read the data file. It might be corrupted.")
        logger.error(f"Failed to decode {JSON_FILE_PATH}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the send process: {e}", exc_info=True)
        bot.reply_to(message, f"An unexpected error occurred: {e}")

# --- Main Execution ---

def main():
    """Load initial data and start the bot's polling loop."""
    # Ensure all necessary directories exist at startup.
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    load_chat_id()
    logger.info("Telegram bot is starting...")
    # Start listening for messages from Telegram. non_stop=True ensures it runs continuously.
    bot.polling(non_stop=True)

if __name__ == '__main__':
    main()
