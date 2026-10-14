// Copyright NGGT.LightKeeper. All Rights Reserved.

// Cache and deduplication settings
const CACHE_KEY = 'sentUrlsCache';
const CACHE_MAX_SIZE = 5000; // Maximum number of API URLs to keep in the cache.

// Retrieve the in-storage deduplication cache or create an empty initial state.
async function getCache() {
  const result = await chrome.storage.local.get(CACHE_KEY);
  // Initialize with a default structure if the cache doesn't exist.
  return result[CACHE_KEY] || { queue: [], set: {} };
}

// Persist the deduplication cache object to extension local storage.
async function setCache(cache) {
  await chrome.storage.local.set({ [CACHE_KEY]: cache });
}

// Check for duplicate URLs and maintain a bounded FIFO cache in extension storage.
async function isDuplicateAndUpdateCache(url) {
  const cache = await getCache();

  // Fast O(1) existence check against set.
  if (cache.set[url]) {
    console.log("Duplicate API URL detected in cache, skipping:", url);
    return true;
  }

  // Append new URL to queue and membership set.
  cache.queue.push(url);
  cache.set[url] = true;

  // Evict oldest entry when cache limit is exceeded.
  if (cache.queue.length > CACHE_MAX_SIZE) {
    const oldestUrl = cache.queue.shift(); // Evict oldest item from queue.
    delete cache.set[oldestUrl]; // Evict item from set.
  }

  await setCache(cache);
  console.log("New unique API URL added to cache:", url);
  return false;
}

// Page reload cache cleanup (disabled)
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

// API endpoints
const ITEM_DETAIL_URL = "https://www.tiktok.com/api/im/item_detail/";

// Network request interception
chrome.webRequest.onCompleted.addListener(
  (details) => {
    // Use an immediately-invoked async function to handle all operations.
    (async () => {
      try {
        // Intercept item detail requests and dispatch extracted items to server.
        if (details.url.startsWith(ITEM_DETAIL_URL) && details.statusCode === 200) {
          console.log("Intercepted item detail API request:", details.url);

          // For item details, the URL itself is unique enough for de-duplication.
          const isDuplicate = await isDuplicateAndUpdateCache(details.url);
          if (isDuplicate) return;

          // Retrieve and parse intercepted TikTok API response.
          const response = await fetch(details.url);
          if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
          const data = await response.json();

          // Extract author uniqueId, video item ID, and determine post type.
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

// Send parsed item payload to the local Python collector server.
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

// Extension message handling
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Respond to popup health check requests.
  if (request.action === 'getState') {
    sendResponse({ isReady: true });
    return true; // Keep the message channel open for the asynchronous response.
  }

  // Forward chat text messages from content script to backend.
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
