import asyncio
import json
import os
import logging
import requests
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import TELEGRAM_TOKEN

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Directories
TEMP_VIDEOS_DIR = 'temp_videos'
os.makedirs(TEMP_VIDEOS_DIR, exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_html(
        "Welcome! Please upload the JSON file exported from the TikTok chat."
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles receiving the JSON file."""
    document = update.message.document
    if document.mime_type != 'application/json':
        await update.message.reply_text("Please upload a valid JSON file.")
        return

    file = await context.bot.get_file(document.file_id)
    file_path = os.path.join(TEMP_VIDEOS_DIR, document.file_name)
    
    await file.download_to_drive(file_path)
    
    await update.message.reply_text(f"File received. Starting to process and send messages...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            messages = json.load(f)
        
        # The messages from content.js are reversed (newest first), so we reverse them back
        messages.reverse()

        for message in messages:
            await process_message(update, context, message)
            await asyncio.sleep(1) # Small delay to avoid rate limiting

        await update.message.reply_text("All messages have been sent successfully!")

    except json.JSONDecodeError:
        await update.message.reply_text("Error: Could not decode the JSON file. Please check the file format.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        await update.message.reply_text(f"An error occurred while processing the file: {e}")
    finally:
        os.remove(file_path) # Clean up the downloaded file

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE, message: dict):
    """Processes a single message from the JSON data."""
    chat_id = update.message.chat_id
    msg_type = message.get('type', 'text')
    content = message.get('content', '')
    author = message.get('author', 'unknown')
    
    caption = f"<b>From:</b> {author}\n\n"

    if not content:
        return # Skip empty messages

    if msg_type == 'text':
        full_message = caption + content
        await context.bot.send_message(chat_id=chat_id, text=full_message, parse_mode='HTML')

    elif msg_type == 'video':
        video_url = content
        video_path = os.path.join(TEMP_VIDEOS_DIR, os.path.basename(video_url.split('?')[0]))
        
        try:
            # Download the video
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            with open(video_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Send the video
            with open(video_path, 'rb') as f:
                await context.bot.send_video(chat_id=chat_id, video=f, caption=caption, parse_mode='HTML')
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download video: {e}")
            await context.bot.send_message(chat_id=chat_id, text=f"{caption} [Failed to download video: {video_url}]", parse_mode='HTML')
        except Exception as e:
            logger.error(f"Failed to send video: {e}")
            await context.bot.send_message(chat_id=chat_id, text=f"{caption} [Failed to send video: {video_url}]", parse_mode='HTML')
        finally:
            if os.path.exists(video_path):
                os.remove(video_path) # Clean up the video file

def main() -> None: 
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.APPLICATION_JSON, handle_document))

    application.run_polling()

if __name__ == '__main__':
    main()
