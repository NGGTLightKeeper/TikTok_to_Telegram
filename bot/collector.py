# Copyright NGGT.LightKeeper. All Rights Reserved.

import os
import json
import logging
import threading
from collections import deque
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- Basic Setup ---
# The logger is configured in 'main.py' to ensure a consistent format.
logger = logging.getLogger(__name__)

# --- Globals & Constants ---
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing for all routes.

# Define the absolute path for the JSON file that stores collected URLs.
JSON_FILE_PATH = os.path.join(os.path.dirname(__file__), 'urls_to_send.json')

# A lock to prevent race conditions when multiple requests try to write to the file simultaneously.
FILE_LOCK = threading.Lock()

# Use a deque as a memory-efficient, fixed-size cache to quickly check for recent URLs.
# This avoids repeatedly reading the JSON file for de-duplication.
RECENTLY_PROCESSED_URLS = deque(maxlen=10000)


def load_existing_urls():
    """
    Load URLs from the JSON file into the de-duplication cache at startup.
    This pre-fills the cache to prevent adding duplicates that already exist on disk.
    """
    with FILE_LOCK:
        if not os.path.exists(JSON_FILE_PATH):
            logger.info(f"'{JSON_FILE_PATH}' not found. Starting with an empty cache.")
            return
        try:
            with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                urls = json.load(f)
                count = 0
                # Populate the deque with URLs from the file.
                for url in urls:
                    if url not in RECENTLY_PROCESSED_URLS:
                        RECENTLY_PROCESSED_URLS.append(url)
                        count += 1
                logger.info(f"Loaded {count} unique URLs from '{JSON_FILE_PATH}' into the cache.")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Could not read or parse '{JSON_FILE_PATH}': {e}")


@app.route('/send_url', methods=['POST'])
def receive_url():
    """
    API endpoint to receive a URL, de-duplicate it, and save it to the JSON file.
    This is called by the browser extension.
    """
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            raise ValueError("Invalid JSON or no 'url' key provided in the request.")
        
        url = data['url']

        # --- De-duplication Check ---
        # First, check the in-memory cache for the URL. This is very fast.
        if url in RECENTLY_PROCESSED_URLS:
            logger.info(f"Duplicate URL detected in cache, skipping: {url}")
            return jsonify({"status": "success", "message": "Duplicate URL, skipped."})
        
        # If not in the cache, add it immediately to prevent processing simultaneous requests for the same URL.
        RECENTLY_PROCESSED_URLS.append(url)
        
        # --- Thread-Safe File Writing ---
        with FILE_LOCK:
            all_urls = []
            # Read the existing URLs from the file.
            if os.path.exists(JSON_FILE_PATH):
                with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                    try:
                        all_urls = json.load(f)
                    except json.JSONDecodeError:
                        # If the file is corrupted or empty, start with a fresh list.
                        logger.warning(f"'{JSON_FILE_PATH}' was corrupted or empty. Starting fresh.")
            
            # Although we checked the cache, we perform a final check on the list read from the file.
            # This handles the rare case where a URL was written by another thread after the cache check.
            if url not in all_urls:
                all_urls.append(url)
                # Write the updated list back to the file.
                with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(all_urls, f, indent=4)
                logger.info(f"Successfully saved new URL. Total URLs: {len(all_urls)}")
            else:
                logger.info(f"Duplicate URL detected in file, skipping: {url}")

        return jsonify({"status": "success", "message": "URL processed."})

    except Exception as e:
        logger.error(f"An error occurred in /send_url: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 400


def main():
    """Main function to start the Flask server for URL collection."""
    load_existing_urls()  # Pre-fill the cache with existing URLs.
    logger.info("Starting Flask server for URL collection on http://127.0.0.1:5000")
    # The server runs indefinitely, listening for requests from the extension.
    app.run(host='127.0.0.1', port=5000)

if __name__ == '__main__':
    main()
