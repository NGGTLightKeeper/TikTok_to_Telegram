# Copyright NGGT.LightKeeper. All Rights Reserved.

import os
import json
import logging
import threading
from collections import deque
from flask import Flask, request, jsonify
from flask_cors import CORS
from config import DD_CACHE_LEN, JSON_FILE_NAME

# --- Basic Setup ---
# The logger is configured in 'main.py' to ensure a consistent format.
logger = logging.getLogger(__name__)

# --- Globals & Constants ---
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing for all routes.

# Define the absolute path for the JSON file that stores collected URLs.
JSON_FILE_PATH = os.path.join(os.path.dirname(__file__), JSON_FILE_NAME)

# A lock to prevent race conditions when multiple requests try to write to the file simultaneously.
FILE_LOCK = threading.Lock()

# Use a deque as a memory-efficient, fixed-size cache to quickly check for recent item IDs.
# This avoids repeatedly reading the JSON file for de-duplication.
RECENTLY_PROCESSED_IDS = deque(maxlen=DD_CACHE_LEN)


def load_existing_items():
    """
    Load item IDs from the JSON file into the de-duplication cache at startup.
    This pre-fills the cache to prevent adding duplicates that already exist on disk.
    """
    with FILE_LOCK:
        if not os.path.exists(JSON_FILE_PATH):
            logger.info(f"'{JSON_FILE_PATH}' not found. Starting with an empty cache.")
            return
        try:
            with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                items = json.load(f)
                if not isinstance(items, list):
                    logger.warning(f"'{JSON_FILE_PATH}' does not contain a JSON list. Starting fresh.")
                    return

                count = 0
                for item in items:
                    # Check if the item is a dictionary and has the required 'itemId'
                    item_id = item.get('itemId') if isinstance(item, dict) else None
                    if item_id:
                        if item_id not in RECENTLY_PROCESSED_IDS:
                            RECENTLY_PROCESSED_IDS.append(item_id)
                            count += 1
                    else:
                        # Handle old format (plain URL strings) for backward compatibility
                        if isinstance(item, str) and item not in RECENTLY_PROCESSED_IDS:
                            RECENTLY_PROCESSED_IDS.append(item)
                            count += 1

                logger.info(f"Loaded {count} unique item IDs from '{JSON_FILE_PATH}' into the cache.")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Could not read or parse '{JSON_FILE_PATH}': {e}")


@app.route('/send_item', methods=['POST'])
def receive_item():
    """
    API endpoint to receive a data item, de-duplicate it by its 'itemId',
    and save it to the JSON file. This is called by the browser extension.
    """
    try:
        data = request.get_json()
        if not data or 'type' not in data or 'itemId' not in data:
            raise ValueError("Invalid JSON: 'type' and 'itemId' keys are required.")

        item_id = data['itemId']

        # --- De-duplication Check ---
        if item_id in RECENTLY_PROCESSED_IDS:
            logger.info(f"Duplicate item ID detected in cache, skipping: {item_id}")
            return jsonify({"status": "success", "message": "Duplicate item, skipped."})

        RECENTLY_PROCESSED_IDS.append(item_id)

        # --- Thread-Safe File Writing ---
        with FILE_LOCK:
            all_items = []
            if os.path.exists(JSON_FILE_PATH):
                try:
                    with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                        all_items = json.load(f)
                        # Ensure we are working with a list
                        if not isinstance(all_items, list):
                            logger.warning(f"'{JSON_FILE_PATH}' was not a list. Re-initializing.")
                            all_items = []
                except (json.JSONDecodeError, IOError):
                    logger.warning(f"'{JSON_FILE_PATH}' was corrupted or empty. Starting fresh.")
                    all_items = []

            # Final check on the list read from the file to handle race conditions.
            # We create a set of existing IDs for a fast lookup.
            existing_ids = {
                item.get('itemId') for item in all_items if isinstance(item, dict)
            }
            if item_id not in existing_ids:
                all_items.append(data)
                with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(all_items, f, indent=4)
                logger.info(f"Successfully saved new item ({data.get('type')}, ID: {item_id}). Total items: {len(all_items)}")
            else:
                logger.info(f"Duplicate item ID detected in file, skipping: {item_id}")

        return jsonify({"status": "success", "message": "Item processed."})

    except Exception as e:
        logger.error(f"An error occurred in /send_url: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 400


def main():
    """Main function to start the Flask server for item collection."""
    load_existing_items()  # Pre-fill the cache with existing item IDs.
    logger.info("Starting Flask server for item collection on http://127.0.0.1:5000")
    # The server runs indefinitely, listening for requests from the extension.
    app.run(host='127.0.0.1', port=5000)


if __name__ == '__main__':
    main()
