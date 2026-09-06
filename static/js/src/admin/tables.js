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

function initCheckoutsListSearch() {
    const checkoutSearchInput = document.getElementById('search-input');
    if (!checkoutSearchInput) return;

    const tbody = document.getElementById('checkouts-tbody') || document.getElementById('checkins-tbody');
    if (!tbody) return;

    const rows = tbody.querySelectorAll('tr[data-search]');
    const resultCount = document.getElementById('result-count');
    const noResults = document.getElementById('no-results');

    checkoutSearchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        let visibleCount = 0;

        rows.forEach(row => {
            const searchText = row.getAttribute('data-search') || '';
            if (searchText.includes(query)) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        if (resultCount) resultCount.innerText = visibleCount;
        if (noResults) noResults.style.display = visibleCount === 0 && rows.length > 0 ? 'block' : 'none';
        tbody.style.display = visibleCount === 0 && rows.length > 0 ? 'none' : '';
    });
}

function initCentralizedSearch() {
    const searchableRows = document.querySelectorAll('.searchable-row');
    if (searchableRows.length === 0) return;

    const filterItems = (query) => {
        const q = query.toLowerCase().trim();
        searchableRows.forEach(row => {
            const searchText = (row.getAttribute('data-search') || '') + ' ' + row.textContent.toLowerCase();
            row.style.display = searchText.includes(q) ? '' : 'none';
        });
    };

    // Gestion du paramètre URL 'q'
    const urlParams = new URLSearchParams(window.location.search);
    const qParam = urlParams.get('q');
    if (qParam) {
        filterItems(qParam);
    }

    const searchInput = document.getElementById('searchInput');
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
    initCheckoutsListSearch();
    initCentralizedSearch();
    initSortableColumns();
}

window.initTables = initTables;
