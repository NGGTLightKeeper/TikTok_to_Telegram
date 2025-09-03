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

// --- Main Logic: Intercept TikTok API Requests ---

chrome.webRequest.onCompleted.addListener(
  (details) => {
    // This is the specific API endpoint that returns video details when you share a video.
    const targetUrlPrefix = "https://www.tiktok.com/api/im/item_detail/";

    if (details.url.startsWith(targetUrlPrefix) && details.statusCode === 200) {
      console.log("Intercepted TikTok API request:", details.url);

      // Use an immediately-invoked async function to handle the asynchronous operations.
      (async () => {
        try {
          // First, check if we've already processed this exact API call.
          const isDuplicate = await isDuplicateAndUpdateCache(details.url);
          if (isDuplicate) {
            return; // Stop if it's a duplicate.
          }

          // Re-fetch the API response to get its content.
          // Note: Manifest V3 does not allow direct access to response bodies in webRequest listeners.
          const response = await fetch(details.url);
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          const data = await response.json();
          console.log("Successfully fetched and parsed API data:", data);

          // Extract the author's username and the video ID from the JSON response.
          const uniqueId = data?.itemInfo?.itemStruct?.author?.uniqueId;
          const videoId = data?.itemInfo?.itemStruct?.id;

          if (uniqueId && videoId) {
            // Construct the user-friendly TikTok video URL.
            const tiktokUrl = `https://www.tiktok.com/@${uniqueId}/video/${videoId}`;
            console.log("Constructed video URL:", tiktokUrl);

            // Send the constructed URL to the local Python server.
            const serverResponse = await fetch("http://127.0.0.1:5000/send_url", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ url: tiktokUrl }),
            });
            
            if (!serverResponse.ok) {
                throw new Error(`Server responded with status: ${serverResponse.status}`);
            }

            const serverData = await serverResponse.json();
            console.log("Server response:", serverData);

          } else {
            console.warn("Could not find uniqueId or videoId in the API response.", data);
          }
        } catch (error) {
          console.error("Error processing intercepted request:", error);
        }
      })();
    }
  },
  // Filter for the specific URL pattern we want to intercept.
  { urls: ["https://*.tiktok.com/api/im/item_detail/*"] }
);

// --- Popup Communication ---
// This listener allows the popup to check if the background script is active.
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getState') {
    sendResponse({ isReady: true });
  }
  // 'return true' is necessary to indicate that sendResponse will be called asynchronously.
  return true;
});
