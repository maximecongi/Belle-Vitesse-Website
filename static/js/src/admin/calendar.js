/**
 * calendar.js — Initialisation de FullCalendar pour le tableau de bord et le calendrier de réservation.
 */

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
    }
}

window.initCalendar = initCalendar;
