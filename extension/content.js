// Copyright NGGT.LightKeeper. All Rights Reserved.

console.log("TT2TG Content Script Loaded.");

// --- Configuration ---
const CHAT_CONTAINER_SELECTOR = '[class*="DivChatMain"]'; // The scrollable container for all messages.
const MESSAGE_NODE_SELECTOR = '[data-e2e="chat-item"]'; // The direct child element added for each new message.
const TEXT_SELECTOR = 'p[class*="--PText"]'; // The element containing the message text.
const PARTNER_NAME_SELECTOR = '[data-e2e="chat-nickname"]'; // The element containing the chat partner's name in the header.
const OWN_MESSAGE_SELECTOR = 'div[class*="ma4lvt"]'; // A selector to identify our own messages to ignore them.


const PROCESSED_ATTRIBUTE = 'data-tt2tg-processed'; // Attribute to mark processed messages.
let chatPartnerName = null; // Will be populated once the chat is found.

/**
 * Finds the main chat container element on the page.
 * Retries a few times in case the script loads before the chat is rendered.
 * @returns {Promise<Element>} A promise that resolves with the chat container element.
 */
function findChatContainer() {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const maxAttempts = 10;
    const interval = setInterval(() => {
      const container = document.querySelector(CHAT_CONTAINER_SELECTOR);
      const partnerNameEl = document.querySelector(PARTNER_NAME_SELECTOR);

      if (container && partnerNameEl) {
        chatPartnerName = partnerNameEl.textContent.trim();
        clearInterval(interval);
        console.log("TT2TG: Chat container and partner name found.", container, chatPartnerName);
        resolve(container);
      } else {
        attempts++;
        if (attempts >= maxAttempts) {
          clearInterval(interval);
          const errorMsg = "Could not find chat container or partner name after multiple attempts.";
          console.error(`TT2TG: ${errorMsg} Selectors:`, CHAT_CONTAINER_SELECTOR, PARTNER_NAME_SELECTOR);
          reject(new Error(errorMsg));
        }
      }
    }, 1000); // Check every second.
  });
}

/**
 * Processes a single message node to extract author and text.
 * It sends the data to the background script.
 * @param {Node} node The HTML element of the message.
 */
function processMessageNode(node) {
  // Ensure it's an element node and hasn't been processed yet.
  if (node.nodeType !== Node.ELEMENT_NODE || node.hasAttribute(PROCESSED_ATTRIBUTE)) {
    return;
  }

  // Ignore our own messages.
  if (node.querySelector(OWN_MESSAGE_SELECTOR)) {
    node.setAttribute(PROCESSED_ATTRIBUTE, 'true'); // Mark as processed to avoid re-checking
    return;
  }

  // Mark as processed immediately to prevent race conditions.
  node.setAttribute(PROCESSED_ATTRIBUTE, 'true');

  const textEl = node.querySelector(TEXT_SELECTOR);
  const author = chatPartnerName; // Use the name from the header.

  if (author && textEl) {
    const text = textEl.textContent.trim();

    if (text) {
      console.log(`TT2TG: Extracted message - Author: ${author}, Text: ${text}`);

      // Send the extracted data to the background script.
      chrome.runtime.sendMessage(
        {
          action: 'text_message',
          data: { author, text },
        },
        (response) => {
          if (chrome.runtime.lastError) {
            console.error("TT2TG: Error sending message to background:", chrome.runtime.lastError.message);
          } else if (response && response.status === 'error') {
            console.error("TT2TG: Background script reported an error:", response.message);
          } else if (response) {
            console.log("TT2TG: Message sent to background script. Status:", response.status);
          }
        }
      );
    }
  }
}

/**
 * Sets up the MutationObserver to watch for new messages.
 * @param {Element} targetNode The chat container element to observe.
 */
function observeChat(targetNode) {
  const config = { childList: true, subtree: true };

  const callback = (mutationsList, observer) => {
    for (const mutation of mutationsList) {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType !== Node.ELEMENT_NODE) return;
          // Sometimes the added node is the message itself.
          if (node.matches(MESSAGE_NODE_SELECTOR)) {
            processMessageNode(node);
          }
          // Sometimes messages are nested inside a wrapper.
          else {
            node.querySelectorAll(MESSAGE_NODE_SELECTOR).forEach(processMessageNode);
          }
        });
      }
    }
  };

  const observer = new MutationObserver(callback);
  observer.observe(targetNode, config);

  console.log("TT2TG: MutationObserver is now watching the chat container.");

  // Also process any messages that already exist when the observer starts.
  targetNode.querySelectorAll(MESSAGE_NODE_SELECTOR).forEach(processMessageNode);
}


// --- Main Execution ---
// Start the process by finding the chat container and then observing it.
findChatContainer()
  .then(observeChat)
  .catch(error => console.error("TT2TG: Failed to initialize chat observer.", error));