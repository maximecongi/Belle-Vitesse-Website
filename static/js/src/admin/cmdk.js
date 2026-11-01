/**
 * cmdk.js — Palette de commande rapide globale (Cmd + K / Ctrl + K).
 * Refonte Hub-centrique avec indexation multi-entités, navigation clavier fluide,
 * filtres rapides (scopes), historique récent (localStorage) et conformité au Design System Belle Vitesse.
 */

let _cmdkCurrentResults = [];
let _cmdkSelectedIndex = 0;
let _cmdkDebounceTimer = null;
let _cmdkActiveScopes = new Set();
const CMDK_RECENT_KEY = 'bv_cmdk_recents';

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
        case 'clapperboard':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.2 6 3 11l-.9-2.4c-.4-1.1.2-2.4 1.3-2.8l13.6-5c1.1-.4 2.4.2 2.8 1.3l.4 1.9Z"/><path d="m6.2 5.3 3.1 4.5"/><path d="m12.1 3.1 3.1 4.5"/><rect x="2" y="11" width="20" height="10" rx="2"/></svg>';
        case 'truck':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18.5" r="2.5"/><circle cx="7" cy="18.5" r="2.5"/></svg>';
        case 'package-check':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 16 2 2 4-4"/><path d="M21 10V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l2-1.14"/><path d="m7.5 4.27 9 5.15"/><polyline points="3.29 7 12 12 20.71 7"/><line x1="12" x2="12" y1="22" y2="12"/></svg>';
        case 'shield':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg>';
        case 'file-signature':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 19.5v.5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8.5L20 7.5V13"/><path d="M14 2v6h6"/><path d="M18.42 15.61a2.1 2.1 0 1 1 2.97 2.97L16.95 23 14 24l1-2.95 4.42-4.44z"/></svg>';
        case 'file-check':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="m9 15 2 2 4-4"/></svg>';
        case 'alert-triangle':
        case 'alert':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
        case 'user':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="7" r="4"/><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/></svg>';
        case 'users':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>';
        case 'user-plus':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>';
        case 'building':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/><line x1="9" y1="22" x2="9" y2="18"/><line x1="15" y1="22" x2="15" y2="18"/><line x1="9" y1="6" x2="9.01" y2="6"/><line x1="15" y1="6" x2="15.01" y2="6"/><line x1="9" y1="10" x2="9.01" y2="10"/><line x1="15" y1="10" x2="15.01" y2="10"/><line x1="9" y1="14" x2="9.01" y2="14"/><line x1="15" y1="14" x2="15.01" y2="14"/></svg>';
        case 'plus':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>';
        case 'calendar':
        case 'calendar-range':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>';
        case 'archive':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>';
        case 'layout-dashboard':
        case 'layout':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/></svg>';
        case 'pen-tool':
        case 'pen':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 19 7-7 3 3-7 7-3-3z"/><path d="m18 13-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="m2 2 7.586 7.586"/><circle cx="11" cy="11" r="2"/></svg>';
        case 'book-open':
        case 'book':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>';
        case 'tag':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>';
        case 'settings':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>';
        case 'history':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>';
        default:
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
    }
}

// ── Gestion de l'historique récent (localStorage) ─────────────────

function _cmdkGetRecents() {
    try {
        const raw = localStorage.getItem(CMDK_RECENT_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
        return [];
    }
}

function _cmdkSaveRecent(item) {
    if (!item || !item.url) return;
    try {
        let recents = _cmdkGetRecents();
        // Déduplication par URL
        recents = recents.filter(r => r.url !== item.url);
        // Ajout en tête
        recents.unshift({
            id: item.id || `rec-${Date.now()}`,
            title: item.title,
            subtitle: item.subtitle,
            url: item.url,
            category: 'Recherches récentes',
            entity_type: item.entity_type || 'recent',
            icon: item.icon || 'history'
        });
        // Garder maximum 5 éléments récents
        if (recents.length > 5) {
            recents = recents.slice(0, 5);
        }
        localStorage.setItem(CMDK_RECENT_KEY, JSON.stringify(recents));
    } catch (e) {
        console.warn('Erreur enregistrement récent Cmd+K:', e);
    }
}

function clearCmdKHistory(e) {
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }
    try {
        localStorage.removeItem(CMDK_RECENT_KEY);
    } catch (err) {
        console.warn(err);
    }
    const input = document.getElementById('cmdkInput');
    const query = input ? input.value.trim() : '';
    fetchCmdKResults(query);
}
window.clearCmdKHistory = clearCmdKHistory;

// ── Gestion de l'ouverture et fermeture ───────────────────────────

function openCmdK() {
    const overlay = document.getElementById('cmdkOverlay');
    const input = document.getElementById('cmdkInput');
    if (!overlay || !input) return;

    overlay.classList.add('active');
    overlay.setAttribute('aria-hidden', 'false');
    input.value = '';
    _cmdkCurrentResults = [];
    _cmdkSelectedIndex = 0;
    _cmdkActiveScopes.clear();

    _cmdkSyncScopeChips();
    fetchCmdKResults('');
    setTimeout(() => input.focus(), 60);
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

// ── Gestion des filtres rapides (Scopes) ──────────────────────────

const SCOPE_CONFIG = {
    'all': { label: 'Tous', prefix: '' },
    'project': { label: 'Projets', prefix: 'p:' },
    'inspection': { label: 'Contrôles', prefix: 'c:' },
    'waiver': { label: 'Décharges', prefix: 'w:' },
    'vehicle': { label: 'Véhicules', prefix: 'v:' },
    'contact': { label: 'Contacts', prefix: 'ct:' },
    'production': { label: 'Productions', prefix: 'prod:' },
    'incident': { label: 'Incidents', prefix: 'i:' },
    'checkout': { label: 'Départs', prefix: 'co:' },
    'checkin': { label: 'Retours', prefix: 'ci:' }
};

const CMDK_PREFIX_MAP = {
    'p': 'project', 'projet': 'project', 'project': 'project',
    'c': 'inspection', 'co': 'checkout', 'ci': 'checkin', 'controle': 'inspection', 'contrôle': 'inspection',
    'w': 'waiver', 'waiver': 'waiver', 'decharge': 'waiver', 'décharge': 'waiver', 'cgl': 'waiver',
    'v': 'vehicle', 'vehicule': 'vehicle', 'véhicule': 'vehicle', 'vehicle': 'vehicle',
    'ct': 'contact', 'contact': 'contact',
    'prod': 'production', 'production': 'production',
    'i': 'incident', 'inc': 'incident', 'incident': 'incident'
};

function _cmdkToggleScope(scope) {
    if (!scope || scope === 'all') {
        _cmdkActiveScopes.clear();
    } else {
        if (_cmdkActiveScopes.has(scope)) {
            _cmdkActiveScopes.delete(scope);
        } else {
            _cmdkActiveScopes.add(scope);
        }
    }
    _cmdkSyncScopeChips();
    const input = document.getElementById('cmdkInput');
    const q = input ? input.value.trim() : '';
    fetchCmdKResults(q);
}

function _cmdkRemoveScope(scope) {
    if (_cmdkActiveScopes.has(scope)) {
        _cmdkActiveScopes.delete(scope);
        _cmdkSyncScopeChips();
        const input = document.getElementById('cmdkInput');
        const q = input ? input.value.trim() : '';
        fetchCmdKResults(q);
    }
}

function _cmdkSyncScopeChips() {
    const isAll = _cmdkActiveScopes.size === 0;
    const chips = document.querySelectorAll('.admin-cmdk-scope-chip');
    chips.forEach(chip => {
        const s = chip.dataset.scope;
        if (s === 'all') {
            chip.classList.toggle('is-active', isAll);
        } else {
            chip.classList.toggle('is-active', _cmdkActiveScopes.has(s));
        }
    });

    const container = document.getElementById('cmdkBadgesContainer');
    if (container) {
        if (isAll) {
            container.innerHTML = '';
        } else {
            let html = '';
            _cmdkActiveScopes.forEach(scope => {
                const cfg = SCOPE_CONFIG[scope] || { label: scope };
                html += `
                    <span class="admin-cmdk-active-scope" data-scope="${_cmdkEscapeHtml(scope)}">
                        <span>${_cmdkEscapeHtml(cfg.label)}</span>
                        <button type="button" class="admin-cmdk-scope-remove" data-scope="${_cmdkEscapeHtml(scope)}" title="Retirer ce filtre" aria-label="Retirer ce filtre">×</button>
                    </span>
                `;
            });
            container.innerHTML = html;

            container.querySelectorAll('.admin-cmdk-scope-remove').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    _cmdkRemoveScope(btn.dataset.scope);
                    const input = document.getElementById('cmdkInput');
                    if (input) input.focus();
                });
            });
        }
    }
}

// ── Appel API de recherche ────────────────────────────────────────

function fetchCmdKResults(q) {
    const resultsContainer = document.getElementById('cmdkResults');
    if (!resultsContainer) return;

    let cleanQuery = q !== undefined && q !== null ? String(q).trim() : '';

    const scopeParam = _cmdkActiveScopes.size > 0
        ? Array.from(_cmdkActiveScopes).join(',')
        : 'all';

    const url = `/admin/api/search?q=${encodeURIComponent(cleanQuery)}&scope=${encodeURIComponent(scopeParam)}`;
    fetch(url)
        .then(res => res.json())
        .then(data => {
            let serverResults = data.results || [];

            // Si query vide, injecter les recherches récentes en haut
            if (!cleanQuery) {
                const recents = _cmdkGetRecents();
                if (recents.length > 0) {
                    serverResults = [...recents, ...serverResults];
                }
            }

            _cmdkCurrentResults = serverResults;
            _cmdkSelectedIndex = 0;
            renderCmdKResults(cleanQuery);
        })
        .catch(err => {
            console.error('Erreur recherche Cmd+K:', err);
        });
}

// ── Rendu structuré par sections (Spotlight / Raycast) ─────────────

function renderCmdKResults(query) {
    const resultsContainer = document.getElementById('cmdkResults');
    if (!resultsContainer) return;

    if (_cmdkCurrentResults.length === 0) {
        resultsContainer.innerHTML = '<div class="admin-cmdk-empty">Aucun résultat trouvé pour votre recherche.</div>';
        return;
    }

    // Regrouper par catégorie
    const groups = {};
    const groupOrder = [];

    _cmdkCurrentResults.forEach((item, navIndex) => {
        const cat = item.category || 'Autres';
        if (!groups[cat]) {
            groups[cat] = [];
            groupOrder.push(cat);
        }
        groups[cat].push({ item, navIndex });
    });

    let html = '';

    groupOrder.forEach(categoryName => {
        const itemsInGroup = groups[categoryName];
        const isRecent = categoryName === 'Recherches récentes';

        html += `
            <div class="admin-cmdk-section-header">
                <span class="admin-cmdk-section-title">
                    <span>${_cmdkEscapeHtml(categoryName)}</span>
                    <span class="admin-cmdk-section-count">${itemsInGroup.length}</span>
                </span>
                ${isRecent ? '<button type="button" class="admin-cmdk-clear-history" onclick="clearCmdKHistory(event)" title="Effacer les recherches récentes">Effacer</button>' : ''}
            </div>
        `;

        itemsInGroup.forEach(({ item, navIndex }) => {
            const isSelected = navIndex === _cmdkSelectedIndex;
            const entityType = (item.entity_type || 'page').toLowerCase();
            const badgeClass = `admin-cmdk-badge-${entityType}`;
            const cleanTitle = _cmdkEscapeHtml(item.title);
            const cleanSub = _cmdkEscapeHtml(item.subtitle);

            html += `
                <a href="${item.url}" class="admin-cmdk-item ${isSelected ? 'selected' : ''}" data-index="${navIndex}">
                    <div class="admin-cmdk-item-left">
                        <div class="admin-cmdk-item-icon" data-entity="${entityType}">
                            ${_cmdkGetIconSvg(item.icon)}
                        </div>
                        <div class="admin-cmdk-item-text">
                            <span class="admin-cmdk-item-title">${cleanTitle}</span>
                            <span class="admin-cmdk-item-sub">${cleanSub}</span>
                        </div>
                    </div>
                    <span class="admin-cmdk-badge ${badgeClass}">${_cmdkEscapeHtml(item.category)}</span>
                </a>
            `;
        });
    });

    resultsContainer.innerHTML = html;

    // Attachement des écouteurs sur chaque item
    resultsContainer.querySelectorAll('.admin-cmdk-item').forEach(el => {
        el.addEventListener('mouseenter', () => {
            _cmdkSelectedIndex = parseInt(el.dataset.index, 10);
            updateCmdKSelection();
        });

        el.addEventListener('click', (e) => {
            const navIndex = parseInt(el.dataset.index, 10);
            const item = _cmdkCurrentResults[navIndex];
            if (item) {
                _cmdkSaveRecent(item);
                if (e.metaKey || e.ctrlKey) {
                    // Laisser le comportement natif d'ouverture nouvel onglet
                    return;
                }
                closeCmdK();
            }
        });
    });
}

function updateCmdKSelection() {
    const resultsContainer = document.getElementById('cmdkResults');
    if (!resultsContainer) return;

    const items = resultsContainer.querySelectorAll('.admin-cmdk-item');
    items.forEach((item) => {
        const idx = parseInt(item.dataset.index, 10);
        if (idx === _cmdkSelectedIndex) {
            item.classList.add('selected');
            item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        } else {
            item.classList.remove('selected');
        }
    });
}

// ── Initialisation des composants & événements ───────────────────

function initCmdK() {
    const overlay = document.getElementById('cmdkOverlay');
    const input = document.getElementById('cmdkInput');
    const trigger = document.getElementById('cmdkTrigger');
    const closeBtn = document.getElementById('cmdkCloseBtn');
    const scopeBar = document.getElementById('cmdkScopeBar');

    if (!overlay || !input) return;

    // Bouton Trigger du header
    if (trigger && !trigger._cmdkBound) {
        trigger._cmdkBound = true;
        trigger.addEventListener('click', (e) => {
            e.preventDefault();
            openCmdK();
        });
    }

    // Bouton ESC dans le header
    if (closeBtn && !closeBtn._cmdkBound) {
        closeBtn._cmdkBound = true;
        closeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            closeCmdK();
        });
    }

    // Clic sur l'overlay pour fermer
    if (!overlay._cmdkBound) {
        overlay._cmdkBound = true;
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeCmdK();
        });
    }

    // Barre de Scope Chips
    if (scopeBar && !scopeBar._cmdkBound) {
        scopeBar._cmdkBound = true;
        scopeBar.addEventListener('click', (e) => {
            const chip = e.target.closest('.admin-cmdk-scope-chip');
            if (!chip) return;
            const scope = chip.dataset.scope;
            _cmdkToggleScope(scope);
            input.focus();
        });
    }

    // Saisie dans l'input
    if (!input._cmdkBound) {
        input._cmdkBound = true;

        input.addEventListener('input', () => {
            const rawVal = input.value;
            if (rawVal.includes(':')) {
                const parts = rawVal.split(':');
                const pfx = parts[0].trim().toLowerCase();
                const remainder = parts.slice(1).join(':').trimStart();

                if (CMDK_PREFIX_MAP[pfx]) {
                    _cmdkActiveScopes.add(CMDK_PREFIX_MAP[pfx]);
                    _cmdkSyncScopeChips();
                    input.value = remainder;
                }
            }

            clearTimeout(_cmdkDebounceTimer);
            _cmdkDebounceTimer = setTimeout(() => {
                fetchCmdKResults(input.value);
            }, 120);
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
                    const item = _cmdkCurrentResults[_cmdkSelectedIndex];
                    _cmdkSaveRecent(item);

                    if (e.metaKey || e.ctrlKey) {
                        window.open(item.url, '_blank');
                    } else {
                        window.location.href = item.url;
                    }
                }
            } else if (e.key === 'Backspace' && input.value === '' && _cmdkActiveScopes.size > 0) {
                // Effacer le dernier filtre de scope si on appuie sur Retour sur un champ vide
                e.preventDefault();
                const scopesArr = Array.from(_cmdkActiveScopes);
                const lastScope = scopesArr[scopesArr.length - 1];
                _cmdkActiveScopes.delete(lastScope);
                _cmdkSyncScopeChips();
                fetchCmdKResults('');
            } else if (e.key === 'Tab') {
                // Auto-compléter le préfixe
                const val = input.value.trim().toLowerCase();
                if (CMDK_PREFIX_MAP[val]) {
                    e.preventDefault();
                    _cmdkActiveScopes.add(CMDK_PREFIX_MAP[val]);
                    input.value = '';
                    _cmdkSyncScopeChips();
                    fetchCmdKResults('');
                }
            }
        });
    }
}

// ── Raccourci clavier global Cmd+K / Ctrl+K et Escape ─────────────

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
