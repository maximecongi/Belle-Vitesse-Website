$(document).ready(function () {
    // ── Configuration & State ──
    let currentDate = new Date(); // Date de référence (défaut: aujourd'hui)
    let currentCategory = 'vehicle'; // Catégorie courante ('vehicle' ou 'head')
    let selectedItemId = ''; // ID de l'équipement sélectionné (optionnel)
    const DAY_COLUMN_WIDTH = 55; // Largeur d'une colonne jour en pixels

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

            // Placer les barres de booking absolument
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

                // Cadrage du booking sur la fenêtre temporelle du mois
                const renderStart = bookStart < monthStart ? monthStart : bookStart;
                const renderEnd = bookEnd > monthEnd ? monthEnd : bookEnd;

                // Calcul du jour de départ (1-indexed) et de la durée dans la fenêtre
                const startDay = renderStart.getDate();
                
                // Différence en jours résistant aux changements d'heure (DST)
                const diffTime = renderEnd.getTime() - renderStart.getTime();
                const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24)) + 1;

                // Calcul des positions horizontales absolues
                const leftPos = (startDay - 1) * DAY_COLUMN_WIDTH + 2;
                const widthVal = (diffDays * DAY_COLUMN_WIDTH) - 4;

                // Trouver la ligne correspondante à cet équipement
                const $row = $grid.find(`.gantt-grid-row[data-item-id="${booking.item_id}"]`);
                if ($row.length > 0) {
                    const conflictClass = booking.hasConflict ? 'has-conflict' : '';
                    const $bar = $(`
                        <div class="gantt-booking-bar ${conflictClass}" 
                             style="left: ${leftPos}px; width: ${widthVal}px; background-color: ${booking.color};"
                             data-project="${booking.project_name}"
                             data-production="${booking.production}"
                             data-start="${formatDateString(bookStart)}"
                             data-end="${formatDateString(bookEnd)}"
                             data-project-id="${booking.project_id}"
                             data-project-code="${booking.project_code || ''}">
                            ${booking.project_name}
                        </div>
                    `);

                    // Clic sur la barre pour aller sur la liste filtrée du projet (nouvel onglet)
                    $bar.on('click', function () {
                        const q = $(this).attr('data-project-code') || booking.project_code || '';
                        window.open(`/admin/projects?q=${encodeURIComponent(q)}`, '_blank');
                    });

                    // Hover Event pour Tooltip Custom
                    $bar.hover(
                        function () {
                            const proj = $(this).data('project');
                            const prod = $(this).data('production');
                            const startStr = $(this).data('start');
                            const endStr = $(this).data('end');

                            $tooltip.html(`
                                <strong>${proj}</strong>
                                <div class="tooltip-prod">Production : ${prod}</div>
                                <div class="tooltip-dates">${startStr} ➔ ${endStr}</div>
                            `).show();
                        },
                        function () {
                            $tooltip.hide();
                        }
                    );

                    $row.append($bar);
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
