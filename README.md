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
5.  The user interacts with the Telegram bot, first using `/start` in a chat to set it as the target.
6.  When the user sends the `/send` command, the bot reads the URL queue, downloads each video, sends it to the target chat, and archives the processed links.

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

### 1. Backend Setup

1.  Clone this repository to your local machine.
2.  Install the required Python libraries as listed above.
3.  Open a terminal in the project's root directory and run the server:
    ```bash
    python main.py runserver
    ```
    This will start both the Flask URL collector and the Telegram bot.

### 2. Browser Extension Setup

1.  Open your Chromium-based browser and navigate to the extensions page (e.g., `chrome://extensions`).
2.  Enable "Developer mode".
3.  Click "Load unpacked" and select the `extension` folder from this repository.
4.  The extension will be installed and will start listening for links automatically.

### 3. Bot Configuration and Usage

1.  Open your Telegram client and find the bot you created with [@BotFather](https://t.me/BotFather/).
2.  In the chat where you want to receive videos, send the `/start` command. The bot will register that chat as the destination.
3.  Open a TikTok chat with the desired user. Scroll through the chat to the desired moment, the extension will automatically save messages.
4.  When you are ready, go back to the target chat in Telegram and send the `/send` command. The bot will begin downloading and sending the collected videos.

## License
This project is licensed under the [MIT License](LICENSE.md).
