# bot.py
import asyncio
import os
import telegram
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
import tiktok_handler
import config
from datetime import datetime

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command and replies with the chat ID."""
    chat_id = update.message.chat_id
    await update.message.reply_text(f"Ваш Chat ID: {chat_id}")

async def sync_messages(context: ContextTypes.DEFAULT_TYPE):
    """Fetches messages from TikTok and sends them to Telegram."""
    bot = context.bot
    print("Fetching messages from TikTok...")
    
    # Using mock data as the library does not support DMs
    messages = await tiktok_handler.get_tiktok_messages(
        session_id=config.TIKTOK_SESSION_ID_COOKIE,
        target_username=config.TIKTOK_TARGET_CHAT_USERNAME,
        from_date_str=config.START_DATE
    )

    if not messages:
        print("No new messages found.")
        await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text="Новых сообщений не найдено.")
        return

    print(f"Found {len(messages)} messages to forward.")
    await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=f"Найдено {len(messages)} сообщений для пересылки.")
    
    # Sort messages by date
    messages.sort(key=lambda x: x['date'])

    for message in messages:
        await send_message_to_telegram(bot, message)
        print("Waiting for 10 seconds before sending the next message...")
        await asyncio.sleep(10)

    print("Finished forwarding all messages.")
    await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text="Пересылка всех сообщений завершена.")

async def sync_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /sync command."""
    await update.message.reply_text("Начинаю синхронизацию сообщений из TikTok...")
    await sync_messages(context)

async def send_message_to_telegram(bot, message):
    """Sends a text or video message to Telegram."""
    try:
        if message['type'] == 'text':
            print(f"Sending text: {message['content']}")
            await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=message['content'])
        elif message['type'] == 'video':
            video_url = message['content']
            # Use a temporary directory for video files
            video_path = os.path.join('temp_videos', f"temp_video_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp4")
            
            print(f"Processing video: {video_url}")
            download_success = await tiktok_handler.download_video(video_url, video_path)
            
            if download_success:
                print(f"Sending video: {video_path}")
                with open(video_path, 'rb') as video_file:
                    await bot.send_video(chat_id=config.TELEGRAM_CHAT_ID, video=video_file)
                
                # Clean up the downloaded file
                if os.path.exists(video_path):
                    os.remove(video_path)
                    print(f"Removed temporary file: {video_path}")
            else:
                await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=f"Не удалось скачать видео: {video_url}")

    except Exception as e:
        print(f"Failed to send message: {e}")

def main():
    """Main function to run the bot."""
    # Create a directory for temporary video files if it doesn't exist
    if not os.path.exists('temp_videos'):
        os.makedirs('temp_videos')

    # Initialize Telegram bot
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("sync", sync_command_handler))

    print("Bot is running... Use /start to get chat ID and /sync to fetch messages.")
    
    # Run the bot until you press Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()