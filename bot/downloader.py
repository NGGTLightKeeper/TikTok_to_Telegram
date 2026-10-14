# Copyright NGGT.LightKeeper. All Rights Reserved.

import os
import json
import logging
import time
import shutil
import requests
import yt_dlp
import config
from config import *

# Basic Setup
logger = logging.getLogger(__name__)

# Path Definitions
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BOT_DIR, '..'))
DOWNLOADS_DIR = os.path.join(PROJECT_ROOT, 'downloads')


def get_downloads_dir() -> str:
    """Ensures the root downloads directory exists and returns its absolute path."""
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    return DOWNLOADS_DIR


def sanitize_name(name: str) -> str:
    """Sanitizes directory and file names for OS filesystem compatibility."""
    if not name:
        return ""
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, '_')
    return name.strip()


def get_author_info(item: dict) -> tuple[str, str]:
    """
    Extracts author (uniqueId, id) from item's apiResponse.
    Falls back to URL parsing or empty strings.
    """
    api_response = item.get('apiResponse')
    if isinstance(api_response, dict):
        item_struct = api_response.get('itemInfo', {}).get('itemStruct', {})
        author = item_struct.get('author', {})
        unique_id = author.get('uniqueId')
        author_id = author.get('id')
        if unique_id or author_id:
            return str(unique_id or ''), str(author_id or '')

    # Fallback to URL parsing if uniqueId is in URL e.g. https://www.tiktok.com/@uniqueId/video/...
    url = item.get('url', '')
    if '@' in url:
        try:
            unique_id = url.split('@', 1)[1].split('/', 1)[0]
            return unique_id, ''
        except Exception:
            pass

    return '', ''


def get_author_directory(item: dict, base_dir: str = None) -> str:
    """
    Resolves the author directory under downloads folder.
    Format: "<uniqueId> <author_id>"
    Trusts author_id: if an author directory exists matching author_id but with an older uniqueId,
    it renames the directory to the new uniqueId to maintain up-to-date author metadata.
    """
    if base_dir is None:
        base_dir = get_downloads_dir()

    unique_id, author_id = get_author_info(item)
    unique_id = sanitize_name(unique_id)
    author_id = sanitize_name(author_id)

    if author_id:
        target_name = f"{unique_id} {author_id}".strip() if unique_id else author_id
        target_path = os.path.join(base_dir, target_name)

        if os.path.exists(base_dir):
            for entry in os.listdir(base_dir):
                entry_path = os.path.join(base_dir, entry)
                if os.path.isdir(entry_path):
                    parts = entry.rsplit(' ', 1)
                    # Check if entry matches author_id (either "<uniqueId> <author_id>" or just "<author_id>")
                    if entry == author_id or (len(parts) == 2 and parts[-1] == author_id):
                        if entry != target_name:
                            # Author uniqueId changed! Rename folder to keep current
                            try:
                                os.rename(entry_path, target_path)
                                logger.info(f"Updated author folder name: '{entry}' -> '{target_name}'")
                                return target_path
                            except Exception as e:
                                logger.error(f"Failed to rename author directory '{entry}' to '{target_name}': {e}")
                                return entry_path
                        return entry_path

        os.makedirs(target_path, exist_ok=True)
        return target_path

    if unique_id:
        target_path = os.path.join(base_dir, unique_id)
        os.makedirs(target_path, exist_ok=True)
        return target_path

    fallback_path = os.path.join(base_dir, "unknown_author")
    os.makedirs(fallback_path, exist_ok=True)
    return fallback_path


def get_target_dir(item: dict) -> str:
    """
    Returns the target directory for saving video.
    If DISABLE_VIDEO_DELETION, DISABLE_VIDEO_SENDING, and ORGANIZE_BY_AUTHOR are all True,
    saves into author-specific subfolders. Otherwise saves directly into root downloads folder.
    """
    base_dir = get_downloads_dir()
    if (getattr(config, 'DISABLE_VIDEO_DELETION', False) and
        getattr(config, 'DISABLE_VIDEO_SENDING', False) and
        getattr(config, 'ORGANIZE_BY_AUTHOR', False)):
        return get_author_directory(item, base_dir)
    return base_dir


def get_item_timestamp(item: dict) -> str:
    """
    Extracts publication timestamp from item's apiResponse.
    Falls back to itemId or current epoch timestamp.
    """
    api_response = item.get('apiResponse')
    if isinstance(api_response, dict):
        item_struct = api_response.get('itemInfo', {}).get('itemStruct', {})
        create_time = item_struct.get('createTime')
        if create_time:
            return str(create_time)

    item_id = item.get('itemId')
    if item_id:
        return str(item_id)

    return str(int(time.time()))


def download_video(item: dict) -> str:
    """
    Downloads video using yt-dlp to the project downloads directory.
    File is named after publication timestamp.
    Returns the absolute path to the downloaded video file, or None on failure.
    """
    url = item.get('url')
    if not url:
        logger.error(f"Video item is missing 'url'. Item: {item}")
        return None

    target_dir = get_target_dir(item)
    timestamp = get_item_timestamp(item)

    ydl_opts = {
        'outtmpl': os.path.join(target_dir, f'{timestamp}.%(ext)s'),
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info_dict)

        # Fallback check if extension was changed by yt-dlp during download/merge
        if not os.path.exists(video_path):
            base_path = os.path.splitext(video_path)[0]
            for ext in ['.mp4', '.mkv', '.webm', '.mov']:
                candidate = base_path + ext
                if os.path.exists(candidate):
                    video_path = candidate
                    break

        if not os.path.exists(video_path):
            logger.error(f"Downloaded video file not found at expected path: {video_path}")
            return None

        logger.info(f"Successfully downloaded video to '{video_path}'")
        return video_path

    except Exception as e:
        logger.error(f"Failed to download video from {url}: {e}", exc_info=True)
        raise


def cleanup_video(video_path: str, force: bool = False):
    """
    Removes the video file unless DISABLE_VIDEO_DELETION is enabled in config.
    """
    if not video_path:
        return

    if force or not getattr(config, 'DISABLE_VIDEO_DELETION', False):
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
                logger.debug(f"Removed temporary video file: {video_path}")
        except Exception as e:
            logger.warning(f"Failed to remove video file '{video_path}': {e}")
    else:
        logger.debug(f"Keeping downloaded video file: {video_path}")


def download_photos(item: dict) -> tuple[str, list[str]]:
    """
    Downloads photos for a 'photo_video' item into a temporary directory.
    Returns (temp_dir, list of downloaded image file paths).
    """
    item_id = item.get('itemId')
    api_response = item.get('apiResponse')

    if not all([item_id, api_response]):
        logger.error(f"Photo_video item {item_id} is missing 'itemId' or 'apiResponse'.")
        return None, []

    images = api_response.get('itemInfo', {}).get('itemStruct', {}).get('imagePost', {}).get('images', [])
    image_urls = [img.get('displayImage', {}).get('url_list', [None])[0] for img in images]
    image_urls = [u for u in image_urls if u]

    if not image_urls:
        logger.warning(f"No image URLs found for item {item_id}.")
        return None, []

    temp_dir = os.path.join(BOT_DIR, f'temp_images_{item_id}')
    os.makedirs(temp_dir, exist_ok=True)

    downloaded_paths = []
    for i, img_url in enumerate(image_urls):
        try:
            response = requests.get(img_url, stream=True, timeout=30)
            response.raise_for_status()

            file_path = os.path.join(temp_dir, f'image_{i}.jpg')
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            downloaded_paths.append(file_path)
        except requests.RequestException as e:
            logger.error(f"Failed to download image {i+1} for item {item_id} from {img_url}: {e}")
            continue

    if not downloaded_paths:
        logger.error(f"Failed to download any images for item {item_id}.")
        return temp_dir, []

    return temp_dir, downloaded_paths


def cleanup_photos(temp_dir: str):
    """Cleans up temporary directory created for photo downloads."""
    if temp_dir and os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary photo directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp photo directory '{temp_dir}': {e}")


def process_queue(queue_file: str = None) -> int:
    """
    Processes the queue file in standalone downloader mode.
    Downloads all video items according to current configuration.
    """
    if queue_file is None:
        queue_file = os.path.join(BOT_DIR, getattr(config, 'JSON_FILE_NAME', 'urls_to_send.json'))

    if not os.path.exists(queue_file):
        logger.info(f"Queue file '{queue_file}' does not exist.")
        return 0

    try:
        with open(queue_file, 'r', encoding='utf-8') as f:
            items = json.load(f)

        if not isinstance(items, list) or not items:
            logger.info("Item queue is empty.")
            return 0

        invert_order = getattr(config, 'INVERT_PROCESS_ORDER', False) or getattr(config, 'INVERT_SEND_ORDER', False)
        ordered_items = items if invert_order else list(reversed(items))

        processed_count = 0
        for item in ordered_items:
            item_type = item.get('type')
            if item_type == 'video' or isinstance(item, str):
                video_item = {'type': 'video', 'url': item} if isinstance(item, str) else item
                path = download_video(video_item)
                if path:
                    processed_count += 1

        logger.info(f"Standalone downloader finished: processed {processed_count}/{len(items)} items.")
        return processed_count

    except Exception as e:
        logger.error(f"Error processing queue file in standalone downloader: {e}", exc_info=True)
        return 0


if __name__ == '__main__':
    from log_config import setup_logging
    setup_logging()
    process_queue()
