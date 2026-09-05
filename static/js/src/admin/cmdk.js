/**
 * cmdk.js — Palette de commande rapide (Cmd + K / Ctrl + K).
 */

let _cmdkCurrentResults = [];
let _cmdkSelectedIndex = 0;
let _cmdkDebounceTimer = null;

function _cmdkEscapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function _cmdkGetIconSvg(icon) {
    switch (icon) {
        case 'folder':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>';
        case 'building':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect><line x1="9" y1="22" x2="9" y2="18"></line><line x1="15" y1="22" x2="15" y2="18"></line><line x1="9" y1="6" x2="9.01" y2="6"></line><line x1="15" y1="6" x2="15.01" y2="6"></line><line x1="9" y1="10" x2="9.01" y2="10"></line><line x1="15" y1="10" x2="15.01" y2="10"></line><line x1="9" y1="14" x2="9.01" y2="14"></line><line x1="15" y1="14" x2="15.01" y2="14"></line></svg>';
        case 'truck':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>';
        case 'calendar':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>';
        case 'user':
        case 'users':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
        case 'plus':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>';
        case 'mail':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>';
        case 'archive':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line></svg>';
        case 'clipboard':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path><rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect></svg>';
        case 'tag':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>';
        case 'settings':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>';
        case 'alert':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>';
        default:
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';
    }
}

function openCmdK() {
    const overlay = document.getElementById('cmdkOverlay');
    const input = document.getElementById('cmdkInput');
    if (!overlay || !input) return;
    overlay.classList.add('active');
    overlay.setAttribute('aria-hidden', 'false');
    input.value = '';
    _cmdkCurrentResults = [];
    _cmdkSelectedIndex = 0;
    fetchCmdKResults('');
    setTimeout(() => input.focus(), 50);
}

function closeCmdK() {
    const overlay = document.getElementById('cmdkOverlay');
    const input = document.getElementById('cmdkInput');
    if (!overlay) return;
    overlay.classList.remove('active');
    overlay.setAttribute('aria-hidden', 'true');
    if (input) input.blur();
}

window.openCmdK = openCmdK;
window.closeCmdK = closeCmdK;

function fetchCmdKResults(q) {
    const resultsContainer = document.getElementById('cmdkResults');
    if (!resultsContainer) return;
    const url = `/admin/api/search?q=${encodeURIComponent(q)}`;
    fetch(url)
        .then(res => res.json())
        .then(data => {
            _cmdkCurrentResults = data.results || [];
            _cmdkSelectedIndex = 0;
            renderCmdKResults();
        })
        .catch(err => {
            console.error('Erreur recherche Cmd+K:', err);
        });
}

function renderCmdKResults() {
    const resultsContainer = document.getElementById('cmdkResults');
    if (!resultsContainer) return;

    if (_cmdkCurrentResults.length === 0) {
        resultsContainer.innerHTML = '<div class="admin-cmdk-empty">Aucun résultat trouvé.</div>';
        return;
    }

    resultsContainer.innerHTML = _cmdkCurrentResults.map((item, idx) => {
        const badgeClass = `admin-cmdk-badge-${(item.category || '').toLowerCase()}`;
        return `
            <a href="${item.url}" class="admin-cmdk-item ${idx === _cmdkSelectedIndex ? 'selected' : ''}" data-index="${idx}">
                <div class="admin-cmdk-item-left">
                    <div class="admin-cmdk-item-icon">
                        ${_cmdkGetIconSvg(item.icon)}
                    </div>
                    <div class="admin-cmdk-item-text">
                        <span class="admin-cmdk-item-title">${_cmdkEscapeHtml(item.title)}</span>
                        <span class="admin-cmdk-item-sub">${_cmdkEscapeHtml(item.subtitle)}</span>
                    </div>
                </div>
                <span class="admin-cmdk-badge ${badgeClass}">${_cmdkEscapeHtml(item.category)}</span>
            </a>
        `;
    }).join('');

    resultsContainer.querySelectorAll('.admin-cmdk-item').forEach(el => {
        el.addEventListener('mouseenter', () => {
            _cmdkSelectedIndex = parseInt(el.dataset.index, 10);
            updateCmdKSelection();
        });
    });
}

function updateCmdKSelection() {
    const resultsContainer = document.getElementById('cmdkResults');
    if (!resultsContainer) return;
    const items = resultsContainer.querySelectorAll('.admin-cmdk-item');
    items.forEach((item, idx) => {
        if (idx === _cmdkSelectedIndex) {
            item.classList.add('selected');
            item.scrollIntoView({ block: 'nearest' });
        } else {
            item.classList.remove('selected');
        }
    });
}

function initCmdK() {
    const overlay = document.getElementById('cmdkOverlay');
    const input = document.getElementById('cmdkInput');
    const trigger = document.getElementById('cmdkTrigger');
    const closeBtn = document.getElementById('cmdkCloseBtn');

    if (!overlay || !input) return;

    if (trigger && !trigger._cmdkBound) {
        trigger._cmdkBound = true;
        trigger.addEventListener('click', (e) => {
            e.preventDefault();
            openCmdK();
        });
    }

    if (closeBtn && !closeBtn._cmdkBound) {
        closeBtn._cmdkBound = true;
        closeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            closeCmdK();
        });
    }

    if (!overlay._cmdkBound) {
        overlay._cmdkBound = true;
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeCmdK();
        });
    }

    if (!input._cmdkBound) {
        input._cmdkBound = true;
        input.addEventListener('input', () => {
            clearTimeout(_cmdkDebounceTimer);
            _cmdkDebounceTimer = setTimeout(() => {
                const query = input.value.trim();
                fetchCmdKResults(query);
            }, 150);
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (_cmdkCurrentResults.length > 0) {
                    _cmdkSelectedIndex = (_cmdkSelectedIndex + 1) % _cmdkCurrentResults.length;
                    updateCmdKSelection();
                }
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (_cmdkCurrentResults.length > 0) {
                    _cmdkSelectedIndex = (_cmdkSelectedIndex - 1 + _cmdkCurrentResults.length) % _cmdkCurrentResults.length;
                    updateCmdKSelection();
                }
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (_cmdkCurrentResults.length > 0 && _cmdkCurrentResults[_cmdkSelectedIndex]) {
                    window.location.href = _cmdkCurrentResults[_cmdkSelectedIndex].url;
                }
            }
        });
    }
}

// Raccourci clavier global Cmd+K / Ctrl+K et Escape
if (!window._cmdkKeydownAttached) {
    window._cmdkKeydownAttached = true;
    document.addEventListener('keydown', (e) => {
        const isK = (e.key && e.key.toLowerCase() === 'k') || e.code === 'KeyK';
        if ((e.metaKey || e.ctrlKey) && isK) {
            e.preventDefault();
            const o = document.getElementById('cmdkOverlay');
            if (o && o.classList.contains('active')) {
                closeCmdK();
            } else {
                openCmdK();
            }
        } else if (e.key === 'Escape') {
            const o = document.getElementById('cmdkOverlay');
            if (o && o.classList.contains('active')) {
                e.preventDefault();
                closeCmdK();
            }
        }
    });
}

window.initCmdK = initCmdK;
