/**
 * vehicle-timeline.js — Contrôleur de la vue chronologique et par mission des véhicules.
 */

function initVehicleTimeline() {
    const viewToggle = document.getElementById('timeline-view-toggle');
    const viewToggleBtns = document.querySelectorAll('#timeline-view-toggle .view-toggle-btn');
    const missionsView = document.getElementById('timeline-missions-view');
    const linearView = document.getElementById('timeline-linear-view');
    const linearFilters = document.getElementById('linear-filters-container');
    const viewCountSpan = document.getElementById('view-indicator-count');

    if (!viewToggleBtns.length) return;

    const missionsCount = viewToggle ? viewToggle.dataset.missionsCount || '0' : '0';
    const eventsCount = viewToggle ? viewToggle.dataset.eventsCount || '0' : '0';

    viewToggleBtns.forEach(btn => {
        if (btn._hasTimelineToggleListener) return;
        btn._hasTimelineToggleListener = true;

        btn.addEventListener('click', function () {
            viewToggleBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            const view = this.getAttribute('data-view');
            if (view === 'missions') {
                if (missionsView) missionsView.classList.remove('is-hidden');
                if (linearView) linearView.classList.add('is-hidden');
                if (linearFilters) linearFilters.classList.add('is-hidden');
                if (viewCountSpan) viewCountSpan.textContent = `${missionsCount} mission(s) répertoriée(s)`;
            } else {
                if (missionsView) missionsView.classList.add('is-hidden');
                if (linearView) linearView.classList.remove('is-hidden');
                if (linearFilters) linearFilters.classList.remove('is-hidden');
                if (viewCountSpan) viewCountSpan.textContent = `${eventsCount} événement(s) au total`;
            }
        });
    });

    // Filtres pour le flux linéaire
    const filterButtons = document.querySelectorAll('#timeline-filters .timeline-filter-btn');
    const items = document.querySelectorAll('#timeline-linear-view .timeline-linear-item');
    const emptyFilterState = document.getElementById('timeline-empty-filter');

    if (!filterButtons.length) return;

    filterButtons.forEach(btn => {
        if (btn._hasTimelineFilterListener) return;
        btn._hasTimelineFilterListener = true;

        btn.addEventListener('click', function () {
            filterButtons.forEach(b => {
                b.classList.remove('active', 'admin-btn-primary');
                b.classList.add('admin-btn-quaternary');
            });
            this.classList.add('active', 'admin-btn-primary');
            this.classList.remove('admin-btn-quaternary');

            const targetType = this.getAttribute('data-type');
            let count = 0;

            items.forEach(item => {
                const itemType = item.getAttribute('data-type');
                const matches = (targetType === 'all' || itemType === targetType);
                if (matches) {
                    item.classList.remove('is-hidden');
                    count++;
                } else {
                    item.classList.add('is-hidden');
                }
            });

            if (viewCountSpan && linearView && !linearView.classList.contains('is-hidden')) {
                viewCountSpan.textContent = count + ' événement(s) affiché(s)';
            }

            if (emptyFilterState) {
                if (count === 0) {
                    emptyFilterState.classList.remove('is-hidden');
                } else {
                    emptyFilterState.classList.add('is-hidden');
                }
            }
        });
    });
}

window.initVehicleTimeline = initVehicleTimeline;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVehicleTimeline);
} else {
    initVehicleTimeline();
}
document.addEventListener('swup:contentReplaced', initVehicleTimeline);

