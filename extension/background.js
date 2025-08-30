
// Listen for web requests
chrome.webRequest.onCompleted.addListener(
  (details) => {
    // The URL of the request we want to intercept
    const targetUrl = "https://www.tiktok.com/api/im/item_detail/";

    if (details.url.startsWith(targetUrl) && details.statusCode === 200) {
      console.log("Intercepted TikTok API request:", details.url);

      // Fetch the content of the URL that was just requested by the page
      fetch(details.url)
        .then(response => {
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          return response.json();
        })
        .then(data => {
          console.log("Successfully fetched and parsed data:", data);
          
          // Extract the required information from the JSON
          const uniqueId = data?.itemInfo?.itemStruct?.author?.uniqueId;
          const videoId = data?.itemInfo?.itemStruct?.id;

          if (uniqueId && videoId) {
            const tiktokUrl = `https://www.tiktok.com/@${uniqueId}/video/${videoId}`;
            console.log("Constructed URL:", tiktokUrl);

            // Send the URL to the local Python server
            fetch("http://127.0.0.1:5000/send_url", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({ url: tiktokUrl }),
            })
            .then(response => response.json())
            .then(serverData => console.log("Sent URL to bot:", serverData))
            .catch(error => console.error("Error sending URL to bot:", error));

          } else {
            console.log("Could not find uniqueId or videoId in the response.");
          }
        })
        .catch(error => {
          console.error("Error fetching or parsing intercepted request:", error);
        });
    }
  },
  // Filter for the requests we are interested in
  { urls: ["https://*.tiktok.com/api/im/item_detail/*"] }
);

// A simple state for the popup to query
let state = {
  isReady: true, // Indicates the background script is running
};

// Listener for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getState') {
    sendResponse(state);
  }
  return true; // Keep channel open for async response
});

