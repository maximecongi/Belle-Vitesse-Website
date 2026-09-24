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
        return '<svg class="fc-phase-icon fc-phase-icon--checkout" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18.5" r="2.5"/><circle cx="7" cy="18.5" r="2.5"/></svg>';
    }
    if (type === 'checkin') {
        // Lucide 'package-check'
        return '<svg class="fc-phase-icon fc-phase-icon--checkin" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 16 2 2 4-4"/><path d="M21 10V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l2-1.14"/><path d="m7.5 4.27 9 5.15"/><polyline points="3.29 7 12 12 20.71 7"/><line x1="12" x2="12" y1="22" y2="12"/></svg>';
    }
    // Lucide 'clapperboard' (projet / tournage)
    return '<svg class="fc-phase-icon fc-phase-icon--project" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.2 6 3 11l-.9-2.4 17.2-5z"/><path d="m6.2 5.3 3.1 3.9"/><path d="m12.4 3.4 3.1 4"/><path d="M3 11h18v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>';
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
                // Squelette de base : la ligne de continuité et le conteneur de badges
                return {
                    html: `
                        <div class="fc-unified-track">
                            <div class="fc-unified-track__line"></div>
                            <div class="fc-unified-track__badges"></div>
                        </div>
                    `
                };
            },
            eventDidMount: function (info) {
                const el = info.el;
                const props = info.event.extendedProps || {};
                const projectName = props.projectName || info.event.title;
                const production = props.production || '';
                const depDate = props.departureDate;
                const shootStart = props.shootStartDate;
                const shootEnd = props.shootEndDate || shootStart;
                const retDate = props.returnDate;

                // Infobulle native complète
                function formatDateFr(dStr) {
                    if (!dStr) return '';
                    const parts = dStr.split('-');
                    return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : dStr;
                }

                const tips = [`Projet : ${projectName}${production ? ' (' + production + ')' : ''}`];
                if (depDate) tips.push(`Départ : ${formatDateFr(depDate)}`);
                if (shootStart) {
                    const shootEndStr = shootEnd && shootEnd !== shootStart ? ` au ${formatDateFr(shootEnd)}` : '';
                    tips.push(`Tournage : du ${formatDateFr(shootStart)}${shootEndStr}`);
                }
                if (retDate) tips.push(`Retour : ${formatDateFr(retDate)}`);
                el.setAttribute('title', tips.join(' • '));

                // ── Positionnement millimétré des jalons sur leurs cases respectives ──
                const badgesContainer = el.querySelector('.fc-unified-track__badges');
                if (!badgesContainer) return;

                const tr = el.closest('tr');
                if (!tr) return;

                const dayCells = Array.from(tr.querySelectorAll('td.fc-daygrid-day[data-date]'));
                const rowDates = dayCells.map(td => td.getAttribute('data-date'));
                if (rowDates.length === 0) return;

                const harness = el.closest('.fc-daygrid-event-harness');
                let segDates = [];

                if (harness && harness.style.gridColumn) {
                    const parts = harness.style.gridColumn.split('/').map(s => parseInt(s.trim(), 10));
                    if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
                        segDates = rowDates.slice(parts[0] - 1, parts[1] - 1);
                    }
                }

                // Fallback de détection géométrique si gridColumn n'est pas explicite
                if (segDates.length === 0) {
                    const elRect = el.getBoundingClientRect();
                    dayCells.forEach(td => {
                        const tdRect = td.getBoundingClientRect();
                        if (tdRect.right > elRect.left + 2 && tdRect.left < elRect.right - 2) {
                            segDates.push(td.getAttribute('data-date'));
                        }
                    });
                }

                if (segDates.length === 0) {
                    // Dernier repli : affiche le projet sur toute la longueur
                    badgesContainer.innerHTML = `
                        <span class="fc-phase-badge fc-phase-badge--project" style="left:0; width:100%;">
                            <span class="fc-phase-badge__icon">${getEntityIconSvg('project')}</span>
                            <span class="fc-phase-badge__title">${escapeHtml(projectName)}</span>
                        </span>
                    `;
                    return;
                }

                const totalCols = segDates.length;
                const truckSvg = getEntityIconSvg('checkout');
                const clapperSvg = getEntityIconSvg('project');
                const checkinSvg = getEntityIconSvg('checkin');

                let badgesHtml = '';

                // 1. JALON DÉPART (Vert)
                if (depDate) {
                    const depIdx = segDates.indexOf(depDate);
                    const depCoincides = (depDate === shootStart);
                    if (depIdx !== -1 && !depCoincides) {
                        const left = (depIdx / totalCols) * 100;
                        const width = (1 / totalCols) * 100;
                        badgesHtml += `
                            <span class="fc-phase-badge fc-phase-badge--checkout"
                                  style="left: calc(${left}% + 1px); width: calc(${width}% - 2px);"
                                  title="Départ : ${escapeHtml(depDate)}">
                                ${truckSvg}
                                <span class="fc-phase-badge__label">Départ</span>
                            </span>
                        `;
                    }
                }

                // 2. JALON TOURNAGE (Ambre)
                if (shootStart && shootEnd) {
                    const shootIndices = [];
                    segDates.forEach((d, idx) => {
                        if (d >= shootStart && d <= shootEnd) {
                            shootIndices.push(idx);
                        }
                    });

                    if (shootIndices.length > 0) {
                        const startIdx = shootIndices[0];
                        const count = shootIndices.length;
                        const left = (startIdx / totalCols) * 100;
                        const width = (count / totalCols) * 100;

                        const isFirstShootDay = (segDates[startIdx] === shootStart);
                        const isLastShootDay = (segDates[startIdx + count - 1] === shootEnd);

                        let shootPrefix = '';
                        if (depDate === shootStart && isFirstShootDay) {
                            shootPrefix = `<span class="fc-phase-coincide fc-phase-coincide--checkout" title="Départ : ${escapeHtml(depDate)}">${truckSvg}</span>`;
                        }

                        let shootSuffix = '';
                        if (retDate === shootEnd && isLastShootDay) {
                            shootSuffix = `<span class="fc-phase-coincide fc-phase-coincide--checkin" title="Retour : ${escapeHtml(retDate)}">${checkinSvg}</span>`;
                        }

                        let shootTitle = escapeHtml(projectName);
                        if (!isFirstShootDay) {
                            shootTitle += ' <span class="fc-phase-badge__suite">(suite)</span>';
                        }

                        badgesHtml += `
                            <span class="fc-phase-badge fc-phase-badge--project"
                                  style="left: calc(${left}% + 1px); width: calc(${width}% - 2px);">
                                ${shootPrefix}
                                <span class="fc-phase-badge__icon">${clapperSvg}</span>
                                <span class="fc-phase-badge__title">${shootTitle}</span>
                                ${production ? `<span class="fc-phase-badge__prod">${escapeHtml(production)}</span>` : ''}
                                ${shootSuffix}
                            </span>
                        `;
                    }
                } else if (!shootStart && !depDate && !retDate) {
                    // Projet sans dates spécifiques : occupe la cellule entière
                    badgesHtml += `
                        <span class="fc-phase-badge fc-phase-badge--project" style="left:0; width:100%;">
                            <span class="fc-phase-badge__icon">${clapperSvg}</span>
                            <span class="fc-phase-badge__title">${escapeHtml(projectName)}</span>
                        </span>
                    `;
                }

                // 3. JALON RETOUR (Bleu)
                if (retDate) {
                    const retIdx = segDates.indexOf(retDate);
                    const retCoincides = (retDate === shootEnd);
                    if (retIdx !== -1 && !retCoincides) {
                        const left = (retIdx / totalCols) * 100;
                        const width = (1 / totalCols) * 100;
                        badgesHtml += `
                            <span class="fc-phase-badge fc-phase-badge--checkin"
                                  style="left: calc(${left}% + 1px); width: calc(${width}% - 2px);"
                                  title="Retour : ${escapeHtml(retDate)}">
                                ${checkinSvg}
                                <span class="fc-phase-badge__label">Retour</span>
                            </span>
                        `;
                    }
                }

                badgesContainer.innerHTML = badgesHtml;
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

