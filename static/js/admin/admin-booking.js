/**
 * admin-booking.js — Calendrier de Booking Matériel (Gantt)
 * Stylisé selon le modèle du calendrier du Dashboard et le Design System Belle Vitesse.
 */

$(document).ready(function () {
    // ── Configuration & State ──
    let currentDate = new Date(); // Date de référence (défaut: aujourd'hui)
    let currentCategory = 'vehicle'; // Catégorie courante ('vehicle' ou 'head')
    let selectedItemId = ''; // ID de l'équipement sélectionné (optionnel)
    const DAY_COLUMN_WIDTH = 50; // Largeur d'une colonne jour en pixels

    // Noms des jours et mois en français
    const MONTH_NAMES = [
        "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
    ];
    const DAY_NAMES = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"];

    // ── Helper SVG Lucide ──
    function getLucideSvg(type) {
        if (type === 'checkout') {
            // Lucide 'truck' (Départ - Vert Émeraude)
            return '<svg class="gantt-bar__icon" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18.5" r="2.5"/><circle cx="7" cy="18.5" r="2.5"/></svg>';
        }
        if (type === 'checkin') {
            // Lucide 'package-check' (Retour - Bleu Océan)
            return '<svg class="gantt-bar__icon" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 16 2 2 4-4"/><path d="M21 10V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l2-1.14"/><path d="m7.5 4.27 9 5.15"/><polyline points="3.29 7 12 12 20.71 7"/><line x1="12" x2="12" y1="22" y2="12"/></svg>';
        }
        if (type === 'project') {
            // Lucide 'clapperboard' (Tournage - Ambre Chaud)
            return '<svg class="gantt-bar__icon" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.2 6 3 11l-.9-2.4 17.2-5z"/><path d="m6.2 5.3 3.1 3.9"/><path d="m12.4 3.4 3.1 4"/><path d="M3 11h18v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>';
        }
        if (type === 'conflict') {
            // Lucide 'alert-triangle'
            return '<svg class="gantt-bar__icon" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
        }
        if (type === 'standby' || type === 'immob') {
            // Lucide 'pause-circle' (Immobilisé - Standby)
            return '<svg class="gantt-bar__icon" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="10" x2="10" y1="15" y2="9"/><line x1="14" x2="14" y1="15" y2="9"/></svg>';
        }
        return '';
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Initialisation Select2
    $('#itemSelect').select2({
        width: '100%',
        language: 'fr'
    });

    // ── Changement de catégorie (Filter Pills comme sur le Dashboard) ──
    $('.category-filter-btn').on('click', function () {
        $('.category-filter-btn').removeClass('active admin-btn-primary').addClass('admin-btn-quaternary');
        $(this).addClass('active admin-btn-primary').removeClass('admin-btn-quaternary');

        currentCategory = $(this).data('category');
        selectedItemId = ''; // Reset le filtre spécifique
        $('#itemSelect').val(null).trigger('change');
        loadFiltersAndDraw();
    });

    // Navigation mois précédent
    $('#prevMonthBtn').on('click', function () {
        currentDate.setMonth(currentDate.getMonth() - 1);
        renderTimelineGrid();
        fetchAndRenderBookings();
    });

    // Navigation mois suivant
    $('#nextMonthBtn').on('click', function () {
        currentDate.setMonth(currentDate.getMonth() + 1);
        renderTimelineGrid();
        fetchAndRenderBookings();
    });

    // Retour au mois d'aujourd'hui
    $('#todayBtn').on('click', function () {
        currentDate = new Date();
        renderTimelineGrid();
        fetchAndRenderBookings();
    });

    // Tooltip positionnement dynamique
    const $tooltip = $('#ganttTooltip');
    $(document).on('mousemove', '.gantt-booking-bar', function (e) {
        $tooltip.css({
            left: e.pageX + 15 + 'px',
            top: e.pageY + 15 + 'px'
        });
    });

    // Synchronisation du survol entre ligne d'équipement (sidebar) et ligne de grille (timeline)
    $(document).on('mouseenter', '.gantt-sidebar-row', function () {
        const itemId = $(this).data('item-id');
        $(`.gantt-grid-row[data-item-id="${itemId}"]`).addClass('is-hovered');
        $(this).addClass('is-hovered');
    }).on('mouseleave', '.gantt-sidebar-row', function () {
        const itemId = $(this).data('item-id');
        $(`.gantt-grid-row[data-item-id="${itemId}"]`).removeClass('is-hovered');
        $(this).removeClass('is-hovered');
    });

    $(document).on('mouseenter', '.gantt-grid-row', function () {
        const itemId = $(this).data('item-id');
        $(`.gantt-sidebar-row[data-item-id="${itemId}"]`).addClass('is-hovered');
        $(this).addClass('is-hovered');
    }).on('mouseleave', '.gantt-grid-row', function () {
        const itemId = $(this).data('item-id');
        $(`.gantt-sidebar-row[data-item-id="${itemId}"]`).removeClass('is-hovered');
        $(this).removeClass('is-hovered');
    });

    // ── Chargement des Filtres et Données ──
    loadFiltersAndDraw();

    function loadFiltersAndDraw() {
        $.getJSON('/admin/api/booking-data', { category: currentCategory, t: Date.now() }, function (data) {
            const $select = $('#itemSelect');

            $select.off('change');
            $select.empty().append('<option value="">— Tous les équipements —</option>');

            data.items.forEach(function (item) {
                $select.append(new Option(item.name, item.id));
            });

            $select.val(selectedItemId || '').trigger('change.select2');

            $select.on('change', function () {
                selectedItemId = $(this).val() || '';
                fetchAndRenderBookings();
            });

            renderTimelineGrid();
            fetchAndRenderBookings();
        });
    }

    // Calcule le nombre de jours dans le mois de currentDate
    function getDaysInMonth(year, month) {
        return new Date(year, month + 1, 0).getDate();
    }

    // Dessine l'en-tête et les cellules de fond de la timeline
    function renderTimelineGrid() {
        const year = currentDate.getFullYear();
        const month = currentDate.getMonth();
        const daysCount = getDaysInMonth(year, month);
        const today = new Date();

        // Mettre à jour l'affichage du mois courant
        $('#monthDisplay').text(`${MONTH_NAMES[month]} ${year}`);

        const $header = $('#ganttTimelineHeader');
        $header.css('grid-template-columns', `repeat(${daysCount}, ${DAY_COLUMN_WIDTH}px)`);
        $header.css('width', `${daysCount * DAY_COLUMN_WIDTH}px`);
        $header.empty();

        let headerHtml = '';
        for (let day = 1; day <= daysCount; day++) {
            const dateObj = new Date(year, month, day);
            const dayName = DAY_NAMES[dateObj.getDay()];
            const isWeekend = dateObj.getDay() === 0 || dateObj.getDay() === 6;
            const isToday = dateObj.getDate() === today.getDate() &&
                dateObj.getMonth() === today.getMonth() &&
                dateObj.getFullYear() === today.getFullYear();

            const weekendClass = isWeekend ? 'weekend' : '';
            const todayClass = isToday ? 'today' : '';

            headerHtml += `
                <div class="gantt-header-day ${weekendClass} ${todayClass}">
                    <span class="day-name">${dayName}</span>
                    <span class="day-num">${day}</span>
                </div>
            `;
        }
        $header.append(headerHtml);

        if (window.lucide) {
            lucide.createIcons();
        }
    }

    // Parse une chaine de date "YYYY-MM-DD" en date locale
    function parseLocalDate(dateStr) {
        if (!dateStr) return null;
        const parts = dateStr.split('-');
        return new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
    }

    // Récupère les données de booking et les dessine sur la grille
    function fetchAndRenderBookings() {
        const year = currentDate.getFullYear();
        const month = currentDate.getMonth();
        const daysCount = getDaysInMonth(year, month);

        const params = {
            category: currentCategory,
            item_id: selectedItemId,
            t: Date.now()
        };

        $.getJSON('/admin/api/booking-data', params, function (data) {
            const $sidebar = $('#ganttSidebarRows');
            const $grid = $('#ganttTimelineGrid');

            $sidebar.empty();
            $grid.empty();

            if (!data.items || data.items.length === 0) {
                $sidebar.append('<div class="gantt-sidebar-empty">Aucun matériel dans cette catégorie</div>');
                $grid.append(`<div class="gantt-grid-row" style="width: ${daysCount * DAY_COLUMN_WIDTH}px;"></div>`);
                return;
            }

            // Créer les rangées d'équipements
            data.items.forEach(function (item) {
                $sidebar.append(`
                    <div class="gantt-sidebar-row" data-item-id="${item.id}" title="${escapeHtml(item.name)}">
                        ${escapeHtml(item.name)}
                    </div>
                `);

                let rowCellsHtml = '';
                const today = new Date();
                for (let day = 1; day <= daysCount; day++) {
                    const dateObj = new Date(year, month, day);
                    const isWeekend = dateObj.getDay() === 0 || dateObj.getDay() === 6;
                    const isToday = dateObj.getDate() === today.getDate() &&
                        dateObj.getMonth() === today.getMonth() &&
                        dateObj.getFullYear() === today.getFullYear();

                    const weekendClass = isWeekend ? 'weekend' : '';
                    const todayClass = isToday ? 'today' : '';

                    rowCellsHtml += `<div class="gantt-grid-cell ${weekendClass} ${todayClass}"></div>`;
                }

                $grid.append(`
                    <div class="gantt-grid-row" data-item-id="${item.id}" style="width: ${daysCount * DAY_COLUMN_WIDTH}px;">
                        ${rowCellsHtml}
                    </div>
                `);
            });

            // Détection et marquage des conflits de booking
            detectAndMarkConflicts(data.bookings);

            const monthStart = new Date(year, month, 1);
            const monthEnd = new Date(year, month, daysCount);

            data.bookings.forEach(function (booking) {
                const bookStart = parseLocalDate(booking.start.split('T')[0]);
                const bookEnd = parseLocalDate(booking.end.split('T')[0]);

                if (!bookStart || !bookEnd) return;
                if (bookEnd < monthStart || bookStart > monthEnd) return;

                const $row = $grid.find(`.gantt-grid-row[data-item-id="${booking.item_id}"]`);
                if ($row.length === 0) return;

                function getPosAndWidth(dStart, dEnd) {
                    if (!dStart || !dEnd) return null;
                    if (dEnd < monthStart || dStart > monthEnd) return null;

                    const rStart = dStart < monthStart ? monthStart : dStart;
                    const rEnd = dEnd > monthEnd ? monthEnd : dEnd;

                    const startDay = rStart.getDate();
                    const diffTime = rEnd.getTime() - rStart.getTime();
                    const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24)) + 1;

                    const left = (startDay - 1) * DAY_COLUMN_WIDTH + 2;
                    const width = (diffDays * DAY_COLUMN_WIDTH) - 4;

                    return { left, width };
                }

                const depD = booking.departure_date ? parseLocalDate(booking.departure_date.split('T')[0]) : null;
                const retD = booking.return_date ? parseLocalDate(booking.return_date.split('T')[0]) : null;
                const sStart = booking.shoot_start ? parseLocalDate(booking.shoot_start.split('T')[0]) : null;
                const sEnd = booking.shoot_end ? parseLocalDate(booking.shoot_end.split('T')[0]) : sStart;

                function buildTooltipHtml() {
                    let phases = '';
                    if (depD) {
                        phases += `
                            <div class="gantt-tooltip__phase">
                                <span class="gantt-tooltip__phase-badge gantt-tooltip__phase-badge--checkout">${getLucideSvg('checkout')}</span>
                                <span><strong>Départ :</strong> ${formatDateString(depD)}</span>
                            </div>
                        `;
                    }

                    if (booking.date_mode === 'punctual' && Array.isArray(booking.shoot_dates) && booking.shoot_dates.length > 0) {
                        const shootDatesFormatted = booking.shoot_dates.map(function (dStr) {
                            const d = parseLocalDate(String(dStr).split('T')[0]);
                            return d ? formatDateString(d) : dStr;
                        });
                        const count = shootDatesFormatted.length;
                        phases += `
                            <div class="gantt-tooltip__phase">
                                <span class="gantt-tooltip__phase-badge gantt-tooltip__phase-badge--project">${getLucideSvg('project')}</span>
                                <span><strong>Tournage (${count}j) :</strong> ${shootDatesFormatted.join(', ')}</span>
                            </div>
                        `;

                        // Afficher les détails des intervalles (immobilisés / non-immobilisés)
                        if (Array.isArray(booking.intervals) && booking.intervals.length > 0) {
                            booking.intervals.forEach(function (inter) {
                                const iStart = parseLocalDate(inter.start);
                                const iEnd = parseLocalDate(inter.end);
                                const daysCount = inter.days_count || (inter.days ? inter.days.length : 0);
                                if (iStart && iEnd && daysCount > 0) {
                                    if (inter.is_immobilized) {
                                        phases += `
                                            <div class="gantt-tooltip__phase gantt-tooltip__phase--immob">
                                                <span class="gantt-tooltip__phase-badge gantt-tooltip__phase-badge--standby">${getLucideSvg('standby')}</span>
                                                <span><strong>Immobilisé sur place (${daysCount}j) :</strong> entre le ${formatDateString(iStart)} et le ${formatDateString(iEnd)}</span>
                                            </div>
                                        `;
                                    } else {
                                        phases += `
                                            <div class="gantt-tooltip__phase gantt-tooltip__phase--free">
                                                <span class="gantt-tooltip__phase-badge gantt-tooltip__phase-badge--checkout">${getLucideSvg('checkout')}</span>
                                                <span class="u-text-muted"><strong>Libéré / Atelier (${daysCount}j) :</strong> entre le ${formatDateString(iStart)} et le ${formatDateString(iEnd)}</span>
                                            </div>
                                        `;
                                    }
                                }
                            });
                        }
                    } else if (sStart) {
                        const shootLabel = sEnd && sEnd.getTime() !== sStart.getTime()
                            ? `${formatDateString(sStart)} → ${formatDateString(sEnd)}`
                            : formatDateString(sStart);
                        phases += `
                            <div class="gantt-tooltip__phase">
                                <span class="gantt-tooltip__phase-badge gantt-tooltip__phase-badge--project">${getLucideSvg('project')}</span>
                                <span><strong>Tournage :</strong> ${shootLabel}</span>
                            </div>
                        `;
                    }

                    if (retD) {
                        phases += `
                            <div class="gantt-tooltip__phase">
                                <span class="gantt-tooltip__phase-badge gantt-tooltip__phase-badge--checkin">${getLucideSvg('checkin')}</span>
                                <span><strong>Retour :</strong> ${formatDateString(retD)}</span>
                            </div>
                        `;
                    }

                    return `
                        <div class="gantt-tooltip__title">${escapeHtml(booking.project_name)}</div>
                        ${booking.production && booking.production !== '—' ? `<div class="gantt-tooltip__prod">Production : ${escapeHtml(booking.production)}</div>` : ''}
                        <div class="gantt-tooltip__phases">${phases}</div>
                        <div class="gantt-tooltip__footer">↗ Ouvrir le projet</div>
                    `;
                }

                const tooltipHtml = buildTooltipHtml();

                function createBarElement(dateS, dateE, contentHtml, extraClass, titleText) {
                    const pos = getPosAndWidth(dateS, dateE);
                    if (!pos) return null;

                    const conflictClass = booking.hasConflict ? 'has-conflict' : '';

                    const $bar = $(`
                        <div class="gantt-booking-bar ${extraClass} ${conflictClass}"
                             style="left: ${pos.left}px; width: ${pos.width}px;"
                             data-project-code="${escapeHtml(booking.project_code || '')}"
                             title="${escapeHtml(titleText || '')}">
                             ${contentHtml}
                        </div>
                    `);

                    $bar.on('click', function () {
                        const q = $(this).attr('data-project-code') || booking.project_code || '';
                        window.open(`/admin/projects?q=${encodeURIComponent(q)}`, '_blank');
                    });

                    $bar.hover(
                        function () { $tooltip.html(tooltipHtml).show(); },
                        function () { $tooltip.hide(); }
                    );

                    return $bar;
                }

                // 1. Lignes de connexion (périodes de réservation effectives / spans continus)
                const spans = (Array.isArray(booking.active_spans) && booking.active_spans.length > 0)
                    ? booking.active_spans
                    : [{ start: booking.start, end: booking.end }];

                spans.forEach(function (span) {
                    const spanS = parseLocalDate(span.start.split('T')[0]);
                    const spanE = parseLocalDate(span.end.split('T')[0]);
                    const spanPos = getPosAndWidth(spanS, spanE);
                    if (spanPos) {
                        const $connLine = $(`
                            <div class="gantt-booking-connection"
                                 style="left: ${spanPos.left}px; width: ${spanPos.width}px;">
                            </div>
                        `);
                        $row.append($connLine);
                    }
                });

                if (booking.date_mode === 'punctual' && Array.isArray(booking.shoot_dates) && booking.shoot_dates.length > 0) {
                    // ── Mode Ponctuel ──
                    // 1. Trier et regrouper les dates de tournage consécutives en blocs
                    const sortedShootDates = booking.shoot_dates
                        .map(function (dStr) { return String(dStr).trim(); })
                        .filter(Boolean)
                        .sort();

                    const shootChunks = [];
                    let curChunk = [];

                    sortedShootDates.forEach(function (dStr) {
                        const dObj = parseLocalDate(dStr.split('T')[0]);
                        if (!dObj) return;

                        if (curChunk.length === 0) {
                            curChunk.push(dObj);
                        } else {
                            const lastD = curChunk[curChunk.length - 1];
                            const diff = Math.round((dObj.getTime() - lastD.getTime()) / (1000 * 60 * 60 * 24));
                            if (diff === 1) {
                                curChunk.push(dObj);
                            } else {
                                shootChunks.push([...curChunk]);
                                curChunk = [dObj];
                            }
                        }
                    });
                    if (curChunk.length > 0) {
                        shootChunks.push(curChunk);
                    }

                    const firstShootDateObj = sortedShootDates.length > 0 ? parseLocalDate(sortedShootDates[0].split('T')[0]) : null;
                    const lastShootDateObj = sortedShootDates.length > 0 ? parseLocalDate(sortedShootDates[sortedShootDates.length - 1].split('T')[0]) : null;

                    // 2. Dessiner chaque bloc de tournage
                    shootChunks.forEach(function (chunk) {
                        const cStart = chunk[0];
                        const cEnd = chunk[chunk.length - 1];

                        let depIconIfCoincides = (depD && depD.getTime() === cStart.getTime()) ? getLucideSvg('checkout') + ' ' : '';
                        let retIconIfCoincides = (retD && retD.getTime() === cEnd.getTime()) ? ' ' + getLucideSvg('checkin') : '';

                        const shootContent = `
                            <span class="gantt-bar-badge">${depIconIfCoincides}${getLucideSvg('project')}</span>
                            <span class="gantt-bar-title">${escapeHtml(booking.project_name)}</span>
                            ${booking.production && booking.production !== '—' ? `<span class="gantt-bar-prod">${escapeHtml(booking.production)}</span>` : ''}
                            ${retIconIfCoincides}
                        `;
                        const rangeStr = chunk.length > 1 ? `du ${formatDateString(cStart)} au ${formatDateString(cEnd)}` : formatDateString(cStart);
                        const $shootBar = createBarElement(cStart, cEnd, shootContent, 'gantt-shoot-bar', `Tournage : ${booking.project_name} (${rangeStr})`);
                        if ($shootBar) $row.append($shootBar);
                    });

                    // 3. Dessiner les intervalles immobilisés (🔒  Immobilisé sur place)
                    if (Array.isArray(booking.intervals) && booking.intervals.length > 0) {
                        booking.intervals.forEach(function (inter) {
                            // On n'affiche QUE les intervalles immobilisés.
                            // Les intervalles non-immobilisés (libérés / retour atelier) NE SONT PAS DESSINÉS,
                            // laissant les cellules totalement libres sur le calendrier matériel.
                            if (!inter.is_immobilized || !Array.isArray(inter.days) || inter.days.length === 0) {
                                return;
                            }

                            const interSorted = inter.days
                                .map(function (dStr) { return parseLocalDate(String(dStr).split('T')[0]); })
                                .filter(Boolean)
                                .sort(function (a, b) { return a.getTime() - b.getTime(); });
                            if (interSorted.length === 0) return;

                            // Regrouper les jours consécutifs de l'intervalle au cas où
                            const immobChunks = [];
                            let curImmobChunk = [];
                            interSorted.forEach(function (dObj) {
                                if (curImmobChunk.length === 0) {
                                    curImmobChunk.push(dObj);
                                } else {
                                    const lastD = curImmobChunk[curImmobChunk.length - 1];
                                    const diff = Math.round((dObj.getTime() - lastD.getTime()) / (1000 * 60 * 60 * 24));
                                    if (diff === 1) {
                                        curImmobChunk.push(dObj);
                                    } else {
                                        immobChunks.push([...curImmobChunk]);
                                        curImmobChunk = [dObj];
                                    }
                                }
                            });
                            if (curImmobChunk.length > 0) immobChunks.push(curImmobChunk);

                            immobChunks.forEach(function (chunk) {
                                const iStart = chunk[0];
                                const iEnd = chunk[chunk.length - 1];
                                const count = chunk.length;

                                const immobContent = `
                                    <span class="gantt-bar-badge">${getLucideSvg('standby')}</span>
                                    <span class="gantt-bar-title">${escapeHtml(booking.project_name)}</span>
                                    <span class="gantt-bar-label">Immobilisé${count > 1 ? ` (${count}j)` : ''}</span>
                                `;
                                const rangeStr = count > 1 ? `du ${formatDateString(iStart)} au ${formatDateString(iEnd)}` : formatDateString(iStart);
                                const $immobBar = createBarElement(iStart, iEnd, immobContent, 'gantt-immob-bar', `Immobilisé sur place (${count}j) : ${booking.project_name} (${rangeStr})`);
                                if ($immobBar) $row.append($immobBar);
                            });
                        });
                    }

                    // 4. Jalon Départ (Vert Émeraude - si strictement avant le 1er tournage)
                    if (depD && firstShootDateObj && depD.getTime() < firstShootDateObj.getTime()) {
                        const depPos = getPosAndWidth(depD, depD);
                        const showText = depPos && depPos.width >= 65;
                        const depContent = `
                            <span class="gantt-bar-badge">${getLucideSvg('checkout')}</span>
                            ${showText ? '<span class="gantt-bar-title">Départ</span>' : ''}
                        `;
                        const $depBar = createBarElement(depD, depD, depContent, 'gantt-dep-bar', `Départ : ${booking.project_name}`);
                        if ($depBar) $row.append($depBar);
                    }

                    // 5. Jalon Retour (Bleu Océan - si strictement après le dernier tournage)
                    if (retD && lastShootDateObj && retD.getTime() > lastShootDateObj.getTime()) {
                        const retPos = getPosAndWidth(retD, retD);
                        const showText = retPos && retPos.width >= 65;
                        const retContent = `
                            <span class="gantt-bar-badge">${getLucideSvg('checkin')}</span>
                            ${showText ? '<span class="gantt-bar-title">Retour</span>' : ''}
                        `;
                        const $retBar = createBarElement(retD, retD, retContent, 'gantt-ret-bar', `Retour : ${booking.project_name}`);
                        if ($retBar) $row.append($retBar);
                    }

                } else {
                    // ── Mode Continu Classique ──
                    const hasAnyPhaseDate = depD || sStart || retD;
                    const drawDepBlock = depD && (!sStart || depD.getTime() < sStart.getTime());
                    const drawRetBlock = retD && (!sEnd || retD.getTime() > sEnd.getTime());
                    const drawShootBlock = !!sStart;

                    // Fallback si aucune phase spécifique
                    if (!hasAnyPhaseDate) {
                        const fallbackContent = `
                            <span class="gantt-bar-badge">${getLucideSvg('project')}</span>
                            <span class="gantt-bar-title">${escapeHtml(booking.project_name)}</span>
                        `;
                        const $fallback = createBarElement(bookStart, bookEnd, fallbackContent, 'gantt-shoot-bar', `Tournage : ${booking.project_name}`);
                        if ($fallback) $row.append($fallback);
                        return;
                    }

                    // 2. Bloc Départ (Check-out) — Vert Émeraude
                    if (drawDepBlock) {
                        const depPos = getPosAndWidth(depD, depD);
                        const showText = depPos && depPos.width >= 65;
                        const depContent = `
                            <span class="gantt-bar-badge">${getLucideSvg('checkout')}</span>
                            ${showText ? '<span class="gantt-bar-title">Départ</span>' : ''}
                        `;
                        const $depBar = createBarElement(depD, depD, depContent, 'gantt-dep-bar', `Départ : ${booking.project_name}`);
                        if ($depBar) $row.append($depBar);
                    }

                    // 3. Bloc Tournage (Projet) — Ambre Chaud
                    if (drawShootBlock) {
                        let shootBadgeSvg = getLucideSvg('project');
                        let depIconIfCoincides = (depD && depD.getTime() === sStart.getTime()) ? getLucideSvg('checkout') + ' ' : '';
                        let retIconIfCoincides = (retD && sEnd && retD.getTime() === sEnd.getTime()) ? ' ' + getLucideSvg('checkin') : '';

                        const shootContent = `
                            <span class="gantt-bar-badge">${depIconIfCoincides}${shootBadgeSvg}</span>
                            <span class="gantt-bar-title">${escapeHtml(booking.project_name)}</span>
                            ${booking.production && booking.production !== '—' ? `<span class="gantt-bar-prod">${escapeHtml(booking.production)}</span>` : ''}
                            ${retIconIfCoincides}
                        `;
                        const $shootBar = createBarElement(sStart, sEnd, shootContent, 'gantt-shoot-bar', `Tournage : ${booking.project_name}`);
                        if ($shootBar) $row.append($shootBar);
                    }

                    // 4. Bloc Retour (Check-in) — Bleu Océan
                    if (drawRetBlock) {
                        const retPos = getPosAndWidth(retD, retD);
                        const showText = retPos && retPos.width >= 65;
                        const retContent = `
                            <span class="gantt-bar-badge">${getLucideSvg('checkin')}</span>
                            ${showText ? '<span class="gantt-bar-title">Retour</span>' : ''}
                        `;
                        const $retBar = createBarElement(retD, retD, retContent, 'gantt-ret-bar', `Retour : ${booking.project_name}`);
                        if ($retBar) $row.append($retBar);
                    }
                }
            });

            if (window.lucide) {
                lucide.createIcons();
            }
        });
    }

    // Formatage des dates en chaines lisibles (ex: "20 Mai 2026")
    function formatDateString(date) {
        return `${date.getDate()} ${MONTH_NAMES[date.getMonth()]} ${date.getFullYear()}`;
    }

    // Détection des conflits temporels (Overlaps sur les spans actifs)
    function detectAndMarkConflicts(bookings) {
        if (!bookings) return;
        const bookingsByItem = {};
        bookings.forEach(function (b) {
            if (!bookingsByItem[b.item_id]) {
                bookingsByItem[b.item_id] = [];
            }
            bookingsByItem[b.item_id].push(b);
        });

        Object.keys(bookingsByItem).forEach(function (itemId) {
            const list = bookingsByItem[itemId];
            for (let i = 0; i < list.length; i++) {
                for (let j = i + 1; j < list.length; j++) {
                    const b1 = list[i];
                    const b2 = list[j];
                    if (b1.project_id === b2.project_id) continue;

                    const b1Spans = (Array.isArray(b1.active_spans) && b1.active_spans.length > 0)
                        ? b1.active_spans
                        : [{ start: b1.start, end: b1.end }];
                    const b2Spans = (Array.isArray(b2.active_spans) && b2.active_spans.length > 0)
                        ? b2.active_spans
                        : [{ start: b2.start, end: b2.end }];

                    let conflictFound = false;
                    for (let s1Idx = 0; s1Idx < b1Spans.length; s1Idx++) {
                        const s1 = b1Spans[s1Idx];
                        const s1Start = parseLocalDate(s1.start.split('T')[0]);
                        const s1End = parseLocalDate(s1.end.split('T')[0]);
                        if (!s1Start || !s1End) continue;

                        for (let s2Idx = 0; s2Idx < b2Spans.length; s2Idx++) {
                            const s2 = b2Spans[s2Idx];
                            const s2Start = parseLocalDate(s2.start.split('T')[0]);
                            const s2End = parseLocalDate(s2.end.split('T')[0]);
                            if (!s2Start || !s2End) continue;

                            if (s1Start <= s2End && s2Start <= s1End) {
                                conflictFound = true;
                                break;
                            }
                        }
                        if (conflictFound) break;
                    }

                    if (conflictFound) {
                        b1.hasConflict = true;
                        b2.hasConflict = true;
                    }
                }
            }
        });
    }
});
