# TT2TG (TikTok to Telegram)

This repository contains the **TT2TG** project, a system designed to automatically intercept messages (text, video, photo-albums) from a selected TikTok chat and send the corresponding messages to a Telegram chat, or save them locally.

The project consists of two main components:
1.  A **Browser Extension** that runs in the background, detects API calls for TikTok messages, and sends JSON payloads to a local server.
2.  A **Python Backend** that includes:
    *   A lightweight **Flask server** (`collector.py`) to receive and collect JSON payloads from the extension into a queue.
    *   A **Telegram Bot** (`bot.py`) built with `pyTelegramBotAPI` that, upon command, processes the queue, downloads media, and dispatches them to a designated chat.
    *   A **Media Downloader** (`downloader.py`) that handles downloading videos via `yt-dlp` to `downloads/`, timestamp-based naming, photo extraction, author folder organization, and standalone queue processing.

## How It Works

1.  The browser extension is loaded into a Chromium-based browser (like Chrome, Edge, etc.).
2.  When the user opens a selected TikTok chat, the extension intercepts API calls containing message details.
3.  The extension constructs a JSON payload and forwards it to the local Flask server.
4.  The Flask server validates the data, deduplicates requests, and appends items to a JSON file queue (`urls_to_send.json`).
5.  The user configures the bot by obtaining a chat ID via `/start` and setting it in `bot/config.py`.
6.  When the user sends the `/send` command in Telegram (or runs the standalone downloader), the queue is processed: media is downloaded to `downloads/` (named by publication timestamp), and depending on configuration, dispatched to Telegram or preserved locally.

## Requirements
*  Python 3.13
*  Python libraries from Core:
   -   You can install the bot's dependency libraries in the "CORE" directory automatically via install_core.bat/.sh file or do it manually via requirements_core.txt
*  A Chromium-based web browser (e.g., Google Chrome, Microsoft Edge)

## Installation and Usage

### 1. Backend Setup & Configuration

1.  Clone this repository to your local machine.
2.  Install the required Python libraries as listed above.
3.  Create Telegram Bot with [@BotFather](https://t.me/BotFather/) and get Telegram Bot Token.
4.  Paste your token into the `TELEGRAM_BOT_TOKEN` variable in `bot/config.py` (e.g., `TELEGRAM_BOT_TOKEN = "12345:your_token_here"`).
5.  Set `TARGET_CHAT_ID = None` initially.
6.  Open a terminal in the `bot` directory and run the server:
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

### 3. Configuration Options

All settings are managed in `bot/config.py`:

*   `DISABLE_ERROR_MESSAGES` *(default: `True`)*: Suppresses error messages in the Telegram chat during processing, sending only technical start/finish notifications and valid content. Eliminates delays on failed attempts since no API rate limits are consumed.
*   `DISABLE_VIDEO_DELETION` *(default: `False`)*: Keeps downloaded videos in the `downloads/` directory instead of deleting them after sending.
*   `DISABLE_VIDEO_SENDING` *(default: `False`)*: Disables sending videos to Telegram, operating purely as a local video downloader.
*   `ORGANIZE_BY_AUTHOR` *(default: `False`)*: When `DISABLE_VIDEO_DELETION` and `DISABLE_VIDEO_SENDING` are both enabled, groups downloaded videos into author folders named `<uniqueId> <id>` (e.g., `username 123456789012345678`). Automatically tracks the author's immutable numeric ID and renames the folder if their username changes.
*   `INVERT_PROCESS_ORDER` *(default: `False`)*: Inverts queue processing order from default reverse-chronological (newest first) to chronological (oldest first).
*   `ASE_DELAY_TIME` *(default: `10`)*: Delay in seconds between messages to avoid Telegram API rate limits (HTTP 429).

### 4. Usage

1.  **Start the Backend**:
    ```bash
    cd bot
    python main.py runserver
    ```
2.  **Collect Messages**: Open a TikTok chat with the desired user. Scroll through the chat to the desired moment; the extension will automatically intercept and queue messages.
3.  **Process Queue**:
    *   **Via Telegram Bot**: Send `/send` in your configured Telegram chat. The bot will download and dispatch the collected items according to your configuration.
    *   **Standalone Downloader**: To download queued videos locally without the Telegram bot, execute:
        ```bash
        cd bot
        python downloader.py
        ```
    Downloaded videos are saved into the root `downloads/` directory and named by their publication timestamp (`createTime`).

## License
This project is licensed under the [MIT License](LICENSE.md).
