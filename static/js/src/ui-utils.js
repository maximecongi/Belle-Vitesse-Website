/**
 * Shared UI Utility Functions
 * Centralizes common JS logic for the frontend (Signatures, Waivers, etc.)
 */

/**
 * Displays a feedback message in an element with id 'feedback'.
 * Standardizes the feedback UI across all signature and waiver pages.
 * 
 * @param {string} msg - The message text or HTML to display.
 * @param {string} type - The style type ('success', 'error', 'neutral').
 */
function showFeedback(msg, type) {
    var el = document.getElementById('feedback');
    if (!el) return;
    
    var processedMsg = msg || '';
    if (processedMsg.indexOf('✅') !== -1) {
        processedMsg = processedMsg.replace(/✅\s*/g, '<i data-lucide="circle-check-big"></i> ');
    }
    
    // Support both direct text and nested text element (for backward compatibility if needed)
    var txtEl = document.getElementById('feedback-text') || el;
    txtEl.innerHTML = processedMsg;
    
    // Standardize class naming and visibility
    el.className = 'feedback-box ' + (type || 'neutral');
    el.style.display = 'block';
    
    // Dynamically render Lucide icons if available
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
    
    // Remove individual coloring if it was set via JS before
    if (txtEl.style.color) {
        txtEl.style.color = '';
    }
    
    // Smooth scroll to the feedback if it's not fully visible
    if (typeof el.scrollIntoView === 'function') {
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

/**
 * Hides the feedback element.
 */
function hideFeedback() {
    var el = document.getElementById('feedback');
    if (el) {
        el.style.display = 'none';
    }
}
