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

@bot.message_handler(commands=['send'])
def send_collected_urls(message):
    """
    Command handler for /send.
    Reads URLs from the JSON file, downloads the corresponding videos using yt-dlp,
    sends them to the target chat, and archives the JSON file.
    """
    global TARGET_CHAT_ID
    if not TARGET_CHAT_ID:
        bot.reply_to(message, "Target chat is not set. Please use /start in the desired chat first.")
        return

    if not os.path.exists(JSON_FILE_PATH):
        bot.reply_to(message, "No links in the queue to send.")
        return

    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            urls = json.load(f)

        if not urls:
            bot.reply_to(message, "The link queue is empty.")
            return

        bot.reply_to(message, f"Starting to send {len(urls)} videos. This may take a while...")

        sent_count = 0
        # Process URLs in reverse order to send the oldest ones first.
        for url in reversed(urls):
            video_path = None
            try:
                # --- Video Download using yt-dlp ---
                ydl_opts = {
                    # Save downloaded videos to a temporary file.
                    'outtmpl': os.path.join(BOT_DIR, 'temp_video_%(id)s.%(ext)s'),
                    # Select the best quality MP4 format up to 1080p.
                    'format': 'best[ext=mp4][height<=1080]/best[ext=mp4]/best'
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=True)
                    video_path = ydl.prepare_filename(info_dict)

                # --- Send Video to Telegram ---
                with open(video_path, 'rb') as video:
                    # Increased timeout for large video files.
                    bot.send_video(TARGET_CHAT_ID, video, timeout=120)
                
                sent_count += 1
                # Pause between sends to avoid hitting Telegram's rate limits.
                time.sleep(7)

            except Exception as e:
                logger.error(f"Failed to process and send video for {url}: {e}")
                bot.send_message(TARGET_CHAT_ID, f"Could not process video from URL:\n{url}\nError: {e}")
            finally:
                # --- Cleanup ---
                # Ensure the temporary video file is deleted after sending or on error.
                if video_path and os.path.exists(video_path):
                    os.remove(video_path)

        logger.info(f"Successfully sent {sent_count} out of {len(urls)} videos.")
        bot.send_message(TARGET_CHAT_ID, f"Finished sending {sent_count} videos.")

        # --- Archive Processed File ---
        if not os.path.exists(ARCHIVE_DIR):
            os.makedirs(ARCHIVE_DIR)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_file_path = os.path.join(ARCHIVE_DIR, f"sent_links_{timestamp}.json")
        # Rename the file to archive it. This is an atomic operation on most systems.
        os.rename(JSON_FILE_PATH, archive_file_path)
        logger.info(f"Archived processed file to '{archive_file_path}'.")

    except json.JSONDecodeError:
        bot.reply_to(message, "Error: Could not read the link file. It might be corrupted.")
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
