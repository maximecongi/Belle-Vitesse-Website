/**
 * tables.js — Recherche en temps réel, filtrage par URL (?q=) et tri dynamique des tables.
 */

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/**
 * Recherche côté serveur (listes paginées) : soumission différée du formulaire GET.
 * Toute la base est interrogée — jamais seulement la page affichée.
 */
const SERVER_SEARCH_DEBOUNCE_MS = 450;
const SERVER_SEARCH_FOCUS_KEY = 'bv-server-search-focus';

function initServerSearch(input) {
    if (input._serverSearchBound || !input.form) return;
    input._serverSearchBound = true;

    // Restaure le focus et le curseur après le rechargement déclenché par la saisie
    try {
        if (sessionStorage.getItem(SERVER_SEARCH_FOCUS_KEY) === window.location.pathname) {
            sessionStorage.removeItem(SERVER_SEARCH_FOCUS_KEY);
            input.focus();
            const len = input.value.length;
            input.setSelectionRange(len, len);
        }
    } catch (e) { /* stockage indisponible : pas de restauration du focus */ }

    let timer = null;
    let lastSubmitted = input.value.trim();

    const submit = () => {
        const value = input.value.trim();
        if (value === lastSubmitted) return;
        // Évite les requêtes sur 1 caractère (trop de bruit), sauf pour vider la recherche
        if (value.length === 1) return;
        lastSubmitted = value;
        try { sessionStorage.setItem(SERVER_SEARCH_FOCUS_KEY, window.location.pathname); } catch (e) { /* ignore */ }
        input.form.requestSubmit ? input.form.requestSubmit() : input.form.submit();
    };

    input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(submit, SERVER_SEARCH_DEBOUNCE_MS);
    });
    input.form.addEventListener('submit', () => {
        clearTimeout(timer);
        lastSubmitted = input.value.trim();
    });
}

function initCentralizedSearch() {
    const searchInput = document.getElementById('searchInput') || document.getElementById('search-input');

    if (searchInput && searchInput.dataset.searchMode === 'server') {
        initServerSearch(searchInput);
        return;
    }

    const searchableRows = document.querySelectorAll('.searchable-row');
    if (searchableRows.length === 0) return;

    const resultCount = document.getElementById('result-count') || document.getElementById('visible-count');
    const noResults = document.getElementById('no-results') || document.getElementById('noResultsRow');

    const filterItems = (query) => {
        const q = query.toLowerCase().trim();
        let visibleCount = 0;
        searchableRows.forEach(row => {
            const searchText = (row.getAttribute('data-search') || '') + ' ' + row.textContent.toLowerCase();
            const matches = searchText.includes(q);
            row.style.display = matches ? '' : 'none';
            if (matches) visibleCount++;
        });

        if (resultCount) resultCount.innerText = visibleCount;
        if (noResults) noResults.style.display = (visibleCount === 0 && searchableRows.length > 0) ? '' : 'none';
    };

    // Gestion du paramètre URL 'q' (liens profonds vers une liste filtrée)
    const urlParams = new URLSearchParams(window.location.search);
    const qParam = urlParams.get('q');
    if (qParam) {
        filterItems(qParam);
    }

    if (searchInput) {
        if (qParam) searchInput.value = qParam;
        searchInput.addEventListener('input', e => {
            filterItems(e.target.value);
        });
    }
}

function initSortableColumns() {
    document.querySelectorAll('.admin-table th.sortable').forEach(th => {
        if (th._sortBound) return;
        th._sortBound = true;

        th.addEventListener('click', () => {
            const table = th.closest('table');
            if (!table) return;
            const tbody = table.querySelector('tbody');
            if (!tbody) return;
            const colIdx = parseInt(th.dataset.col, 10);
            const rows = Array.from(tbody.querySelectorAll('tr.searchable-row'));

            const isAsc = th.classList.contains('asc');
            table.querySelectorAll('th.sortable').forEach(h => h.classList.remove('asc', 'desc'));
            th.classList.add(isAsc ? 'desc' : 'asc');

            rows.sort((a, b) => {
                const aCell = a.children[colIdx];
                const bCell = b.children[colIdx];
                const aText = (aCell?.dataset.sort || aCell?.textContent || '').trim().toLowerCase();
                const bText = (bCell?.dataset.sort || bCell?.textContent || '').trim().toLowerCase();
                return isAsc ? bText.localeCompare(aText) : aText.localeCompare(bText);
            });

            rows.forEach(row => tbody.appendChild(row));
        });
    });
}

function initTables() {
    initCentralizedSearch();
    initSortableColumns();
}

window.initTables = initTables;
