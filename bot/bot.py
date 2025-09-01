import telebot
import json
import os
import logging
import time
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN
import yt_dlp

# --- Basic Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Globals & Constants ---
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Make paths relative to the script's location
BOT_DIR = os.path.dirname(__file__)
CHAT_ID_FILE = os.path.join(BOT_DIR, 'chat_id.txt')
JSON_FILE_PATH = os.path.join(BOT_DIR, 'urls_to_send.json')
ARCHIVE_DIR = os.path.join(BOT_DIR, 'sent_archive')

TARGET_CHAT_ID = None

# --- Telegram Bot Logic ---

def load_chat_id():
    """Load the target chat ID from the file."""
    global TARGET_CHAT_ID
    if os.path.exists(CHAT_ID_FILE):
        with open(CHAT_ID_FILE, 'r') as f:
            try:
                TARGET_CHAT_ID = int(f.read().strip())
                logger.info(f"Loaded target chat ID: {TARGET_CHAT_ID}")
            except (ValueError, TypeError):
                logger.error(f"Could not read chat ID from file '{CHAT_ID_FILE}'.")
    else:
        logger.warning(f"Chat ID file '{CHAT_ID_FILE}' not found.")

def save_chat_id(chat_id):
    """Save the target chat ID to the file."""
    global TARGET_CHAT_ID
    TARGET_CHAT_ID = chat_id
    with open(CHAT_ID_FILE, 'w') as f:
        f.write(str(chat_id))
    logger.info(f"Saved new target chat ID: {chat_id}")

@bot.message_handler(commands=['start'])
def set_target_chat(message):
    """Sets the chat where this command is issued as the target for receiving URLs.""" 
    save_chat_id(message.chat.id)
    bot.reply_to(
        message,
        "This chat has been set as the target for sending links. "
        "Use the /send command to send all collected links."
    )

@bot.message_handler(commands=['send'])
def send_collected_urls(message):
    """Reads URLs from the JSON file, downloads the videos, and sends them to the target chat."""
    global TARGET_CHAT_ID
    if not TARGET_CHAT_ID:
        bot.reply_to(message, "Target chat is not set. Please use /start first.")
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

        bot.reply_to(message, f"Starting to send {len(urls)} videos...")

        count = 0
        for url in reversed(urls):
            video_path = None
            try:
                # Configure yt-dlp to download the video
                ydl_opts = {
                    'outtmpl': os.path.join(BOT_DIR, 'temp_video_%(id)s.%(ext)s'),
                    'format': 'best[ext=mp4][height<=1080]/best[ext=mp4]/best' # Prefer mp4, up to 1080p
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=True)
                    video_path = ydl.prepare_filename(info_dict)

                # Send the video
                with open(video_path, 'rb') as video:
                    bot.send_video(TARGET_CHAT_ID, video, timeout=120)
                
                count += 1
                time.sleep(7) # Sleep to avoid hitting Telegram rate limits

            except Exception as e:
                logger.error(f"Failed to process and send video for {url}: {e}")
                bot.send_message(TARGET_CHAT_ID, f"""Could not process video from URL:
{url}
Error: {e}""")
            finally:
                # Clean up the downloaded file
                if video_path and os.path.exists(video_path):
                    os.remove(video_path)

        logger.info(f"Successfully sent {count} videos.")
        bot.send_message(TARGET_CHAT_ID, f"Finished sending {count} videos.")

        # Archive the file to prevent re-sending
        if not os.path.exists(ARCHIVE_DIR):
            os.makedirs(ARCHIVE_DIR)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_file_path = os.path.join(ARCHIVE_DIR, f"sent_links_{timestamp}.json")
        os.rename(JSON_FILE_PATH, archive_file_path)
        logger.info(f"Archived processed file to '{archive_file_path}'.")

    except json.JSONDecodeError:
        bot.reply_to(message, "Error: Could not read the link file. It might be corrupted.")
        logger.error(f"Failed to decode {JSON_FILE_PATH}")
    except Exception as e:
        logger.error(f"An error occurred during sending: {e}")
        bot.reply_to(message, f"An unexpected error occurred: {e}")

# --- Main Execution ---

def main():
    """Load initial data and start the bot."""
    load_chat_id()
    logger.info("Telegram bot is starting...")
    bot.polling(non_stop=True)

if __name__ == '__main__':
    main()