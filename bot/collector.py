# Copyright NGGT.LightKeeper. All Rights Reserved.

import os
import json
import logging
import threading
from collections import deque
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- Basic Setup ---
# Logging is configured in main.py
logger = logging.getLogger(__name__)

# --- Globals & Constants ---
app = Flask(__name__)
CORS(app) # Enable CORS for all routes

JSON_FILE_PATH = os.path.join(os.path.dirname(__file__), 'urls_to_send.json')
FILE_LOCK = threading.Lock() # Lock to prevent race conditions

# Use a deque for a memory-efficient, fixed-size cache of recent URLs
RECENTLY_PROCESSED_URLS = deque(maxlen=10000)


def load_existing_urls():
    """Load URLs from the JSON file into the de-duplication cache at startup."""
    with FILE_LOCK:
        if not os.path.exists(JSON_FILE_PATH):
            return
        try:
            with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                urls = json.load(f)
                count = 0
                for url in urls:
                    if url not in RECENTLY_PROCESSED_URLS:
                        RECENTLY_PROCESSED_URLS.append(url)
                        count += 1
                logger.info(f"Loaded {count} unique URLs from '{JSON_FILE_PATH}' into the cache.")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Could not read or parse '{JSON_FILE_PATH}': {e}")


@app.route('/send_url', methods=['POST'])
def receive_url():
    """Endpoint to receive a URL, de-duplicate it, and save it to a JSON file."""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            raise ValueError("Invalid JSON or no URL provided in the request.")
        
        url = data['url']

        # --- De-duplication Check ---
        if url in RECENTLY_PROCESSED_URLS:
            logger.info(f"Duplicate URL detected in cache, skipping: {url}")
            return jsonify({"status": "success", "message": "Duplicate URL, skipped."})
        
        # Add to in-memory cache immediately
        RECENTLY_PROCESSED_URLS.append(url)
        
        # --- Save to JSON file (with lock to prevent race conditions) ---
        with FILE_LOCK:
            all_urls = []
            if os.path.exists(JSON_FILE_PATH):
                with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                    try:
                        all_urls = json.load(f)
                    except json.JSONDecodeError:
                        logger.warning(f"'{JSON_FILE_PATH}' was corrupted or empty. Starting fresh.")
            
            if url not in all_urls:
                all_urls.append(url)
                with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(all_urls, f, indent=4)
                logger.info(f"Successfully saved new URL to '{JSON_FILE_PATH}'. Total URLs: {len(all_urls)}")
            else:
                # This case can happen if another thread wrote the URL while this one was waiting for the lock
                logger.info(f"Duplicate URL detected in file, skipping: {url}")


        return jsonify({"status": "success", "message": "URL processed."})

    except Exception as e:
        logger.error(f"Error in /send_url: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400


def main():
    """Main function to start the collector server."""
    load_existing_urls() # Pre-fill cache with any existing URLs
    logger.info("Starting Flask server for URL collection on http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000)

if __name__ == '__main__':
    main()
