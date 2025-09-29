// Copyright NGGT.LightKeeper. All Rights Reserved.

// --- Caching Mechanism for De-duplication ---

const CACHE_KEY = 'sentUrlsCache';
const CACHE_MAX_SIZE = 5000; // The maximum number of API URLs to keep in the cache.

/**
 * Retrieves the cache from chrome.storage.local.
 * The cache uses both a queue (for size management) and a set (for fast lookups).
 * @returns {Promise<{queue: string[], set: {[key: string]: boolean}}>} The cache object.
 */
async function getCache() {
  const result = await chrome.storage.local.get(CACHE_KEY);
  // Initialize with a default structure if the cache doesn't exist.
  return result[CACHE_KEY] || { queue: [], set: {} };
}

/**
 * Saves the cache object back to chrome.storage.local.
 * @param {{queue: string[], set: {[key: string]: boolean}}} cache The cache object to save.
 */
async function setCache(cache) {
  await chrome.storage.local.set({ [CACHE_KEY]: cache });
}

/**
 * Checks if a URL is a duplicate. If not, it adds the URL to the cache.
 * This prevents sending the same API request to the backend multiple times.
 * The cache is trimmed to CACHE_MAX_SIZE to prevent it from growing indefinitely.
 * @param {string} url The API URL to check.
 * @returns {Promise<boolean>} True if the URL was a duplicate, false otherwise.
 */
async function isDuplicateAndUpdateCache(url) {
  const cache = await getCache();

  // Use the 'set' for a fast O(1) lookup.
  if (cache.set[url]) {
    console.log("Duplicate API URL detected in cache, skipping:", url);
    return true;
  }

  // If it's a new URL, add it to both the queue and the set.
  cache.queue.push(url);
  cache.set[url] = true;

  // If the cache exceeds the max size, remove the oldest item.
  if (cache.queue.length > CACHE_MAX_SIZE) {
    const oldestUrl = cache.queue.shift(); // Remove from the front of the queue.
    delete cache.set[oldestUrl];      // Remove from the set.
  }

  await setCache(cache);
  console.log("New unique API URL added to cache:", url);
  return false;
}

// --- Listener to Clear Cache on Page Reload ---

// NOTE: This functionality is currently disabled because the primary interception target
// is the API call, not URLs that appear on the page. Reloading the page does not
// necessarily mean we want to re-process all API calls. If the goal was to scrape
// visible links, this would be more useful. It is kept here for potential future use.
/*
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'loading' && tab.url && tab.url.includes('tiktok.com')) {
    console.log('TikTok page is reloading. Clearing URL cache.');
    chrome.storage.local.remove(CACHE_KEY, () => {
      console.log('Cache cleared.');
    });
  }
});
*/

// --- API Endpoints ---
const ITEM_DETAIL_URL = "https://www.tiktok.com/api/im/item_detail/";

// --- Main Logic: Intercept TikTok API Requests ---

chrome.webRequest.onCompleted.addListener(
  (details) => {
    // Use an immediately-invoked async function to handle all operations.
    (async () => {
      try {
        // --- Handler for Video/Photo Items ---
        if (details.url.startsWith(ITEM_DETAIL_URL) && details.statusCode === 200) {
          console.log("Intercepted item detail API request:", details.url);

          // For item details, the URL itself is unique enough for de-duplication.
          const isDuplicate = await isDuplicateAndUpdateCache(details.url);
          if (isDuplicate) return;

          const response = await fetch(details.url);
          if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
          const data = await response.json();

          const itemStruct = data?.itemInfo?.itemStruct;
          const uniqueId = itemStruct?.author?.uniqueId;
          const videoId = itemStruct?.id;

          if (uniqueId && videoId) {
            const tiktokUrl = `https://www.tiktok.com/@${uniqueId}/video/${videoId}`;
            const isPhoto = itemStruct.imagePost && itemStruct.imagePost.images.length > 0;
            const itemType = isPhoto ? 'photo_video' : 'video';
            const payload = {
              type: itemType,
              itemId: videoId,
              url: tiktokUrl,
              apiResponse: data,
            };
            
            console.log(`Sending item of type '${itemType}' to server:`, payload);
            await sendToServer(payload);
          } else {
            console.warn("Could not find uniqueId or videoId in API response.", data);
          }
        }
      } catch (error) {
        console.error("Error processing intercepted request:", error);
      }
    })();
  },
  // Filter for all the URL patterns we want to intercept.
  { urls: [ `${ITEM_DETAIL_URL}*` ] }
);

/**
 * Sends a data payload to the local Python server.
 * @param {object} payload The data to send.
 */
async function sendToServer(payload) {
    const serverResponse = await fetch("http://127.0.0.1:5000/send_item", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!serverResponse.ok) {
        throw new Error(`Server responded with status: ${serverResponse.status}`);
    }

    const serverData = await serverResponse.json();
    console.log("Server response:", serverData);
}

// --- Communication from Content & Popup Scripts ---
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Handle state check from popup
  if (request.action === 'getState') {
    sendResponse({ isReady: true });
    return true; // Keep the message channel open for the asynchronous response.
  }

  // Handle new text message from content script
  if (request.action === 'text_message') {
    (async () => {
      try {
        const { author, text } = request.data;
        // Generate a unique ID for the message to allow for de-duplication.
        // A combination of timestamp and text content is reasonably unique.
        const messageId = `msg_${Date.now()}_${text.slice(0, 20)}`;

        const isDuplicate = await isDuplicateAndUpdateCache(messageId);
        if (isDuplicate) {
          sendResponse({ status: 'duplicate' });
          return;
        }

        const payload = {
          type: 'message',
          itemId: messageId,
          author: author,
          text: text,
        };

        console.log(`Sending item of type 'message' from content script to server:`, payload);
        await sendToServer(payload);
        sendResponse({ status: 'success' });
      } catch (error) {
        console.error('Error handling text message from content script:', error);
        sendResponse({ status: 'error', message: error.message });
      }
    })();

    return true; // Indicate that sendResponse will be called asynchronously.
  }
});
