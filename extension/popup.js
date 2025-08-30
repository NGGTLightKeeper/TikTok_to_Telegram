// Manages the state of the scraping process
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "updateState") {
        updateUI(request.state);
    }
    if (request.action === "updateCount") {
        const statusDiv = document.getElementById('status');
        statusDiv.textContent = `Status: Scraping... Found ${request.count} messages.`;
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const saveBtn = document.getElementById('saveBtn');

    // Get initial state from background script
    chrome.runtime.sendMessage({ action: "getState" }, (response) => {
        updateUI(response.state);
    });

    startBtn.addEventListener('click', () => {
        chrome.runtime.sendMessage({ action: "start" });
    });

    stopBtn.addEventListener('click', () => {
        chrome.runtime.sendMessage({ action: "stop" });
    });

    saveBtn.addEventListener('click', () => {
        chrome.runtime.sendMessage({ action: "save" });
    });
});

function updateUI(state) {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const saveBtn = document.getElementById('saveBtn');
    const statusDiv = document.getElementById('status');

    startBtn.disabled = state.isScraping;
    stopBtn.disabled = !state.isScraping;
    saveBtn.disabled = state.isScraping || state.messageCount === 0;

    let statusText = "Status: Idle";
    if (state.isScraping) {
        statusText = `Status: Scraping... Found ${state.messageCount} messages.`;
    } else if (state.messageCount > 0) {
        statusText = `Status: Stopped. Found ${state.messageCount} messages. Ready to save.`;
    }
    statusDiv.textContent = statusText;
}
