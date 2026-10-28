/**
 * fleet-filters.js — Filtrage par statut et recherche instantanée sur la flotte de véhicules.
 */

function initFleetFilters() {
    const filterPills = document.querySelectorAll('#fleet-filter-pills .filter-pill');
    const cards = document.querySelectorAll('.vehicle-card');
    const visibleCount = document.getElementById('fleet-visible-count') || document.getElementById('visible-count');
    const emptyFilterState = document.getElementById('fleet-empty-filter');
    const searchInput = document.getElementById('searchInput');

    if (!cards.length) return;

    let currentFilter = 'all';

    function applyFilters() {
        const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
        let count = 0;
        cards.forEach(card => {
            const status = card.getAttribute('data-status');
            const name = card.getAttribute('data-name') || '';
            const uniqueId = card.getAttribute('data-unique-id') || '';

            const statusMatches = (currentFilter === 'all' || status === currentFilter);
            const searchMatches = !query || name.includes(query) || uniqueId.includes(query);

            if (statusMatches && searchMatches) {
                card.classList.remove('is-hidden', 'u-d-none');
                count++;
            } else {
                card.classList.add('is-hidden', 'u-d-none');
            }
        });

        if (visibleCount) {
            visibleCount.textContent = count;
        }

        if (emptyFilterState) {
            if (count === 0) {
                emptyFilterState.classList.remove('is-hidden', 'u-d-none');
            } else {
                emptyFilterState.classList.add('is-hidden', 'u-d-none');
            }
        }
    }

    if (searchInput && !searchInput._hasFleetListener) {
        searchInput._hasFleetListener = true;
        const urlParams = new URLSearchParams(window.location.search);
        const initialQ = urlParams.get('q');
        if (initialQ) {
            searchInput.value = initialQ;
        }
        searchInput.addEventListener('input', applyFilters);
    }

    filterPills.forEach(pill => {
        if (pill._hasFleetPillListener) return;
        pill._hasFleetPillListener = true;

        pill.addEventListener('click', function () {
            filterPills.forEach(p => {
                p.classList.remove('active', 'admin-btn-primary');
                p.classList.add('admin-btn-quaternary');
            });
            this.classList.add('active', 'admin-btn-primary');
            this.classList.remove('admin-btn-quaternary');
            currentFilter = this.getAttribute('data-status') || this.getAttribute('data-filter') || 'all';
            applyFilters();
        });
    });

    // Application initiale
    applyFilters();
}

window.initFleetFilters = initFleetFilters;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFleetFilters);
} else {
    initFleetFilters();
}
document.addEventListener('swup:contentReplaced', initFleetFilters);

