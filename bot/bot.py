
import telebot
import json
import os
import logging
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
from config import TELEGRAM_BOT_TOKEN

# --- Basic Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Globals & Constants ---
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
app = Flask(__name__)
CORS(app) # This will enable CORS for all routes

TARGET_CHAT_ID = None
CHAT_ID_FILE = 'chat_id.txt'

# --- Flask Web Server ---

@app.route('/send_url', methods=['POST'])
def receive_url():
    """Endpoint to receive a URL from the Chrome extension."""
    global TARGET_CHAT_ID
    if not TARGET_CHAT_ID:
        logger.warning("Received a URL but no target chat ID is set.")
        return jsonify({"status": "error", "message": "Target chat ID not set. Use /start in the Telegram bot."}), 500

    try:
        data = request.get_json()
        logger.info(f"Received data: {data}")
        url = data.get('url')
        if not url:
            raise ValueError("No URL provided in the request.")

        # Send the URL to the target Telegram chat
        bot.send_message(TARGET_CHAT_ID, url)
        logger.info(f"Successfully sent URL to chat {TARGET_CHAT_ID}: {url}")
        return jsonify({"status": "success", "message": "URL sent."})

    except Exception as e:
        logger.error(f"Error in /send_url: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

def run_flask_app():
    """Run the Flask app on port 5000."""
    # Using 0.0.0.0 to make it accessible from the network if needed,
    # though for local extension communication 127.0.0.1 is sufficient.
    app.run(host='0.0.0.0', port=5000)

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
                logger.error("Could not read chat ID from file. File might be corrupted.")

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
        "This chat has been set as the target for receiving TikTok links. "
        "The browser extension will now send links here."
    )

# --- Main Execution ---

def main():
    """Load initial data and start both Flask and Telebot."""
    load_chat_id()
    
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    logger.info("Flask server started in a background thread.")

    # Start the bot polling in the main thread
    logger.info("Telegram bot is starting...")
    bot.polling(non_stop=True)

if __name__ == '__main__':
    main()
