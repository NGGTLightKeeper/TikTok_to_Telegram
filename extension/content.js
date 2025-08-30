let scrapingInterval;
let collectedMessages = [];
let knownMessageIds = new Set();

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "startScraping") {
        console.log("Starting to scrape...");
        collectedMessages = [];
        knownMessageIds = new Set();
        startScrolling();
    } else if (request.action === "stopScraping") {
        console.log("Stopping scrape.");
        stopScrolling();
    } else if (request.action === "saveData") {
        console.log("Saving data...");
        downloadJson(collectedMessages);
    }
});

function startScrolling() {
    if (scrapingInterval) clearInterval(scrapingInterval);
    scrapingInterval = setInterval(scrapeAndScroll, 3000); // every 3 seconds
}

function stopScrolling() {
    clearInterval(scrapingInterval);
    // Update state in background script
    chrome.runtime.sendMessage({
        action: "setState",
        state: { isScraping: false, messageCount: collectedMessages.length }
    });
}

function scrapeAndScroll() {
    const messageContainer = document.querySelector('div[class*="DivMessageListContainer"]');
    if (!messageContainer) {
        console.error("Message container not found.");
        stopScrolling();
        return;
    }

    // This is a placeholder selector. It needs to be updated with the actual one from TikTok.
    const messages = messageContainer.querySelectorAll('div[class*="DivMessageContent"]');
    
    let newMessagesFound = false;
    messages.forEach(msg => {
        // This is a placeholder for a unique message ID. Needs to be adapted.
        const messageId = msg.textContent.slice(0, 50) + (msg.querySelector('img')?.src || '');

        if (!knownMessageIds.has(messageId)) {
            newMessagesFound = true;
            knownMessageIds.add(messageId);

            let messageData = {
                type: 'text',
                content: msg.textContent,
                author: 'unknown', // Placeholder
                timestamp: new Date().toISOString() // Placeholder
            };

            // Check for video
            const videoElement = msg.querySelector('video');
            if (videoElement) {
                messageData.type = 'video';
                messageData.content = videoElement.src;
            }
            
            // Check for author - Placeholder selector
            const authorElement = msg.closest('div[class*="DivMessageItem"]').querySelector('span[class*="SpanUserName"]');
            if(authorElement) {
                messageData.author = authorElement.textContent;
            }

            collectedMessages.unshift(messageData); // Add to the beginning
        }
    });

    // Update count in popup
    chrome.runtime.sendMessage({ action: "updateCount", count: collectedMessages.length });

    // Scroll up
    messageContainer.scrollTop = 0;

    // If no new messages are found for a while, maybe stop.
    // This logic can be improved.
    if (!newMessagesFound) {
        console.log("No new messages found. Stopping.");
        // stopScrolling(); // Optional: auto-stop
    }
}

function downloadJson(data) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    
    // Generate filename
    const usernameElement = document.querySelector('span[class*="Username"]'); // Placeholder selector
    const username = usernameElement ? usernameElement.textContent : 'chat';
    const date = new Date().toISOString().split('T')[0];
    a.download = `tiktok_${username}_${date}.json`;

    a.href = url;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
