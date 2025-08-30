// --- De-duplication Cache using chrome.storage ---

const CACHE_KEY = 'sentUrlsCache';
const CACHE_MAX_SIZE = 5000; // Keep a reasonable limit

// Function to get the cache from storage
async function getCache() {
  const result = await chrome.storage.local.get(CACHE_KEY);
  // Ensure we have a consistent structure
  return result[CACHE_KEY] || { queue: [], set: {} };
}

// Function to save the cache to storage
async function setCache(cache) {
  await chrome.storage.local.set({ [CACHE_KEY]: cache });
}

// Check for duplicates and update the cache
async function isDuplicateAndUpdateCache(url) {
  const cache = await getCache();

  if (cache.set[url]) {
    console.log("Duplicate URL detected, skipping:", url);
    return true; // It's a duplicate
  }

  // It's a new URL, add it to the cache
  cache.queue.push(url);
  cache.set[url] = true;

  // Trim the cache if it exceeds the max size
  if (cache.queue.length > CACHE_MAX_SIZE) {
    const oldestUrl = cache.queue.shift();
    delete cache.set[oldestUrl];
  }

  await setCache(cache);
  console.log("New unique URL added to cache:", url);
  return false; // It was not a duplicate
}


// --- Listener to clear cache on page reload ---

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  // Check if a TikTok tab is starting to load
  if (changeInfo.status === 'loading' && tab.url && tab.url.includes('tiktok.com')) {
    console.log('TikTok page is reloading. Clearing URL cache.');
    chrome.storage.local.remove(CACHE_KEY, () => {
      console.log('Cache cleared.');
    });
  }
});


// --- Main Logic: Listen for web requests ---

chrome.webRequest.onCompleted.addListener(
  (details) => {
    const targetUrl = "https://www.tiktok.com/api/im/item_detail/";

    if (details.url.startsWith(targetUrl) && details.statusCode === 200) {
      console.log("Intercepted TikTok API request:", details.url);

      // We need to wrap the main logic in an async function to use await
      (async () => {
        try {
          // --- De-duplication Check ---
          const isDuplicate = await isDuplicateAndUpdateCache(details.url);
          if (isDuplicate) {
            return; // Stop processing if it's a duplicate API call URL
          }

          const response = await fetch(details.url);
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          const data = await response.json();
          console.log("Successfully fetched and parsed data:", data);

          const uniqueId = data?.itemInfo?.itemStruct?.author?.uniqueId;
          const videoId = data?.itemInfo?.itemStruct?.id;

          if (uniqueId && videoId) {
            const tiktokUrl = `https://www.tiktok.com/@${uniqueId}/video/${videoId}`;
            console.log("Constructed unique URL:", tiktokUrl);

            // Send the URL to the local Python server
            const serverResponse = await fetch("http://127.0.0.1:5000/send_url", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ url: tiktokUrl }),
            });
            const serverData = await serverResponse.json();
            console.log("Sent URL to bot:", serverData);

          } else {
            console.log("Could not find uniqueId or videoId in the response.");
          }
        } catch (error) {
          console.error("Error processing intercepted request:", error);
        }
      })(); // Immediately invoke the async function
    }
  },
  { urls: ["https://*.tiktok.com/api/im/item_detail/*"] }
);


// --- Popup Communication ---
// This is just to let the popup know the extension is active.
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getState') {
    sendResponse({ isReady: true });
  }
  return true; // Keep channel open for async response
});