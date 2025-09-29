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

# Define the absolute path for the JSON file that stores collected data.
JSON_FILE_PATH = os.path.join(os.path.dirname(__file__), 'collected_data.json')

# A lock to prevent race conditions when multiple requests try to write to the file simultaneously.
FILE_LOCK = threading.Lock()

# Use a deque as a memory-efficient, fixed-size cache to quickly check for recent unique identifiers.
# This avoids repeatedly reading the JSON file for de-duplication.
RECENTLY_PROCESSED_IDS = deque(maxlen=10000)


def get_item_id(item):
    """
    Extracts a unique identifier from a collected item for de-duplication purposes.
    - For videos, it's the URL.
    - For slideshows, it's the item ID.
    - For chat messages, we use the text content (less reliable, but best effort).
    """
    item_type = item.get('type')
    data = item.get('data', {})

    if item_type == 'video':
        return data.get('url')
    if item_type == 'slideshow':
        # Item ID is a more reliable unique identifier than a list of image URLs.
        return str(data.get('itemId'))
    if item_type == 'chat_message':
        # No reliable unique ID for messages, so we use the text.
        # This might not be perfect but prevents simple duplicates.
        return data.get('text')
    return None


def load_existing_ids():
    """
    Load unique IDs from the JSON file into the de-duplication cache at startup.
    This pre-fills the cache to prevent adding duplicates that already exist on disk.
    """
    with FILE_LOCK:
        if not os.path.exists(JSON_FILE_PATH):
            logger.info(f"'{JSON_FILE_PATH}' not found. Starting with an empty cache.")
            return
        try:
            with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                items = json.load(f)
                count = 0
                for item in items:
                    item_id = get_item_id(item)
                    if item_id and item_id not in RECENTLY_PROCESSED_IDS:
                        RECENTLY_PROCESSED_IDS.append(item_id)
                        count += 1
                logger.info(f"Loaded {count} unique item IDs from '{JSON_FILE_PATH}' into the cache.")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Could not read or parse '{JSON_FILE_PATH}': {e}")


@app.route('/collect_data', methods=['POST'])
def receive_data():
    """
    API endpoint to receive structured data (video, slideshow, chat message),
    de-duplicate it, and save it to the JSON file.
    """
    try:
        payload = request.get_json()
        if not payload or 'type' not in payload or 'data' not in payload:
            raise ValueError("Invalid JSON or missing 'type'/'data' keys.")
        
        item_id = get_item_id(payload)
        if not item_id:
            logger.warning(f"Could not determine a unique ID for item: {payload}")
            return jsonify({"status": "error", "message": "Item lacks a unique identifier."}), 400

        # --- De-duplication Check ---
        if item_id in RECENTLY_PROCESSED_IDS:
            logger.info(f"Duplicate item detected in cache, skipping: {item_id}")
            return jsonify({"status": "success", "message": "Duplicate item, skipped."})
        
        RECENTLY_PROCESSED_IDS.append(item_id)
        
        # --- Thread-Safe File Writing ---
        with FILE_LOCK:
            all_items = []
            if os.path.exists(JSON_FILE_PATH):
                with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                    try:
                        all_items = json.load(f)
                    except json.JSONDecodeError:
                        logger.warning(f"'{JSON_FILE_PATH}' was corrupted or empty. Starting fresh.")
            
            # Final check to ensure the ID is not already in the file.
            existing_ids = {get_item_id(item) for item in all_items if get_item_id(item)}
            if item_id not in existing_ids:
                all_items.append(payload)
                with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(all_items, f, indent=4)
                logger.info(f"Successfully saved new {payload.get('type')} item. Total items: {len(all_items)}")
            else:
                logger.info(f"Duplicate item detected in file, skipping: {item_id}")

        return jsonify({"status": "success", "message": "Item processed."})

    except Exception as e:
        logger.error(f"An error occurred in /collect_data: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 400


def main():
    """Main function to start the Flask server for data collection."""
    load_existing_ids()  # Pre-fill the cache with existing item IDs.
    logger.info("Starting Flask server for data collection on http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000)

if __name__ == '__main__':
    main()
