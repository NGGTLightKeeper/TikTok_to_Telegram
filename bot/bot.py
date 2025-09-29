# Copyright NGGT.LightKeeper. All Rights Reserved.

import telebot
import json
import os
import logging
import time
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN
import yt_dlp
import requests
import shutil

# --- Basic Setup ---
# Logger is configured in 'main.py' via 'log_config.py'.
logger = logging.getLogger(__name__)

# --- Globals & Constants ---
# Initialize the Telegram bot instance.
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# --- Path Definitions ---
# Use the script's directory as a base to ensure paths are correct.
BOT_DIR = os.path.dirname(__file__)
# File to store the ID of the target chat for sending videos.
CHAT_ID_FILE = os.path.join(BOT_DIR, 'chat_id.txt')
# JSON file where the collector script stores incoming URLs.
JSON_FILE_PATH = os.path.join(BOT_DIR, 'urls_to_send.json')
# Directory to move processed JSON files to, preventing re-sends.
ARCHIVE_DIR = os.path.join(BOT_DIR, 'sent_archive')

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
        with open(CHAT_ID_FILE, 'r') as f:
            try:
                TARGET_CHAT_ID = int(f.read().strip())
                logger.info(f"Loaded target chat ID: {TARGET_CHAT_ID}")
            except (ValueError, TypeError):
                logger.error(f"Could not parse chat ID from file '{CHAT_ID_FILE}'.")
    else:
        logger.warning(f"Chat ID file '{CHAT_ID_FILE}' not found. Use /start to set it.")

def save_chat_id(chat_id):
    """Save the provided chat ID to the 'chat_id.txt' file."""
    global TARGET_CHAT_ID
    TARGET_CHAT_ID = chat_id
    with open(CHAT_ID_FILE, 'w') as f:
        f.write(str(chat_id))
    logger.info(f"Saved new target chat ID: {chat_id}")

@bot.message_handler(commands=['start'])
def set_target_chat(message):
    """
    Command handler for /start.
    Sets the chat where this command is issued as the target for receiving videos.
    """
    save_chat_id(message.chat.id)
    bot.reply_to(
        message,
        "This chat has been set as the target for sending links. "
        "Use the /send command to process and send all collected links."
    )

# --- Item Type Handlers ---

def handle_video_item(item, chat_id):
    """Handles downloading and sending a video item."""
    url = item.get('url')
    if not url:
        logger.error(f"Video item is missing 'url'. Item: {item}")
        return False

    video_path = None
    try:
        ydl_opts = {
            'outtmpl': os.path.join(BOT_DIR, 'temp_video_%(id)s.%(ext)s'),
            'format': 'best[ext=mp4][height<=1080]/best[ext=mp4]/best'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info_dict)

        with open(video_path, 'rb') as video:
            bot.send_video(chat_id, video, timeout=120)

        logger.info(f"Successfully sent video from URL: {url}")
        return True
    except Exception as e:
        logger.error(f"Failed to process and send video for {url}: {e}", exc_info=True)
        bot.send_message(chat_id, f"Could not process video from URL:\n{url}\nError: {e}")
        return False
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)

def handle_photo_video_item(item, chat_id):
    """
    Handles a 'photo_video' item by downloading its images and sending them as a media group.
    """
    item_id = item.get('itemId')
    api_response = item.get('apiResponse')

    if not all([item_id, api_response]):
        logger.error(f"Photo_video item {item_id} is missing 'itemId' or 'apiResponse'.")
        return False

    temp_dir = None
    try:
        # Extract image URLs from the API response
        images = api_response.get('itemInfo', {}).get('itemStruct', {}).get('imagePost', {}).get('images', [])
        image_urls = [img.get('displayImage', {}).get('url_list', [None])[0] for img in images]
        image_urls = [url for url in image_urls if url] # Filter out any None URLs

        if not image_urls:
            logger.warning(f"No image URLs found for item {item_id}.")
            bot.send_message(chat_id, f"Could not find images for post: {item.get('url')}")
            return False

        # Create a unique temporary directory for this item's images
        temp_dir = os.path.join(BOT_DIR, f'temp_images_{item_id}')
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        media_group = []
        downloaded_paths = []

        # Download each image
        for i, url in enumerate(image_urls):
            try:
                response = requests.get(url, stream=True)
                response.raise_for_status()

                # Use a generic filename, as the extension is often missing in the URL
                file_path = os.path.join(temp_dir, f'image_{i}.jpg')
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                downloaded_paths.append(file_path)
            except requests.RequestException as e:
                logger.error(f"Failed to download image {i+1} for item {item_id} from {url}: {e}")
                # Continue to try sending the successfully downloaded images
                continue

        if not downloaded_paths:
            logger.error(f"Failed to download any images for item {item_id}.")
            return False

        # Prepare media group for sending
        for path in downloaded_paths:
            with open(path, 'rb') as photo_file:
                # For the first photo, we read it directly. For subsequent ones, we attach them.
                # This seems to be a reliable way to handle media groups with local files.
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
        bot.send_message(chat_id, f"An error occurred while processing a photo post: {item.get('url')}")
        return False
    finally:
        # Clean up the temporary directory and its contents
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")

def handle_message_item(item, chat_id):
    """Handles formatting and sending a text message item."""
    author = item.get('author')
    text = item.get('text')
    item_id = item.get('itemId')

    if not all([author, text, item_id]):
        logger.error(f"Message item is missing required fields. Item ID: {item_id}")
        return False

    try:
        # Format the message as requested: **Author:** Text
        # Using 'MarkdownV2' parse mode requires escaping special characters.
        # However, for simple bolding, the default mode or 'Markdown' is safer.
        # Let's stick to a simple format that's less prone to parsing errors.
        formatted_message = f"*{author}:* {text}"

        bot.send_message(chat_id, formatted_message, parse_mode='Markdown')
        logger.info(f"Successfully sent message item: {item_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send message item {item_id}: {e}", exc_info=True)
        # Optionally, send a plain text version if formatting fails
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
    sends the content to the target chat, and archives the JSON file.
    """
    global TARGET_CHAT_ID
    if not TARGET_CHAT_ID:
        bot.reply_to(message, "Target chat is not set. Please use /start in the desired chat first.")
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
        # Process items in chronological order (oldest first).
        for item in items:
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
                    bot.send_message(TARGET_CHAT_ID, f"Unknown item type: {item_type}. Skipping.")

            if success:
                sent_count += 1

            # Pause between sends to avoid hitting Telegram's rate limits.
            time.sleep(5)

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
        bot.reply_to(message, "Error: Could not read the item file. It might be corrupted.")
        logger.error(f"Failed to decode {JSON_FILE_PATH}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the send process: {e}", exc_info=True)
        bot.reply_to(message, f"An unexpected error occurred: {e}")

# --- Main Execution ---

def main():
    """Load initial data and start the bot's polling loop."""
    load_chat_id()
    logger.info("Telegram bot is starting...")
    # Start listening for messages from Telegram. non_stop=True ensures it runs continuously.
    bot.polling(non_stop=True)

if __name__ == '__main__':
    main()
