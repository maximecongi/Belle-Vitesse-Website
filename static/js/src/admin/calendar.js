/**
 * calendar.js — Initialisation et rendu personnalisé de FullCalendar
 * conforme au Design System de Belle Vitesse ERP.
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

function getEntityIconSvg(type) {
    if (type === 'checkout') {
        // Lucide 'truck'
        return '<svg class="fc-event-custom__icon" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18.5" r="2.5"/><circle cx="7" cy="18.5" r="2.5"/></svg>';
    }
    if (type === 'checkin') {
        // Lucide 'package-check'
        return '<svg class="fc-event-custom__icon" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 16 2 2 4-4"/><path d="M21 10V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l2-1.14"/><path d="m7.5 4.27 9 5.15"/><polyline points="3.29 7 12 12 20.71 7"/><line x1="12" x2="12" y1="22" y2="12"/></svg>';
    }
    // Lucide 'clapperboard' (projet / tournage)
    return '<svg class="fc-event-custom__icon" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.2 6 3 11l-.9-2.4 17.2-5z"/><path d="m6.2 5.3 3.1 3.9"/><path d="m12.4 3.4 3.1 4"/><path d="M3 11h18v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>';
}

function initCalendar() {
    const calendarEl = document.getElementById('calendar');
    if (calendarEl && typeof FullCalendar !== 'undefined' && !calendarEl.dataset.initialized) {
        calendarEl.dataset.initialized = 'true';

        const calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridWeek',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,dayGridWeek,dayGridDay'
            },
            locale: 'fr',
            eventOrder: "order,start",
            allDayText: 'Toute la journée',
            firstDay: 1,
            buttonText: {
                today: "Aujourd'hui",
                month: 'Mois',
                week: 'Semaine',
                day: 'Jour'
            },
            events: '/admin/api/events',
            eventContent: function (arg) {
                const props = arg.event.extendedProps || {};
                const type = props.type || 'project';
                const typeLabel = props.typeLabel || (type === 'checkout' ? 'Départ' : type === 'checkin' ? 'Retour' : 'Tournage');
                const projectName = props.projectName || arg.event.title;
                const production = props.production || '';
                const iconSvg = getEntityIconSvg(type);

                return {
                    html: `
                        <div class="fc-event-custom fc-event-custom--${escapeHtml(type)}">
                            <span class="fc-event-custom__badge">${iconSvg}</span>
                            <span class="fc-event-custom__title">${escapeHtml(projectName)}</span>
                            ${production ? `<span class="fc-event-custom__prod">${escapeHtml(production)}</span>` : ''}
                        </div>
                    `
                };
            },
            eventDidMount: function (info) {
                const props = info.event.extendedProps || {};
                const typeLabel = props.typeLabel || (props.type === 'checkout' ? 'Départ' : props.type === 'checkin' ? 'Retour' : 'Tournage');
                const projectName = props.projectName || info.event.title;
                const prod = props.production ? ` — Prod : ${props.production}` : '';
                info.el.setAttribute('title', `${typeLabel} : ${projectName}${prod}`);
            },
            eventClick: function (info) {
                if (info.event.url) {
                    info.jsEvent.preventDefault();
                    window.location.href = info.event.url;
                }
            },
            height: 'auto',
            contentHeight: 650
        });

        calendar.render();

        // ── Gestion des filtres interactifs par type d'événement ──
        const filterBtns = document.querySelectorAll('#calendarFilters .calendar-filter-btn');
        if (filterBtns.length > 0) {
            filterBtns.forEach(btn => {
                btn.addEventListener('click', function () {
                    const filter = this.dataset.filter || 'all';
                    calendarEl.dataset.filter = filter;

                    filterBtns.forEach(b => {
                        b.classList.remove('active', 'admin-btn-primary');
                        b.classList.add('admin-btn-quaternary');
                    });
                    this.classList.add('active', 'admin-btn-primary');
                    this.classList.remove('admin-btn-quaternary');
                });
            });
        }
    }
}

window.initCalendar = initCalendar;

