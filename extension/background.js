let state = {
    isScraping: false,
    messageCount: 0
};

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    switch (request.action) {
        case "start":
            startScraping(sender.tab);
            break;
        case "stop":
            stopScraping(sender.tab);
            break;
        case "save":
            saveData(sender.tab);
            break;
        case "getState":
            sendResponse({ state });
            break;
        case "setState":
            state = request.state;
            // Forward state update to popup
            chrome.runtime.sendMessage({ action: "updateState", state });
            break;
    }
    return true; // Indicates that the response is sent asynchronously
});

function startScraping(tab) {
    state.isScraping = true;
    state.messageCount = 0;
    chrome.tabs.sendMessage(tab.id, { action: "startScraping" });
    chrome.runtime.sendMessage({ action: "updateState", state });
}

function stopScraping(tab) {
    state.isScraping = false;
    chrome.tabs.sendMessage(tab.id, { action: "stopScraping" });
    chrome.runtime.sendMessage({ action: "updateState", state });
}

function saveData(tab) {
    chrome.tabs.sendMessage(tab.id, { action: "saveData" });
}
