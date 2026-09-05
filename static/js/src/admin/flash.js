/**
 * flash.js — Gestion des messages flash et toasts d'administration.
 */

function dismissFlash(f) {
    if (!f || !f.parentNode) return;
    f.style.opacity = '0';
    f.style.transform = 'translateX(100%)';
    f.style.transition = 'all 0.5s ease';
    setTimeout(() => f.remove(), 500);
}

/**
 * Affiche dynamiquement un message flash (toast).
 * @param {string} message
 * @param {string} category (info, success, warning, error)
 */
window.showFlash = function (message, category = 'info') {
    const container = document.querySelector('.admin-flash-container');
    if (!container) return;

    const flash = document.createElement('div');
    flash.className = `admin-flash-item flash-${category}`;
    flash.textContent = message;

    container.appendChild(flash);

    // Auto-dismiss après 5s
    setTimeout(() => {
        dismissFlash(flash);
    }, 5000);
};

function initFlash() {
    const flashes = document.querySelectorAll('.admin-flash-item');
    if (flashes.length) {
        setTimeout(() => {
            flashes.forEach(f => dismissFlash(f));
        }, 5000);
    }
}

window.initFlash = initFlash;
