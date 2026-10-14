# Copyright NGGT.LightKeeper. All Rights Reserved.

from __future__ import annotations

import json
import logging
import os
import threading
from collections import deque
from typing import Any

from flask import Flask, jsonify, request
from flask_cors import CORS

import config
from config import DD_CACHE_LEN, JSON_FILE_NAME

logger = logging.getLogger(__name__)


# Application initialization and shared state

app = Flask(__name__)
CORS(app)

JSON_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), JSON_FILE_NAME)
FILE_LOCK = threading.Lock()
RECENTLY_PROCESSED_IDS: deque[str] = deque(maxlen=DD_CACHE_LEN)


# Cache pre-warming

# Pre-fill deduplication cache with existing item IDs from the queue file on disk.
def load_existing_items() -> None:
    with FILE_LOCK:
        if not os.path.exists(JSON_FILE_PATH):
            logger.info(f"'{JSON_FILE_PATH}' not found. Starting with an empty cache.")
            return

        try:
            with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
                items = json.load(f)

            if not isinstance(items, list):
                logger.warning(f"'{JSON_FILE_PATH}' does not contain a JSON list. Starting fresh.")
                return

            count = 0
            for item in items:
                # Extract item ID from dictionary or legacy string entry.
                item_id = item.get("itemId") if isinstance(item, dict) else item if isinstance(item, str) else None
                if item_id and item_id not in RECENTLY_PROCESSED_IDS:
                    RECENTLY_PROCESSED_IDS.append(item_id)
                    count += 1

            logger.info(f"Loaded {count} unique item IDs from '{JSON_FILE_PATH}' into cache.")
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Could not read or parse '{JSON_FILE_PATH}': {e}")


# HTTP endpoints

# Receive incoming TikTok items from browser extension, deduplicate, and persist to queue file.
@app.route("/send_item", methods=["POST"])
def receive_item() -> tuple[Any, int] | Any:
    try:
        data = request.get_json()
        if not data or "type" not in data or "itemId" not in data:
            raise ValueError("Invalid JSON: 'type' and 'itemId' keys are required.")

        item_id = str(data["itemId"])

        # Check in-memory LRU cache to reject immediate duplicate requests.
        if item_id in RECENTLY_PROCESSED_IDS:
            logger.info(f"Duplicate item ID detected in cache, skipping: {item_id}")
            return jsonify({"status": "success", "message": "Duplicate item, skipped."})

        RECENTLY_PROCESSED_IDS.append(item_id)

        # Thread-safe write with file-level deduplication to prevent race conditions.
        with FILE_LOCK:
            all_items: list[dict[str, Any]] = []
            if os.path.exists(JSON_FILE_PATH):
                try:
                    with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, list):
                            all_items = loaded
                        else:
                            logger.warning(f"'{JSON_FILE_PATH}' was not a list. Re-initializing.")
                except (json.JSONDecodeError, OSError):
                    logger.warning(f"'{JSON_FILE_PATH}' was corrupted or empty. Starting fresh.")

            existing_ids = {
                item.get("itemId") for item in all_items if isinstance(item, dict)
            }
            if item_id not in existing_ids:
                all_items.append(data)
                with open(JSON_FILE_PATH, "w", encoding="utf-8") as f:
                    json.dump(all_items, f, indent=4)
                logger.info(
                    f"Successfully saved new item ({data.get('type')}, ID: {item_id}). "
                    f"Total items: {len(all_items)}"
                )
            else:
                logger.info(f"Duplicate item ID detected in file, skipping: {item_id}")

        return jsonify({"status": "success", "message": "Item processed."})

    except Exception as e:
        logger.error(f"An error occurred in /send_item: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 400


# Server entry point

# Start the Flask collector server on the local loopback interface.
def main() -> None:
    load_existing_items()
    logger.info("Starting Flask server for item collection on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000)


if __name__ == "__main__":
    main()
