# TT2TG (TikTok to Telegram)

This repository contains the **TT2TG** project, a system designed to automatically intercept messages (text, video, photo-albums) from a selected TikTok chat and send the corresponding messages to a Telegram chat.

The project consists of two main components:
1.  A **Browser Extension** that runs in the background, detects API calls for TikTok messages, and sends the JSONs to a local server.
2.  A **Python Backend** that includes:
    *   A lightweight **Flask server** to receive and collect the JSONs from the extension.
    *   A **Telegram Bot** built with `pyTelegramBotAPI` that, upon command, downloads the videos from the collected JSON using `yt-dlp` and sends them to a designated chat.

## How It Works

1.  The browser extension is loaded into a Chromium-based browser (like Chrome, Edge, etc.).
2.  When the user in selected TikTok chat, the extension intercepts the underlying API call that contains the messages information.
3.  The extension constructs the JSON with API data and sends it to the local Flask server.
4.  The Flask server receives the JSON, checks for duplicates, and saves it to a JSON file queue.
5.  The user configures the bot by getting a chat ID via the `/start` command and setting it in a configuration file.
6.  When the user sends the `/send` command in the configured chat, the bot reads the URL queue, downloads each item, sends it to the chat, and archives the processed links.

## Requirements
*  Python 3.13
*  TelegramBotCore / Python libraries:
   -   [TelegramBotCore 2.2 (FULL)](https://github.com/NGGTLightKeeper/TelegramBotCore/releases/tag/TelegramBotCore_ver.2.2)
   -   `pyTelegramBotAPI`
   -   `Flask`
   -   `Flask-Cors`
   -   `yt-dlp`
*  A Chromium-based web browser (e.g., Google Chrome, Microsoft Edge)

You can install the required Python packages using pip:
```bash
pip install pyTelegramBotAPI Flask Flask-Cors yt-dlp
```

## Installation and Usage

### 1. Backend Setup & Configuration

1.  Clone this repository to your local machine.
2.  Install the required Python libraries as listed above.
3.  Create Telegram Bot with [@BotFather](https://t.me/BotFather/) and get Telegram Bot Token.
4.  Paste your token into the `TELEGRAM_BOT_TOKEN` variable (e.g., `TELEGRAM_BOT_TOKEN = "12345:your_token_here"`).
5.  You also need to set the `TARGET_CHAT_ID`. Leave it as `None` for now.
6.  Open a terminal in the project's root directory and run the server:
    ```bash
    python main.py runserver
    ```
    This will start both the Flask URL collector and the Telegram bot.
7.  Open your Telegram client, find your bot, and send it the `/start` command in the chat where you want to receive files.
8.  The bot will reply with your **Chat ID**. It will be a number (possibly negative). Copy this ID.
9.  Stop the server in your terminal (Ctrl+C).
10.  Go back to `bot/config.py` and paste the copied Chat ID into the `TARGET_CHAT_ID` variable (e.g., `TARGET_CHAT_ID = -100123456789`).
11.  Save the `config.py` file.

### 2. Browser Extension Setup

1.  Open your Chromium-based browser and navigate to the extensions page (e.g., `chrome://extensions`).
2.  Enable "Developer mode".
3.  Click "Load unpacked" and select the `extension` folder from this repository.
4.  The extension will be installed and will start listening for links automatically.

### 3. Usage

1.  **Start the Backend**: If it's not already running, start the server again:
    ```bash
    python main.py runserver
    ```
2.  Open a TikTok chat with the desired user. Scroll through the chat to the desired moment, the extension will automatically save messages.
3.  When you are ready, go back to the target chat in Telegram and send the `/send` command. The bot will begin downloading and sending the collected messages.

## License
This project is licensed under the [MIT License](LICENSE.md).
