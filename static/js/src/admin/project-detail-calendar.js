/**
 * project-detail-calendar.js — Calendrier visuel pour les projets (hub projet).
 * Conforme au design system et au calendrier de project_form.html (ProjectTimelineDatePicker).
 * - Supporte à la fois les dates continues (plage de tournage) et ponctuelles (multi-dates)
 * - Vue double mois responsive avec navigation (< et >)
 * - Rendu identique des cellules (in-shoot-range, shoot-punctual-day, Immobilisé hachuré, départ, retour, aujourd'hui)
 * - Légende compacte avec pastilles colorées
 */

(function (window, document) {
    'use strict';

    var MONTH_NAMES_FR = [
        'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
        'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
    ];

    var DAY_NAMES_FR = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];

    function parseISO(str) {
        if (!str) return null;
        var parts = str.split('-');
        if (parts.length !== 3) return null;
        return new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
    }

    function toIso(dateObj) {
        var y = dateObj.getFullYear();
        var m = String(dateObj.getMonth() + 1).padStart(2, '0');
        var d = String(dateObj.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + d;
    }

    function formatDateFrench(isoStr) {
        if (!isoStr) return '—';
        var dObj = parseISO(isoStr);
        if (!dObj || isNaN(dObj.getTime())) return isoStr;
        var dayNames = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'];
        var dayName = dayNames[dObj.getDay()];
        var mName = MONTH_NAMES_FR[dObj.getMonth()].toLowerCase();
        return dayName + ' ' + dObj.getDate() + ' ' + mName + ' ' + dObj.getFullYear();
    }

    function initProjectDetailCalendar() {
        var container = document.getElementById('projectShootCalendar');
        if (!container) return;

        var dataEl = document.getElementById('projectShootCalendarData');
        if (!dataEl) return;

        var data;
        try {
            data = JSON.parse(dataEl.textContent);
        } catch (e) {
            console.warn('projectDetailCalendar: erreur parsing JSON', e);
            return;
        }

        var isPunctual = Boolean(data.is_punctual || (data.date_mode === 'punctual'));
        var shootDates = Array.isArray(data.shoot_dates)
            ? data.shoot_dates.filter(function (d) { return typeof d === 'string' && d.trim().length > 0; }).sort()
            : [];
        var shootStart = data.shoot_start || null;
        var shootEnd = data.shoot_end || null;
        var departureDate = data.departure_date || null;
        var returnDate = data.return_date || null;
        var intervals = Array.isArray(data.inter_shoot_intervals) ? data.inter_shoot_intervals : [];

        if (!isPunctual) {
            if (shootStart && !shootEnd) shootEnd = shootStart;
            if (shootEnd && !shootStart) shootStart = shootEnd;
        }

        var hasAnyDate = isPunctual
            ? (shootDates.length > 0)
            : Boolean(shootStart || shootEnd || departureDate || returnDate);

        if (!hasAnyDate) {
            var wrapper = document.getElementById('projectShootCalendarWrapper');
            if (wrapper) wrapper.classList.add('u-d-none');
            return;
        }

        // Sets for punctual lookup
        var shootDatesSet = new Set(shootDates);
        var immobilizedDays = new Set();

        intervals.forEach(function (inter) {
            if (inter.is_immobilized !== false) {
                (inter.days || []).forEach(function (day) {
                    immobilizedDays.add(day);
                });
            }
        });

        // Date de référence pour le mois 1
        var initialIso = isPunctual
            ? (shootDates[0] || departureDate || returnDate || toIso(new Date()))
            : (shootStart || departureDate || shootEnd || returnDate || toIso(new Date()));
        var initialDate = parseISO(initialIso) || new Date();
        var currentYear = initialDate.getFullYear();
        var currentMonth = initialDate.getMonth();

        function refreshIcons() {
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                try {
                    window.lucide.createIcons({ root: container });
                } catch (e) {
                    try { window.lucide.createIcons(); } catch (err) { }
                }
            }
        }

        function renderMonthHtml(year, month, showPrev, showNext) {
            var firstDayIndex = new Date(year, month, 1).getDay(); // 0 = Dimanche
            var startOffset = (firstDayIndex + 6) % 7; // Lundi = 0
            var daysInMonth = new Date(year, month + 1, 0).getDate();
            var todayIso = toIso(new Date());

            var daysHtml = '';

            // Jours vides au début du mois
            for (var i = 0; i < startOffset; i++) {
                daysHtml += '<div class="pdp-day-cell empty"></div>';
            }

            // Jours du mois
            for (var d = 1; d <= daysInMonth; d++) {
                var dateIso = year + '-' + String(month + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
                var classes = ['pdp-day-cell'];

                if (dateIso === todayIso) {
                    classes.push('is-today');
                }

                var isDep = (departureDate === dateIso);
                var isRet = (returnDate === dateIso);
                var isShootDay = false;
                var isStandbyDay = false;

                if (isPunctual) {
                    if (shootDatesSet.has(dateIso)) {
                        classes.push('shoot-punctual-day');
                        isShootDay = true;
                    } else if (immobilizedDays.has(dateIso)) {
                        classes.push('intermediate-standby-day');
                        isStandbyDay = true;
                    }
                } else {
                    // Mode continu
                    var isShootStart = (shootStart === dateIso);
                    var isShootEnd = (shootEnd === dateIso);

                    if (shootStart && shootEnd) {
                        if (dateIso >= shootStart && dateIso <= shootEnd) {
                            classes.push('in-shoot-range');
                            isShootDay = true;
                        }
                    } else if (isShootStart || isShootEnd) {
                        classes.push('in-shoot-range');
                        isShootDay = true;
                    }

                    if (isShootStart) classes.push('shoot-start-day');
                    if (isShootEnd) classes.push('shoot-end-day');
                }

                if (isDep) classes.push('departure-day');
                if (isRet) classes.push('return-day');

                // Badges/dots en cas de chevauchement sur la même date
                var dotsHtml = '';
                var dots = [];
                if (isDep) dots.push('dot-dep');
                if (isShootDay) dots.push('dot-shoot');
                if (isRet) dots.push('dot-ret');

                if (dots.length > 1) {
                    dotsHtml = '<div class="pdp-day-badges">' +
                        dots.map(function (dt) { return '<div class="pdp-dot ' + dt + '"></div>'; }).join('') +
                        '</div>';
                }

                var titleTooltip = '';
                if (isPunctual) {
                    if (isShootDay) titleTooltip = 'Jour de tournage (' + formatDateFrench(dateIso) + ')';
                    else if (isStandbyDay) titleTooltip = 'Véhicule immobilisé (' + formatDateFrench(dateIso) + ')';
                    else if (isDep) titleTooltip = 'Prépa / Enlèvement matériel (' + formatDateFrench(dateIso) + ')';
                    else if (isRet) titleTooltip = 'Restitution matériel (' + formatDateFrench(dateIso) + ')';
                    else titleTooltip = formatDateFrench(dateIso);
                } else {
                    if (dateIso === shootStart && dateIso === shootEnd) titleTooltip = 'Jour de tournage (' + formatDateFrench(dateIso) + ')';
                    else if (dateIso === shootStart) titleTooltip = 'Début du tournage (' + formatDateFrench(dateIso) + ')';
                    else if (dateIso === shootEnd) titleTooltip = 'Fin du tournage (' + formatDateFrench(dateIso) + ')';
                    else if (isShootDay) titleTooltip = 'Période de tournage (' + formatDateFrench(dateIso) + ')';
                    else if (isDep) titleTooltip = 'Prépa / Enlèvement matériel (' + formatDateFrench(dateIso) + ')';
                    else if (isRet) titleTooltip = 'Restitution matériel (' + formatDateFrench(dateIso) + ')';
                    else titleTooltip = formatDateFrench(dateIso);
                }

                daysHtml += '<div class="' + classes.join(' ') + '" data-date="' + dateIso + '" title="' + titleTooltip + '">' +
                    '<span>' + d + '</span>' +
                    dotsHtml +
                    '</div>';
            }

            var prevActionHtml = showPrev
                ? '<button type="button" class="pdp-nav-btn pdc-prev-btn" title="Mois précédent"><i data-lucide="chevron-left"></i></button>'
                : '<div class="pdp-nav-spacer"></div>';

            var nextActionHtml = showNext
                ? '<button type="button" class="pdp-nav-btn pdc-next-btn" title="Mois suivant"><i data-lucide="chevron-right"></i></button>'
                : '<div class="pdp-nav-spacer"></div>';

            return '<div class="pdp-month-card">' +
                '<div class="pdp-month-header">' +
                prevActionHtml +
                '<div class="pdp-month-title">' + MONTH_NAMES_FR[month] + ' ' + year + '</div>' +
                nextActionHtml +
                '</div>' +
                '<div class="pdp-weekdays">' +
                DAY_NAMES_FR.map(function (w) { return '<div>' + w + '</div>'; }).join('') +
                '</div>' +
                '<div class="pdp-days-grid">' +
                daysHtml +
                '</div>' +
                '</div>';
        }

        function render() {
            var m1Year = currentYear;
            var m1Month = currentMonth;

            var m2Year = m1Year;
            var m2Month = m1Month + 1;
            if (m2Month > 11) {
                m2Month = 0;
                m2Year++;
            }

            // Calendar viewport (double mois côte à côte)
            var calendarViewportHtml = '<div class="pdp-calendar-container" id="pdp-calendar-viewport">' +
                renderMonthHtml(m1Year, m1Month, true, false) +
                renderMonthHtml(m2Year, m2Month, false, true) +
                '</div>';

            // Legend
            var legendSwatchesHtml = '';

            if (departureDate) {
                legendSwatchesHtml += '<div class="pdp-legend-item">' +
                    '<div class="pdp-legend-swatch swatch-dep"></div>' +
                    '<span>Prépa / Enlèvement</span>' +
                    '</div>';
            }

            if (isPunctual ? shootDates.length > 0 : (shootStart || shootEnd)) {
                legendSwatchesHtml += '<div class="pdp-legend-item">' +
                    '<div class="pdp-legend-swatch swatch-shoot"></div>' +
                    '<span>Tournage</span>' +
                    '</div>';
            }

            if (isPunctual) {
                if (immobilizedDays.size > 0) {
                    legendSwatchesHtml += '<div class="pdp-legend-item">' +
                        '<div class="pdp-legend-swatch swatch-standby"></div>' +
                        '<span>Immobilisé</span>' +
                        '</div>';
                }
            }

            if (returnDate) {
                legendSwatchesHtml += '<div class="pdp-legend-item">' +
                    '<div class="pdp-legend-swatch swatch-ret"></div>' +
                    '<span>Retour matériel</span>' +
                    '</div>';
            }

            var legendHtml = '<div class="pdp-footer-legend">' +
                '<div class="pdp-legend-items">' +
                legendSwatchesHtml +
                '</div>' +
                '<div class="pdp-legend-hint">' +
                'Survolez un jour pour afficher les détails du planning.' +
                '</div>' +
                '</div>';

            // Conservé tel que modifié par l'utilisateur : affichage direct du viewport + légende
            container.innerHTML = calendarViewportHtml + legendHtml;

            // Bind click handlers pour la navigation des mois
            var prevBtn = container.querySelector('.pdc-prev-btn');
            var nextBtn = container.querySelector('.pdc-next-btn');

            if (prevBtn) {
                prevBtn.addEventListener('click', function (e) {
                    e.preventDefault();
                    currentMonth--;
                    if (currentMonth < 0) {
                        currentMonth = 11;
                        currentYear--;
                    }
                    render();
                });
            }

            if (nextBtn) {
                nextBtn.addEventListener('click', function (e) {
                    e.preventDefault();
                    currentMonth++;
                    if (currentMonth > 11) {
                        currentMonth = 0;
                        currentYear++;
                    }
                    render();
                });
            }

            refreshIcons();
        }

        render();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initProjectDetailCalendar);
    } else {
        initProjectDetailCalendar();
    }

})(window, document);
