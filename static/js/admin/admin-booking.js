$(document).ready(function () {
    // ── Configuration & State ──
    let currentDate = new Date(); // Date de référence (défaut: aujourd'hui)
    let currentCategory = 'vehicle'; // Catégorie courante ('vehicle' ou 'head')
    let selectedItemId = ''; // ID de l'équipement sélectionné (optionnel)
    const DAY_COLUMN_WIDTH = 40; // Largeur d'une colonne jour en pixels

    // Noms des jours et mois en français
    const MONTH_NAMES = [
        "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
    ];
    const DAY_NAMES = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"];

    // Initialisation Select2
    $('#itemSelect').select2({
        width: '100%'
    });

    // ── Initialisation & Event Listeners ──
    loadFiltersAndDraw();

    // Changement de catégorie (Tabs)
    $('.tab-btn').on('click', function () {
        $('.tab-btn').removeClass('active');
        $(this).addClass('active');
        currentCategory = $(this).data('category');
        selectedItemId = ''; // Reset le filtre spécifique
        $('#itemSelect').val(null).trigger('change');
        loadFiltersAndDraw();
    });

    // Initialisation & Event Listeners
    loadFiltersAndDraw();

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

    // Tooltip Follow Mouse
    const $tooltip = $('#ganttTooltip');
    $(document).on('mousemove', '.gantt-booking-bar', function (e) {
        $tooltip.css({
            left: e.pageX + 15 + 'px',
            top: e.pageY + 15 + 'px'
        });
    });

    // ── Fonctions Principales ──

    function loadFiltersAndDraw() {
        $.getJSON('/admin/api/booking-data', { category: currentCategory, t: Date.now() }, function (data) {
            // Remplir le dropdown
            const $select = $('#itemSelect');

            // Désactiver l'écouteur d'événement pour éviter la double requête lors de la mise à jour
            $select.off('change');

            $select.empty().append('<option value="">— Tous —</option>');
            data.items.forEach(function (item) {
                $select.append(new Option(item.name, item.id));
            });

            $select.val(selectedItemId || '').trigger('change.select2');

            // Ré-attacher l'écouteur d'événement après remplissage
            $select.on('change', function () {
                selectedItemId = $(this).val() || '';
                fetchAndRenderBookings();
            });

            // Dessiner la timeline et charger les bookings
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

        // Définir la structure CSS Grid pour le header
        const $header = $('#ganttTimelineHeader');
        $header.css('grid-template-columns', `repeat(${daysCount}, ${DAY_COLUMN_WIDTH}px)`);
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
                    <span class="day-num">${day}</span>
                    <span class="day-name">${dayName}</span>
                </div>
            `;
        }
        $header.append(headerHtml);
    }

    // Parse une chaine de date "YYYY-MM-DD" en date locale
    function parseLocalDate(dateStr) {
        if (!dateStr) return null;
        const parts = dateStr.split('-');
        return new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
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

            // S'il n'y a aucun équipement correspondant
            if (data.items.length === 0) {
                $sidebar.append('<div class="gantt-sidebar-row" style="color: var(--grey-2); font-style: italic;">Aucun matériel</div>');
                $grid.append(`<div class="gantt-grid-row" style="width: ${daysCount * DAY_COLUMN_WIDTH}px;"></div>`);
                return;
            }


            // Créer les rangées d'équipements
            data.items.forEach(function (item) {
                // Sidebar
                $sidebar.append(`
                    <div class="gantt-sidebar-row" title="${item.name}">
                        ${item.name}
                    </div>
                `);

                // Timeline Background Row
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

            // Détection et marquage des conflits de booking (chevauchement de dates par équipement)
            detectAndMarkConflicts(data.bookings);

            const monthStart = new Date(year, month, 1);
            const monthEnd = new Date(year, month, daysCount);

            data.bookings.forEach(function (booking) {
                // Parse local dates to avoid timezone shifts
                const bookStart = parseLocalDate(booking.start.split('T')[0]);
                const bookEnd = parseLocalDate(booking.end.split('T')[0]);

                if (!bookStart || !bookEnd) return;

                // Si le booking n'a aucun jour en commun avec le mois sélectionné, on passe
                if (bookEnd < monthStart || bookStart > monthEnd) {
                    return;
                }

                // Trouver la ligne correspondante à cet équipement
                const $row = $grid.find(`.gantt-grid-row[data-item-id="${booking.item_id}"]`);
                if ($row.length === 0) return;

                // Helper pour calculer la position et largeur d'une plage de dates dans le mois
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

                // Parse des dates individuelles
                const depD = booking.departure_date ? parseLocalDate(booking.departure_date.split('T')[0]) : null;
                const retD = booking.return_date ? parseLocalDate(booking.return_date.split('T')[0]) : null;
                const sStart = booking.shoot_start ? parseLocalDate(booking.shoot_start.split('T')[0]) : null;
                const sEnd = booking.shoot_end ? parseLocalDate(booking.shoot_end.split('T')[0]) : sStart;

                // Construire le texte du tooltip avec le détail des phases
                function buildTooltipHtml() {
                    let phases = '';
                    if (depD) {
                        phases += `<div class="tooltip-phase"><span class="tooltip-phase-icon">🚚</span> Départ : ${formatDateString(depD)}</div>`;
                    }
                    if (sStart) {
                        const shootLabel = sEnd && sEnd.getTime() !== sStart.getTime()
                            ? `${formatDateString(sStart)} → ${formatDateString(sEnd)}`
                            : formatDateString(sStart);
                        phases += `<div class="tooltip-phase"><span class="tooltip-phase-icon">🎬</span> Tournage : ${shootLabel}</div>`;
                    }
                    if (retD) {
                        phases += `<div class="tooltip-phase"><span class="tooltip-phase-icon">📦</span> Retour : ${formatDateString(retD)}</div>`;
                    }

                    return `
                        <strong>${booking.project_name}</strong>
                        <div class="tooltip-prod">Production : ${booking.production}</div>
                        <div class="tooltip-phases">${phases}</div>
                    `;
                }

                const tooltipHtml = buildTooltipHtml();

                // Helper pour créer un élément HTML de barre
                function createBarElement(dateS, dateE, content, extraClass) {
                    const pos = getPosAndWidth(dateS, dateE);
                    if (!pos) return null;

                    const conflictClass = booking.hasConflict ? 'has-conflict' : '';

                    const $bar = $(`
                        <div class="gantt-booking-bar ${extraClass} ${conflictClass}"
                             style="left: ${pos.left}px; width: ${pos.width}px; z-index: 2; background-color: ${booking.color};"
                             data-project-code="${booking.project_code || ''}">
                             ${content}
                        </div>
                    `);

                    // Clic pour aller sur la liste filtrée
                    $bar.on('click', function () {
                        const q = $(this).attr('data-project-code') || booking.project_code || '';
                        window.open(`/admin/projects?q=${encodeURIComponent(q)}`, '_blank');
                    });

                    // Tooltip au survol
                    $bar.hover(
                        function () { $tooltip.html(tooltipHtml).show(); },
                        function () { $tooltip.hide(); }
                    );

                    return $bar;
                }

                // Détermination des blocs à dessiner
                const hasAnyPhaseDate = depD || sStart || retD;
                const drawDepBlock = depD && (!sStart || depD.getTime() < sStart.getTime());
                const drawRetBlock = retD && (!sEnd || retD.getTime() > sEnd.getTime());
                const drawShootBlock = !!sStart;

                // Si aucune date individuelle, afficher un bloc unique (fallback)
                if (!hasAnyPhaseDate) {
                    const $fallback = createBarElement(bookStart, bookEnd, `🎬 ${booking.project_name}`, 'gantt-shoot-bar');
                    if ($fallback) $row.append($fallback);
                    return;
                }

                // 1. Ligne de connexion entre toutes les phases
                const globalPos = getPosAndWidth(bookStart, bookEnd);
                if (globalPos) {
                    const $connLine = $(`
                        <div class="gantt-booking-connection"
                             style="left: ${globalPos.left}px; width: ${globalPos.width}px; background-color: ${booking.color};">
                        </div>
                    `);
                    $row.append($connLine);
                }

                // 2. Bloc Départ (🚚) — jour unique, style outlined amber
                if (drawDepBlock) {
                    const $depBar = createBarElement(depD, depD, '🚚', 'gantt-dep-bar');
                    if ($depBar) $row.append($depBar);
                }

                // 3. Bloc Tournage (🎬) — barre pleine, couleur du projet
                if (drawShootBlock) {
                    let label = booking.project_name;
                    // Ajouter les icônes si départ/retour coïncident avec le tournage
                    if (depD && depD.getTime() === sStart.getTime()) {
                        label = '🚚 ' + label;
                    }
                    if (retD && sEnd && retD.getTime() === sEnd.getTime()) {
                        label = label + ' 📦';
                    }

                    const $shootBar = createBarElement(sStart, sEnd, `🎬 ${label}`, 'gantt-shoot-bar');
                    if ($shootBar) $row.append($shootBar);
                }

                // 4. Bloc Retour (📦) — jour unique, style outlined teal
                if (drawRetBlock) {
                    const $retBar = createBarElement(retD, retD, '📦', 'gantt-ret-bar');
                    if ($retBar) $row.append($retBar);
                }
            });
        });
    }

    // Formatage des dates en chaines lisibles (ex: "20 Mai 2026")
    function formatDateString(date) {
        return `${date.getDate()} ${MONTH_NAMES[date.getMonth()]} ${date.getFullYear()}`;
    }

    // Détection des conflits temporels (Overlaps)
    function detectAndMarkConflicts(bookings) {
        // Grouper les bookings par item_id
        const bookingsByItem = {};
        bookings.forEach(function (b) {
            if (!bookingsByItem[b.item_id]) {
                bookingsByItem[b.item_id] = [];
            }
            bookingsByItem[b.item_id].push(b);
        });

        // Analyser chaque groupe
        Object.keys(bookingsByItem).forEach(function (itemId) {
            const list = bookingsByItem[itemId];
            for (let i = 0; i < list.length; i++) {
                for (let j = i + 1; j < list.length; j++) {
                    const b1 = list[i];
                    const b2 = list[j];

                    const s1 = parseLocalDate(b1.start.split('T')[0]);
                    const e1 = parseLocalDate(b1.end.split('T')[0]);
                    const s2 = parseLocalDate(b2.start.split('T')[0]);
                    const e2 = parseLocalDate(b2.end.split('T')[0]);

                    // Condition de chevauchement de dates
                    if (s1 <= e2 && s2 <= e1) {
                        b1.hasConflict = true;
                        b2.hasConflict = true;
                    }
                }
            }
        });
    }
});
