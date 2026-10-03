/**
 * checkpoints.js — Gestion interactive des points de contrôle (Checkpoints)
 * Administration Belle Vitesse.
 * - Formulaire de création/édition : activation/désactivation et vidage dynamique du champ unité
 * - Liste des points de contrôle : recherche, filtres par catégorie, modale de consignes spécifiques
 */

document.addEventListener('DOMContentLoaded', function () {
    initCheckpointForm();
    initCheckpointsList();
});

/**
 * Initialise le comportement dynamique du formulaire de point de contrôle.
 * Désactive et vide le champ unité si le type d'évaluation n'est pas "value" (Mesure / Valeur saisie).
 */
function initCheckpointForm() {
    const typeSelect = document.getElementById('checkpoint_type');
    const unitInput = document.getElementById('checkpoint_unit');
    const unitLabel = document.getElementById('checkpoint_unit_label');
    const unitHint = document.getElementById('checkpoint_unit_hint');

    if (!typeSelect || !unitInput) return;

    function updateUnitState() {
        const isValue = typeSelect.value === 'value';
        if (isValue) {
            unitInput.disabled = false;
            if (unitLabel) unitLabel.classList.remove('u-text-muted');
            if (unitHint) unitHint.textContent = 'Affichée à côté de la valeur saisie.';
        } else {
            unitInput.value = '';
            unitInput.disabled = true;
            if (unitLabel) unitLabel.classList.add('u-text-muted');
            if (unitHint) unitHint.textContent = 'Non applicable pour une évaluation par statut.';
        }
    }

    typeSelect.addEventListener('change', updateUnitState);
    updateUnitState();
}

/**
 * Initialise la recherche, les filtres et la modale de consigne sur la page de liste des checkpoints.
 */
function initCheckpointsList() {
    const tbody = document.getElementById('checkpointsTableBody');
    if (!tbody) return;

    const searchInput = document.getElementById('searchInput') || document.getElementById('checkpointSearch') || document.getElementById('checkpointSearchInput');
    const filterPills = document.querySelectorAll('#checkpoint-filter-pills .filter-pill, .category-filter-pill');
    const noResultsRow = document.getElementById('checkpoint-no-results') || document.getElementById('noResultsRow');
    const visibleCountEl = document.getElementById('checkpoint-visible-count') || document.getElementById('visibleCheckpointsCount');

    const rows = tbody.querySelectorAll('.checkpoint-row');
    let activeCategory = 'all';
    let searchQuery = '';

    function normalizeStr(str) {
        return (str || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .trim();
    }

    function filterRows() {
        let count = 0;
        const normQuery = normalizeStr(searchQuery);
        const normActiveCategory = normalizeStr(activeCategory);
        const visiblePerCategory = {};

        rows.forEach(function (row) {
            const cat = normalizeStr(row.getAttribute('data-category') || '');
            const searchData = normalizeStr(row.getAttribute('data-search') || '');

            const matchesCategory = (normActiveCategory === 'all' || cat === normActiveCategory);
            const matchesSearch = !normQuery || searchData.indexOf(normQuery) !== -1;
            const show = matchesCategory && matchesSearch;

            row.classList.toggle('u-d-none', !show);
            if (show) {
                count++;
                visiblePerCategory[cat] = (visiblePerCategory[cat] || 0) + 1;
            }
        });

        const catHeaders = tbody.querySelectorAll('.checkpoint-category-header');
        catHeaders.forEach(function (header) {
            const cat = normalizeStr(header.getAttribute('data-category') || '');
            const hasVisibleRows = (visiblePerCategory[cat] || 0) > 0;
            const matchesCategoryFilter = (normActiveCategory === 'all' || cat === normActiveCategory);
            const showHeader = hasVisibleRows && matchesCategoryFilter;
            header.classList.toggle('u-d-none', !showHeader);
            if (showHeader) {
                const countSpan = header.querySelector('.checkpoint-cat-count');
                if (countSpan) {
                    countSpan.textContent = visiblePerCategory[cat] || 0;
                }
            }
        });

        if (visibleCountEl) visibleCountEl.textContent = count;
        if (noResultsRow) noResultsRow.classList.toggle('u-d-none', count > 0);
    }

    if (searchInput) {
        searchInput.addEventListener('input', function (e) {
            searchQuery = e.target.value;
            filterRows();
        });
    }

    filterPills.forEach(function (btn) {
        btn.addEventListener('click', function () {
            filterPills.forEach(function (b) {
                b.classList.remove('active', 'admin-btn-primary');
                b.classList.add('admin-btn-quaternary');
            });
            btn.classList.add('active', 'admin-btn-primary');
            btn.classList.remove('admin-btn-quaternary');
            activeCategory = btn.getAttribute('data-category');
            filterRows();
        });
    });

    // ── Gestion de la Modale de Consigne Spécifique ──
    const modal = document.getElementById('checkpointIndicationModal');
    const modalVehicle = document.getElementById('modalVehicleName');
    const modalCheckpoint = document.getElementById('modalCheckpointLabel');
    const modalIndication = document.getElementById('modalIndicationText');
    const closeModalBtn = document.getElementById('closeIndicationModal');
    const closeModalFooterBtn = document.getElementById('closeIndicationModalBtn');

    function openModal(vehicle, checkpoint, indication) {
        if (!modal) return;
        if (modalVehicle) modalVehicle.textContent = '🏎️ ' + vehicle;
        if (modalCheckpoint) modalCheckpoint.textContent = checkpoint;
        if (modalIndication) modalIndication.textContent = indication;
        modal.classList.add('open');
        document.body.classList.add('u-overflow-hidden');
    }

    function closeModal() {
        if (!modal) return;
        modal.classList.remove('open');
        document.body.classList.remove('u-overflow-hidden');
    }

    document.addEventListener('click', function (e) {
        const trigger = e.target.closest('.checkpoint-spec-trigger');
        if (trigger) {
            e.preventDefault();
            e.stopPropagation();
            openModal(
                trigger.getAttribute('data-vehicle') || '',
                trigger.getAttribute('data-checkpoint') || '',
                trigger.getAttribute('data-indication') || ''
            );
            return;
        }

        if (e.target === modal || e.target === closeModalBtn || e.target === closeModalFooterBtn || e.target.closest('#closeIndicationModal')) {
            closeModal();
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal && modal.classList.contains('open')) {
            closeModal();
        }
    });
}
