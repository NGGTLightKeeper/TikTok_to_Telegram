# Copyright NGGT.LightKeeper. All Rights Reserved.

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any

import telebot

import config
from config import *
import downloader

logger = logging.getLogger(__name__)


# Telegram bot initialization and paths

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE_PATH = os.path.join(BOT_DIR, JSON_FILE_NAME)
ARCHIVE_DIR = os.path.join(BOT_DIR, ARCHIVE_DIR_NAME)


# Bot command handlers

# Reply with current chat ID and configuration instructions for TARGET_CHAT_ID.
@bot.message_handler(commands=["start"])
def get_chat_id(message: telebot.types.Message) -> None:
    chat_id = message.chat.id
    bot.reply_to(
        message,
        "Welcome! To configure this bot, you need to set your chat ID in the configuration file.\n\n"
        f"Your Chat ID is: `{chat_id}`\n\n"
        "Please copy this ID, paste it into the `TARGET_CHAT_ID` variable in the `bot/config.py` file, and restart the bot.",
        parse_mode="Markdown",
    )


# Media item dispatch handlers

# Download and optionally dispatch a video item to the target Telegram chat.
def handle_video_item(item: dict[str, Any], chat_id: int | str) -> bool:
    url = item.get("url")
    if not url:
        logger.error(f"Video item is missing 'url'. Item: {item}")
        return False

    video_path: str | None = None
    try:
        # Download video to root downloads folder (or author subfolder if enabled).
        video_path = downloader.download_video(item)
        if not video_path:
            return False

        # In download-only mode, bypass Telegram dispatch.
        if getattr(config, "DISABLE_VIDEO_SENDING", False):
            logger.info(f"Video downloaded successfully (sending disabled): {video_path}")
            return True

        # Send video file to configured Telegram chat.
        with open(video_path, "rb") as video:
            bot.send_video(chat_id, video, timeout=120)

        logger.info(f"Successfully sent video from URL: {url}")
        return True

    except Exception as e:
        logger.error(f"Failed to process and send video for {url}: {e}", exc_info=True)
        if not getattr(config, "DISABLE_ERROR_MESSAGES", False):
            bot.send_message(chat_id, f"Could not process video from URL:\n{url}\nError: {e}")
        return False

    finally:
        # Remove temporary video unless retention is requested in configuration.
        downloader.cleanup_video(video_path)


# Download photo album images and send them to the Telegram chat as a media group.
def handle_photo_video_item(item: dict[str, Any], chat_id: int | str) -> bool:
    item_id = item.get("itemId")
    temp_dir: str | None = None

    try:
        # Download images into a dedicated temporary folder.
        temp_dir, downloaded_paths = downloader.download_photos(item)
        if not downloaded_paths:
            if not getattr(config, "DISABLE_ERROR_MESSAGES", False):
                bot.send_message(chat_id, f"Could not find images for post: {item.get('url')}")
            return False

        # Construct Telegram media group from downloaded image buffers.
        media_group: list[telebot.types.InputMediaPhoto] = []
        for path in downloaded_paths:
            with open(path, "rb") as photo_file:
                media_group.append(telebot.types.InputMediaPhoto(photo_file.read()))

        if media_group:
            bot.send_media_group(chat_id, media_group, timeout=120)
            logger.info(f"Successfully sent {len(media_group)} photos for item {item_id}.")
            return True

        logger.warning(f"Media group was empty for item {item_id}, nothing to send.")
        return False

    except Exception as e:
        logger.error(f"An unexpected error occurred while handling photo_video item {item_id}: {e}", exc_info=True)
        if not getattr(config, "DISABLE_ERROR_MESSAGES", False):
            bot.send_message(chat_id, f"An error occurred while processing a photo post: {item.get('url')}")
        return False

    finally:
        # Remove temporary image files and parent directory.
        downloader.cleanup_photos(temp_dir)


# Format and dispatch a collected text message to the target Telegram chat.
def handle_message_item(item: dict[str, Any], chat_id: int | str) -> bool:
    author = item.get("author")
    text = item.get("text")
    item_id = item.get("itemId")

    if not all([author, text, item_id]):
        logger.error(f"Message item is missing required fields. Item ID: {item_id}")
        return False

    try:
        # Format message in bold author style.
        formatted_message = f"*{author}:* {text}"
        bot.send_message(chat_id, formatted_message, parse_mode="Markdown")
        logger.info(f"Successfully sent message item: {item_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to send message item {item_id}: {e}", exc_info=True)
        # Fallback to plain unformatted text if markdown parsing rejected the payload.
        if not getattr(config, "DISABLE_ERROR_MESSAGES", False):
            try:
                bot.send_message(chat_id, f"Failed to send formatted message from {author}:\n{text}")
            except Exception as fallback_e:
                logger.error(f"Failed to send fallback message for item {item_id}: {fallback_e}")
        return False


# Queue processing and sending loop

# Process collected queue items, dispatching or downloading each according to configuration.
@bot.message_handler(commands=["send"])
def send_collected_items(message: telebot.types.Message) -> None:
    # Ensure destination chat ID is configured before initiating process.
    if not TARGET_CHAT_ID:
        bot.reply_to(
            message,
            "Error: Target chat ID is not configured.\n"
            "Please run the /start command in the target chat, get the ID, "
            "and set it in the `bot/config.py` file.",
        )
        logger.warning("Send command aborted: TARGET_CHAT_ID is not set in config.py.")
        return

    # Check for presence of the URL queue file on disk.
    if not os.path.exists(JSON_FILE_PATH):
        bot.reply_to(message, "No items in the queue to send.")
        return

    try:
        with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
            items = json.load(f)

        if not isinstance(items, list) or not items:
            bot.reply_to(message, "The item queue is empty or invalid.")
            return

        bot.reply_to(message, f"Starting to send {len(items)} items. This may take a while...")

        sent_count = 0
        total_count = len(items)

        # Resolve processing order: default is reverse chronological (newest first).
        invert_order = getattr(config, "INVERT_PROCESS_ORDER", False) or getattr(config, "INVERT_SEND_ORDER", False)
        ordered_items = items if invert_order else list(reversed(items))

        # Iterate through queue items and dispatch according to type.
        for item in ordered_items:
            item_type = item.get("type") if isinstance(item, dict) else "video"
            success = False

            if item_type == "video":
                success = handle_video_item(item, TARGET_CHAT_ID)
            elif item_type == "photo_video":
                success = handle_photo_video_item(item, TARGET_CHAT_ID)
            elif item_type == "message":
                success = handle_message_item(item, TARGET_CHAT_ID)
            else:
                # Handle legacy string-based URLs for backward compatibility.
                if isinstance(item, str):
                    legacy_item = {"type": "video", "url": item}
                    success = handle_video_item(legacy_item, TARGET_CHAT_ID)
                else:
                    logger.warning(f"Unknown or missing item type: {item_type}. Item: {item}")
                    if not getattr(config, "DISABLE_ERROR_MESSAGES", False):
                        bot.send_message(TARGET_CHAT_ID, f"Unknown item type: {item_type}. Skipping.")

            # Rate limit delays: only sleep if a message consumed Telegram API limit.
            if success:
                sent_count += 1
                if not (item_type == "video" and getattr(config, "DISABLE_VIDEO_SENDING", False)):
                    time.sleep(ASE_DELAY_TIME)
            elif not getattr(config, "DISABLE_ERROR_MESSAGES", False):
                time.sleep(ASE_DELAY_TIME)

        # Send technical completion notification.
        logger.info(f"Successfully processed {sent_count} out of {total_count} items.")
        bot.send_message(TARGET_CHAT_ID, f"Finished sending. Processed {sent_count}/{total_count} items.")

        # Archive processed queue file to prevent duplicate processing.
        if not os.path.exists(ARCHIVE_DIR):
            os.makedirs(ARCHIVE_DIR)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_file_path = os.path.join(ARCHIVE_DIR, f"sent_links_{timestamp}.json")
        os.rename(JSON_FILE_PATH, archive_file_path)
        logger.info(f"Archived processed file to '{archive_file_path}'.")

    except json.JSONDecodeError:
        logger.error(f"Failed to decode {JSON_FILE_PATH}")
        if not getattr(config, "DISABLE_ERROR_MESSAGES", False):
            bot.reply_to(message, "Error: Could not read the item file. It might be corrupted.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the send process: {e}", exc_info=True)
        if not getattr(config, "DISABLE_ERROR_MESSAGES", False):
            bot.reply_to(message, f"An unexpected error occurred: {e}")


# Bot entry point

# Start the Telegram bot polling loop.
def main() -> None:
    logger.info("Telegram bot is starting...")
    bot.polling(non_stop=True)


if __name__ == "__main__":
    main()
