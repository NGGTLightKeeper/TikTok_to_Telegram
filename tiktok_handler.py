# tiktok_handler.py
import asyncio
import aiohttp
from playwright.async_api import async_playwright
from datetime import datetime
import time
import os

async def get_tiktok_messages(session_id, target_username, from_date_str):
    """
    Uses Playwright to launch a browser, handles the cookie consent banner by looking for specific text,
    logs in with a session cookie, and scrapes messages.
    """
    print("Launching VISIBLE browser for debugging...")
    messages = []
    
    if not os.path.exists('debug'):
        os.makedirs('debug')

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
        
        await context.add_cookies([{
            'name': 'sessionid', 'value': session_id, 'domain': '.tiktok.com', 'path': '/',
            'httpOnly': True, 'secure': True, 'sameSite': 'Lax'
        }])

        page = await context.new_page()
        
        print("Navigating to TikTok homepage...")
        await page.goto('https://www.tiktok.com/', timeout=60000)

        # --- NEW: Handle Cookie Banner using TEXT selector ---
        print("Checking for cookie consent banner with text 'Разрешить все'...")
        try:
            # Use Playwright's text selector to find the button
            await page.get_by_role("button", name="Разрешить все").click(timeout=10000)
            print("Cookie banner accepted.")
            await page.wait_for_timeout(3000) # Wait for the banner to disappear
        except Exception:
            print("Cookie banner not found or already accepted, continuing...")

        # Now, navigate to the messages page
        print("Navigating to TikTok messages page...")
        try:
            await page.goto('https://www.tiktok.com/messages/', timeout=60000)
        except Exception as e:
            print(f"Failed to navigate to the messages page. Error: {e}")
            await page.screenshot(path='debug/navigation_error.png')
            await browser.close()
            return []

        # Wait for the chat list
        chat_list_selector = '[data-e2e="im-chat-list-container"]'
        try:
            print("Waiting for inbox to load...")
            await page.wait_for_selector(chat_list_selector, timeout=30000)
            print("Inbox loaded successfully.")
        except Exception as e:
            print(f"Failed to find the chat list after handling cookies.")
            await page.screenshot(path='debug/inbox_load_error.png')
            await browser.close()
            print("A screenshot 'debug/inbox_load_error.png' has been saved.")
            return []

        # Search and click chat
        print(f"Searching for chat with '{target_username}'...")
        try:
            user_chat_locator = page.locator('[data-e2e="im-chat-list-item"]').filter(has_text=target_username)
            await user_chat_locator.click(timeout=15000)
            print("Chat found and opened.")
        except Exception as e:
            print(f"Could not find or click on the chat for '{target_username}'.")
            await page.screenshot(path='debug/chat_find_error.png')
            await browser.close()
            return []

        # Scrape messages
        message_list_selector = '[data-e2e="im-message-list-container"]'
        await page.wait_for_selector(message_list_selector, timeout=15000)
        print("Scraping messages...")
        await page.wait_for_timeout(3000)

        message_elements = await page.locator('[data-e2e="im-message-item"]').all()
        print(f"Found {len(message_elements)} message items.")

        for el in message_elements:
            try:
                text = "".join(await el.locator('[data-e2e="im-message-content"]').all_inner_texts()).strip()
                if text: messages.append({"type": "text", "content": text, "date": datetime.now().isoformat() + "Z"})
            except Exception: pass
            try:
                if await el.locator('video').count() > 0:
                    video_url = await el.locator('video').get_attribute('src')
                    if video_url: messages.append({"type": "video", "content": video_url, "date": datetime.now().isoformat() + "Z"})
            except Exception: pass

        print("Closing browser.")
        await browser.close()
        
        print(f"Scraped {len(messages)} messages.")
        unique_messages = [dict(t) for t in {tuple(d.items()) for d in messages}]
        return unique_messages


async def download_video(url, path):
    """Downloads a video from a given URL asynchronously."""
    print(f"Downloading video from {url} to {path}...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                with open(path, 'wb') as f:
                    while True:
                        chunk = await response.content.read(1024)
                        if not chunk: break
                        f.write(chunk)
        print("Download complete.")
        return True
    except aiohttp.ClientError as e:
        print(f"Error downloading video: {e}")
        return False
