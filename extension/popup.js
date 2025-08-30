document.addEventListener('DOMContentLoaded', () => {
  const statusText = document.getElementById('status-text');
  const statusIndicator = document.getElementById('status-indicator');

  // Set the status to active, as the background script is always running
  statusText.textContent = 'Active';
  statusIndicator.className = 'active';
});
