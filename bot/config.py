# Copyright NGGT.LightKeeper. All Rights Reserved.

# The token obtained from @BotFather on Telegram
# IMPORTANT: Storing tokens directly in the code is insecure.
# For environment variable usage, uncomment the following lines:
# import os
# TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"

# Your Chat ID
# IMPORTANT: The ID must be an integer, not a string.
# Example:
# TARGET_CHAT_ID = -1001234567890
TARGET_CHAT_ID = None


# Delay time (in seconds) between messages to fix Error 429 (Too Many Requests) from Telegram API
# Recommended value 5-15 seconds
ASE_DELAY_TIME = 10

# De-duplication cache length
DD_CACHE_LEN = 10000

DISABLE_ERROR_MESSAGES = True

# Disable deleting downloaded videos after sending (False = delete after sending, True = keep videos in downloads folder)
DISABLE_VIDEO_DELETION = False

# Disable sending videos to Telegram chat, making the application act purely as a video downloader
DISABLE_VIDEO_SENDING = False

# If both DISABLE_VIDEO_DELETION and DISABLE_VIDEO_SENDING are enabled,
# organize downloaded videos into separate folders per author ("uniqueId id")
ORGANIZE_BY_AUTHOR = False

# Invert video processing/sending order from default (default is newest first, True = oldest first)
INVERT_PROCESS_ORDER = False
INVERT_SEND_ORDER = INVERT_PROCESS_ORDER

# Collected data JSON file name
JSON_FILE_NAME = "urls_to_send.json"

# Directory to move processed JSON files to, preventing re-sends.
ARCHIVE_DIR_NAME = "sent_archive"
