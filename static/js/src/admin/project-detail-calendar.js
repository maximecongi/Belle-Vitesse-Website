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

    function esc(str) {
        return String(str == null ? '' : str)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
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

        // ── Pointage du matériel (véhicules / têtes) par jour de tournage ──
        var usage = (data.usage && Array.isArray(data.usage.equipment) && data.usage.equipment.length &&
            Array.isArray(data.usage.days) && data.usage.days.length) ? data.usage : null;
        var usageMode = false;
        var usageBrush = usage ? usage.equipment[0].key : null; // clé « type:id » ou '*' (tout le matériel)
        var usageDaySet = new Set(usage ? usage.days.map(function (d) { return d.iso; }) : []);
        var usageDayLabels = {};
        if (usage) usage.days.forEach(function (d) { usageDayLabels[d.iso] = d.label; });
        var usageEquipByKey = {};
        if (usage) usage.equipment.forEach(function (e) { usageEquipByKey[e.key] = e; });
        var paint = null;          // { state, changes: Map } pendant un clic / glisser
        var saveChain = Promise.resolve();
        var pendingBadge = document.querySelector('[data-usage-pending-badge]');

        function usageState(key, iso) {
            var m = usage.marks[key] || {};
            return m[iso] || 'none';
        }

        function nextState(state) {
            return state === 'none' ? 'used' : (state === 'used' ? 'unused' : 'none');
        }

        function brushKeys() {
            return usageBrush === '*' ? usage.equipment.map(function (e) { return e.key; }) : [usageBrush];
        }

        // État cible d'un clic sur un jour : cycle du matériel actif, ou de tout le matériel
        function targetStateFor(iso) {
            if (usageBrush !== '*') return nextState(usageState(usageBrush, iso));
            var states = usage.equipment.map(function (e) { return usageState(e.key, iso); });
            if (states.every(function (s) { return s === 'used'; })) return 'unused';
            if (states.every(function (s) { return s === 'unused'; })) return 'none';
            return 'used';
        }

        function cellUsageState(iso) {
            if (usageBrush !== '*') return usageState(usageBrush, iso);
            var states = usage.equipment.map(function (e) { return usageState(e.key, iso); });
            if (states.every(function (s) { return s === 'used'; })) return 'used';
            if (states.every(function (s) { return s === 'unused'; })) return 'unused';
            if (states.every(function (s) { return s === 'none'; })) return 'none';
            return 'mixed';
        }

        function usageMarkersHtml(iso) {
            var html = '';
            usage.equipment.forEach(function (e) {
                var s = usageState(e.key, iso);
                if (!usageMode && s === 'none') return;
                html += '<span class="pdu-marker eq-color-' + esc(e.color) + ' is-' + s + '"></span>';
            });
            return html ? '<div class="pdu-markers" aria-hidden="true">' + html + '</div>' : '';
        }

        function usageTooltip(iso) {
            var parts = usage.equipment.map(function (e) {
                var s = usageState(e.key, iso);
                var lbl = s === 'used' ? 'utilisé' : (s === 'unused' ? 'non utilisé' : 'non pointé');
                return e.name + ' : ' + lbl;
            });
            return (usageDayLabels[iso] || formatDateFrench(iso)) + ' — ' + parts.join(' · ');
        }

        // Classes, attributs et marqueurs d'une case pour le pointage
        function usageCellParts(iso) {
            if (!usage) return { classes: [], attrs: '', html: '', title: null };
            if (!usageDaySet.has(iso)) {
                return { classes: usageMode ? ['is-usage-off'] : [], attrs: '', html: '', title: null };
            }
            var classes = ['has-usage'];
            var attrs = '';
            if (usageMode) {
                var st = cellUsageState(iso);
                classes.push('is-usage-day', 'usage-state-' + st);
                if (usageBrush !== '*') classes.push('eq-color-' + usageEquipByKey[usageBrush].color);
                attrs = ' role="button" tabindex="0" aria-label="' + esc(usageTooltip(iso)) + '"';
            }
            return { classes: classes, attrs: attrs, html: usageMarkersHtml(iso), title: usageTooltip(iso) };
        }

        function refreshUsageCell(cell) {
            var iso = cell.getAttribute('data-date');
            cell.className = cell.className.split(/\s+/).filter(function (c) {
                return c && c !== 'has-usage' && c !== 'is-usage-day' && c.indexOf('usage-state-') !== 0 && c.indexOf('eq-color-') !== 0;
            }).join(' ');
            var parts = usageCellParts(iso);
            parts.classes.forEach(function (c) { cell.classList.add(c); });
            if (parts.title) {
                cell.setAttribute('title', parts.title);
                cell.setAttribute('aria-label', parts.title);
            }
            var old = cell.querySelector('.pdu-markers');
            if (old) old.remove();
            if (parts.html) cell.insertAdjacentHTML('beforeend', parts.html);
        }

        function applyToDay(iso, state) {
            brushKeys().forEach(function (key) {
                var prev = usageState(key, iso);
                if (prev === state) return;
                var id = key + '|' + iso;
                if (!paint.changes.has(id)) paint.changes.set(id, { key: key, iso: iso, prev: prev });
                paint.changes.get(id).state = state;
                if (state === 'none') delete usage.marks[key][iso];
                else usage.marks[key][iso] = state;
            });
            var cell = container.querySelector('.pdp-day-cell[data-date="' + iso + '"]');
            if (cell) refreshUsageCell(cell);
        }

        function updatePendingBadge(count) {
            if (!pendingBadge) return;
            pendingBadge.hidden = !count;
            var lbl = pendingBadge.querySelector('[data-usage-pending-label]');
            if (lbl) lbl.textContent = count + ' jour' + (count > 1 ? 's' : '') + ' à pointer';
        }

        function postUsage(changes) {
            var csrfMeta = document.querySelector('meta[name="csrf-token"]');
            return fetch(data.usage_url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfMeta ? csrfMeta.getAttribute('content') : '',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    changes: changes.map(function (c) {
                        var sep = c.key.indexOf(':');
                        return {
                            equipment_type: c.key.slice(0, sep),
                            equipment_id: c.key.slice(sep + 1),
                            date: c.iso,
                            state: c.state
                        };
                    })
                })
            }).then(function (resp) {
                return resp.json().catch(function () { return {}; }).then(function (body) {
                    if (!resp.ok || body.status !== 'success') {
                        throw new Error(body.message || 'Le pointage n\'a pas pu être enregistré.');
                    }
                    return body.usage;
                });
            });
        }

        function commitChanges(changes) {
            changes = changes.filter(function (c) { return c.state !== c.prev; });
            if (!changes.length) return;
            saveChain = saveChain.then(function () {
                return postUsage(changes).then(function (serverUsage) {
                    // Totaux et rappel recalculés côté serveur
                    serverUsage.equipment.forEach(function (e) {
                        var local = usageEquipByKey[e.key];
                        if (local) {
                            local.used_days = e.used_days;
                            local.unused_days = e.unused_days;
                            local.pending_days = e.pending_days;
                        }
                    });
                    usage.pending_count = serverUsage.pending_count;
                    updatePendingBadge(serverUsage.pending_count);
                    renderUsageChrome();
                }).catch(function (err) {
                    // Annulation locale des changements refusés
                    changes.forEach(function (c) {
                        if (c.prev === 'none') delete usage.marks[c.key][c.iso];
                        else usage.marks[c.key][c.iso] = c.prev;
                    });
                    render();
                    if (typeof window.showFlash === 'function') window.showFlash(err.message, 'error');
                });
            });
        }

        function startPaint(iso) {
            paint = { state: targetStateFor(iso), changes: new Map() };
            applyToDay(iso, paint.state);
        }

        function endPaint() {
            if (!paint) return;
            var changes = Array.from(paint.changes.values());
            paint = null;
            container.classList.remove('is-usage-painting');
            commitChanges(changes);
        }

        function fillAll(state) {
            paint = { state: state, changes: new Map() };
            usage.days.forEach(function (d) { applyToDay(d.iso, state); });
            endPaint();
        }

        function setUsageMode(on) {
            usageMode = Boolean(on) && Boolean(usage);
            container.classList.toggle('is-usage-mode', usageMode);
            if (usageMode) {
                // Aller au mois du premier jour pointable si aucun n'est visible
                var visible = usage.days.some(function (d) {
                    var dt = parseISO(d.iso);
                    var idx = (dt.getFullYear() - currentYear) * 12 + (dt.getMonth() - currentMonth);
                    return idx === 0 || idx === 1;
                });
                if (!visible) {
                    var first = parseISO(usage.days[0].iso);
                    currentYear = first.getFullYear();
                    currentMonth = first.getMonth();
                }
            }
            render();
        }

        // Barre matériel permanente : même structure et même hauteur dans les deux modes,
        // pour que le calendrier reste exactement à la même position quand on bascule.
        function usageBarHtml() {
            var chips = usage.equipment.map(function (e) {
                var title = esc(e.type_label + (e.code ? ' · ' + e.code : ''));
                var inner = '<span class="pdu-chip-swatch"></span>' +
                    '<span class="pdu-chip-name">' + esc(e.name) + '</span>' +
                    '<span class="pdu-chip-count">' + e.used_days + '/' + usage.days.length + ' j</span>';
                if (!usageMode) {
                    return '<span class="pdu-chip is-static eq-color-' + esc(e.color) + '" title="' + title + '">' + inner + '</span>';
                }
                var active = usageBrush === e.key;
                return '<button type="button" class="pdu-chip eq-color-' + esc(e.color) + (active ? ' is-active' : '') + '"' +
                    ' data-usage-brush="' + esc(e.key) + '" aria-pressed="' + active + '" title="' + title + '">' +
                    inner + '</button>';
            }).join('');
            if (usage.equipment.length > 1) {
                var allInner = '<i data-lucide="layers"></i><span class="pdu-chip-name">Tout le matériel</span>';
                if (usageMode) {
                    var allActive = usageBrush === '*';
                    chips += '<button type="button" class="pdu-chip pdu-chip--all' + (allActive ? ' is-active' : '') + '"' +
                        ' data-usage-brush="*" aria-pressed="' + allActive + '">' + allInner + '</button>';
                } else {
                    // Place réservée : garde la même largeur (et donc le même retour à la ligne) qu'en pointage
                    chips += '<span class="pdu-chip pdu-chip--all is-placeholder" aria-hidden="true">' + allInner + '</span>';
                }
            }

            var toggle = '<button type="button" class="admin-btn admin-btn-xs ' + (usageMode ? 'admin-btn-primary' : 'admin-btn-secondary') + '"' +
                ' data-action="toggle-usage-mode" aria-pressed="' + usageMode + '"' +
                ' title="Noter, pour chaque jour de tournage, le matériel réellement utilisé">' +
                '<i data-lucide="list-checks"></i> ' + (usageMode ? 'Terminer le pointage' : 'Pointer le matériel') + '</button>';
            var left = toggle;
            if (usageMode) {
                var target = usageBrush === '*' ? 'tout le matériel' : usageEquipByKey[usageBrush].name;
                left += '<button type="button" class="admin-btn admin-btn-xs admin-btn-secondary" data-usage-fill="used"' +
                    ' title="Marquer ' + esc(target) + ' comme utilisé sur tous les jours de tournage">' +
                    '<i data-lucide="check-check"></i> Utilisé tous les jours</button>' +
                    '<button type="button" class="admin-btn admin-btn-xs admin-btn-secondary" data-usage-fill="none"' +
                    ' title="Effacer le pointage de ' + esc(target) + '">' +
                    '<i data-lucide="eraser"></i> Effacer</button>';
            }
            var exportBtn = '<a class="admin-btn admin-btn-xs admin-btn-secondary pdu-export" href="' + esc(data.usage_export_url) + '"' +
                ' target="_blank" rel="noopener" title="Relevé d\'utilisation du matériel (PDF)">' +
                '<i data-lucide="file-text"></i> Relevé PDF</a>';

            return '<div class="pdu-toolbar">' +
                '<div class="pdu-brushes" role="group" aria-label="' + (usageMode ? 'Matériel à pointer' : 'Jours utilisés par matériel') + '">' + chips + '</div>' +
                '<div class="pdu-actions">' +
                '<div class="pdu-actions-main">' + left + '</div>' +
                exportBtn +
                '</div>' +
                '</div>';
        }

        function usageLegendHtml() {
            var orphans = usage.orphans_count
                ? '<div class="pdu-orphans"><i data-lucide="info"></i> ' + usage.orphans_count +
                ' pointage' + (usage.orphans_count > 1 ? 's' : '') + ' hors des jours ou du matériel actuels du projet ' +
                '(conservé' + (usage.orphans_count > 1 ? 's' : '') + ', non comptabilisé' + (usage.orphans_count > 1 ? 's' : '') + ').</div>'
                : '';
            if (usageMode) {
                return '<div class="pdp-footer-legend pdu-legend">' +
                    '<div class="pdp-legend-items">' +
                    '<div class="pdp-legend-item"><span class="pdu-legend-swatch is-used"></span><span>Utilisé</span></div>' +
                    '<div class="pdp-legend-item"><span class="pdu-legend-swatch is-unused"></span><span>Non utilisé</span></div>' +
                    '<div class="pdp-legend-item"><span class="pdu-legend-swatch is-none"></span><span>Non pointé</span></div>' +
                    '</div>' +
                    '<div class="pdp-legend-hint">Cliquez ou glissez sur les jours de tournage : non pointé → utilisé → non utilisé.</div>' +
                    '</div>' + orphans;
            }
            return orphans;
        }

        // Rafraîchit la barre d'outils et la légende sans reconstruire le calendrier
        function renderUsageChrome() {
            if (!usage) return;
            var tb = container.querySelector('[data-usage-toolbar-host]');
            if (tb) tb.innerHTML = usageBarHtml();
            var lg = container.querySelector('[data-usage-legend-host]');
            if (lg) lg.innerHTML = usageLegendHtml();
            refreshIcons();
        }

        if (usage) {
            // Clic / glisser sur les jours de tournage (souris, stylet et tactile)
            container.addEventListener('pointerdown', function (e) {
                if (!usageMode || e.button > 0) return;
                var cell = e.target.closest('.pdp-day-cell.is-usage-day');
                if (!cell) return;
                e.preventDefault();
                if (cell.hasPointerCapture && cell.hasPointerCapture(e.pointerId)) cell.releasePointerCapture(e.pointerId);
                container.classList.add('is-usage-painting');
                startPaint(cell.getAttribute('data-date'));
            });
            container.addEventListener('pointermove', function (e) {
                if (!paint) return;
                var el = document.elementFromPoint(e.clientX, e.clientY);
                var cell = el && el.closest ? el.closest('.pdp-day-cell.is-usage-day') : null;
                if (cell && container.contains(cell)) applyToDay(cell.getAttribute('data-date'), paint.state);
            });
            document.addEventListener('pointerup', endPaint);
            document.addEventListener('pointercancel', endPaint);

            container.addEventListener('keydown', function (e) {
                if (!usageMode || (e.key !== 'Enter' && e.key !== ' ')) return;
                var cell = e.target.closest('.pdp-day-cell.is-usage-day');
                if (!cell) return;
                e.preventDefault();
                startPaint(cell.getAttribute('data-date'));
                endPaint();
            });

            container.addEventListener('click', function (e) {
                if (e.target.closest('[data-action="toggle-usage-mode"]')) {
                    setUsageMode(!usageMode);
                    return;
                }
                var brush = e.target.closest('[data-usage-brush]');
                if (brush) {
                    usageBrush = brush.getAttribute('data-usage-brush');
                    render();
                    return;
                }
                var fill = e.target.closest('[data-usage-fill]');
                if (fill) {
                    var state = fill.getAttribute('data-usage-fill');
                    var target = usageBrush === '*' ? 'de tout le matériel' : 'de ' + usageEquipByKey[usageBrush].name;
                    if (state === 'none' && typeof window.adminConfirm === 'function') {
                        window.adminConfirm('Effacer le pointage ' + target + ' sur tous les jours de tournage ?', {
                            title: 'Effacer le pointage', label: 'Effacer'
                        }).then(function (ok) { if (ok) fillAll(state); });
                    } else {
                        fillAll(state);
                    }
                }
            });

        }

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

                var usageParts = usageCellParts(dateIso);
                classes = classes.concat(usageParts.classes);
                if (usageParts.title) titleTooltip = usageParts.title;

                daysHtml += '<div class="' + classes.join(' ') + '" data-date="' + dateIso + '" title="' + esc(titleTooltip) + '"' +
                    usageParts.attrs + '>' +
                    '<span>' + d + '</span>' +
                    dotsHtml +
                    usageParts.html +
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
            if (usage) {
                container.innerHTML = '<div data-usage-toolbar-host>' + usageBarHtml() + '</div>' +
                    calendarViewportHtml +
                    (usageMode ? '' : legendHtml) +
                    '<div data-usage-legend-host>' + usageLegendHtml() + '</div>';
            } else {
                container.innerHTML = calendarViewportHtml + legendHtml;
            }

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

        // Lien direct vers le pointage (ex. rappel « jours à pointer » de la liste des projets)
        if (usage && window.location.hash === '#pointage') {
            setUsageMode(true);
            var wrapperEl = document.getElementById('projectShootCalendarWrapper');
            if (wrapperEl) wrapperEl.scrollIntoView({ block: 'start' });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initProjectDetailCalendar);
    } else {
        initProjectDetailCalendar();
    }

})(window, document);
