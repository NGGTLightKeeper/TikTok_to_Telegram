// Copyright NGGT.LightKeeper. All Rights Reserved.

/**
 * This script runs when the extension's popup is opened.
 * It sends a message to the background service worker to check its status
 * and updates the UI accordingly.
 */
document.addEventListener('DOMContentLoaded', () => {
  const statusIndicator = document.getElementById('status-indicator');
  const statusText = document.getElementById('status-text');

  // Send a message to the background script to get its state.
  chrome.runtime.sendMessage({ action: 'getState' }, (response) => {
    // The background script will respond if it's active.
    if (chrome.runtime.lastError) {
      // An error indicates the background script is inactive or couldn't respond.
      console.error('Error communicating with background script:', chrome.runtime.lastError.message);
      statusIndicator.classList.remove('active');
      statusIndicator.classList.add('inactive'); // You would need to define an 'inactive' style.
      statusText.textContent = 'Inactive';
    } else if (response && response.isReady) {
      // A successful response means the script is running.
      console.log('Background script is active.');
      statusIndicator.classList.add('active');
      statusText.textContent = 'Active';
    } else {
      // Handle unexpected responses.
      statusIndicator.classList.remove('active');
      statusIndicator.classList.add('inactive');
      statusText.textContent = 'Error';
    }
  });
});
