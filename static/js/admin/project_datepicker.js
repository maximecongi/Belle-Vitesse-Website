/**
 * ProjectTimelineDatePicker - Belle Vitesse
 * Sélecteur de dates interactif multi-jalons pour projets.
 * Supporte :
 * 1. Le mode 'Plage Continue' (Départ, Début Tournage, Fin Tournage, Retour)
 * 2. Le mode 'Dates Ponctuelles' (Sélection multi-dates libres avec gestion d'immobilisation ou relâchement)
 */

(function (window, document) {
    'use strict';

    class ProjectTimelineDatePicker {
        constructor(options = {}) {
            this.container = typeof options.container === 'string'
                ? document.querySelector(options.container)
                : options.container;

            if (!this.container) {
                console.error("ProjectTimelineDatePicker: Conteneur introuvable.");
                return;
            }

            this.inputDateMode = document.getElementById(options.inputDateModeId || 'date_mode_input');
            this.inputIsImmobilized = document.getElementById(options.inputIsImmobilizedId || 'is_immobilized_between_input');
            this.inputShootDates = document.getElementById(options.inputShootDatesId || 'shoot_dates_input');
            this.inputDeparture = document.getElementById(options.inputDepartureId || 'departure_date_input');
            this.inputShootStart = document.getElementById(options.inputShootStartId || 'shoot_start_input');
            this.inputShootEnd = document.getElementById(options.inputShootEndId || 'shoot_end_input');
            this.inputReturn = document.getElementById(options.inputReturnId || 'return_date_input');
            this.inputInterShootStatuses = document.getElementById(options.inputInterShootStatusesId || 'inter_shoot_statuses_input');

            // Mode : 'continuous' ou 'punctual'
            const initialMode = this.inputDateMode ? (this.inputDateMode.value || 'continuous') : 'continuous';
            this.mode = (initialMode === 'punctual') ? 'punctual' : 'continuous';

            // Immobilisation : booléen par défaut (true par défaut)
            if (this.inputIsImmobilized) {
                this.isImmobilized = this.inputIsImmobilized.value !== 'false';
            } else {
                this.isImmobilized = true;
            }

            // Statuts personnalisés par intervalle inter-dates { "start_end": boolean }
            this.interShootStatuses = {};
            if (this.inputInterShootStatuses && this.inputInterShootStatuses.value) {
                try {
                    const parsed = JSON.parse(this.inputInterShootStatuses.value);
                    if (Array.isArray(parsed)) {
                        parsed.forEach(item => {
                            if (item && item.start && item.end) {
                                this.interShootStatuses[`${item.start}_${item.end}`] = (item.is_immobilized !== false);
                            }
                        });
                    } else if (typeof parsed === 'object' && parsed !== null) {
                        this.interShootStatuses = parsed;
                    }
                } catch (e) {
                    console.warn("ProjectTimelineDatePicker: Erreur parsing inter_shoot_statuses JSON", e);
                }
            }

            // État des dates de tournage ponctuelles
            this.shootDates = [];
            if (this.inputShootDates && this.inputShootDates.value) {
                try {
                    const parsed = JSON.parse(this.inputShootDates.value);
                    if (Array.isArray(parsed)) {
                        this.shootDates = parsed.filter(d => typeof d === 'string' && d.trim().length > 0).sort();
                    }
                } catch (e) {
                    console.warn("ProjectTimelineDatePicker: Erreur parsing shoot_dates JSON", e);
                }
            }

            // État des 4 dates jalons (Format 'YYYY-MM-DD')
            this.dates = {
                departure: this.inputDeparture ? this.inputDeparture.value || null : null,
                shoot_start: this.inputShootStart ? this.inputShootStart.value || null : null,
                shoot_end: this.inputShootEnd ? this.inputShootEnd.value || null : null,
                return: this.inputReturn ? this.inputReturn.value || null : null
            };

            // Si mode ponctuel avec shootDates vide mais shoot_start défini
            if (this.mode === 'punctual' && this.shootDates.length === 0) {
                if (this.dates.shoot_start) this.shootDates.push(this.dates.shoot_start);
                if (this.dates.shoot_end && this.dates.shoot_end !== this.dates.shoot_start) {
                    this.shootDates.push(this.dates.shoot_end);
                }
                this.shootDates.sort();
            }

            // Jalon actif sélectionné
            this.activeMilestone = (this.mode === 'punctual') ? 'shoot_dates' : 'departure';
            this.quickMode = null; // 'shoot_1d', etc.

            // Mois affiché pour le 1er calendrier
            const initialDate = (this.shootDates.length > 0 ? this.shootDates[0] : null) || this.dates.shoot_start || this.dates.departure || new Date();
            const d = new Date(initialDate);
            this.currentYear = isNaN(d.getTime()) ? new Date().getFullYear() : d.getFullYear();
            this.currentMonth = isNaN(d.getTime()) ? new Date().getMonth() : d.getMonth();

            this.monthNames = [
                "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
            ];
            this.weekdayNames = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

            this.init();
        }

        init() {
            this.renderLayout();
            this.updateMilestoneCards();
            this.renderIntervalsSection();
            this.renderCalendars();
            this.bindEvents();
            this.syncInputs();
            this.refreshIcons();
        }

        refreshIcons() {
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                try {
                    window.lucide.createIcons({
                        root: this.container
                    });
                } catch (e) {
                    try {
                        window.lucide.createIcons();
                    } catch (err) { }
                }
            }
        }

        renderLayout() {
            const isPunctual = (this.mode === 'punctual');

            this.container.innerHTML = `
                <div class="project-datepicker-container">
                    <!-- Barre de sélection du Mode de Dates -->
                    <div class="pdp-mode-bar">
                        <div class="pdp-mode-tabs" role="tablist">
                            <button type="button" class="pdp-mode-tab ${!isPunctual ? 'active' : ''}" data-mode="continuous" title="Période continue avec date de début et de fin de tournage">
                                <span><i data-lucide="calendar-range"></i> Plage Continue</span>
                            </button>
                            <button type="button" class="pdp-mode-tab ${isPunctual ? 'active' : ''}" data-mode="punctual" title="Sélection de dates spécifiques ponctuelles avec gestion d'immobilisation">
                                <span><i data-lucide="calendar-days"></i> Dates Ponctuelles</span>
                            </button>
                        </div>
                        <div class="pdp-mode-hint" id="pdp-mode-hint-text">
                            ${isPunctual
                    ? '<span>💡 Cliquez sur chaque jour de tournage pour l\'ajouter ou le retirer.</span>'
                    : '<span>💡 Sélectionnez les jalons clés dans l\'ordre ou utilisez les raccourcis.</span>'}
                        </div>
                    </div>

                    <!-- Cartes des Jalons -->
                    <div class="pdp-milestones-grid" id="pdp-milestones-grid">
                        ${this.renderMilestonesHtml()}
                    </div>

                    <!-- Section dynamique des Intervalles Ponctuels -->
                    <div class="pdp-intervals-container" id="pdp-intervals-container" style="display: none;"></div>

                    <!-- Barre d'outils et Raccourcis -->
                    <div class="pdp-toolbar">
                        <div class="pdp-presets-group">
                            <span class="pdp-preset-label"><i data-lucide="sparkles"></i> Raccourcis :</span>
                            <button type="button" class="pdp-preset-btn btn-highlight" id="pdp-preset-auto-range" title="Caler automatiquement la Prépa à J-1 et le Retour à J+1 autour de la période de tournage">
                                <i data-lucide="wand-2"></i> Auto Prépa / Retour
                            </button>
                            ${!isPunctual ? `
                                <button type="button" class="pdp-preset-btn" id="pdp-preset-1day" title="Cliquez sur le jour du tournage pour créer un shoot d'1 jour avec prépa J-1 et retour J+1">
                                    <i data-lucide="zap"></i> Shoot 1 jour complet
                                </button>
                            ` : `
                                <button type="button" class="pdp-preset-btn" id="pdp-preset-toggle-immob" title="Basculer le statut d'immobilisation du véhicule entre les dates">
                                    ${this.isImmobilized ? '<i data-lucide="unlock"></i> Relâcher entre les dates' : '<i data-lucide="lock"></i> Immobiliser entre les dates'}
                                </button>
                            `}
                        </div>
                        <div class="pdp-actions-group">
                            <button type="button" class="pdp-preset-btn" id="pdp-btn-today"><i data-lucide="calendar"></i> Aujourd'hui</button>
                            <button type="button" class="pdp-preset-btn pdp-btn-reset" id="pdp-btn-reset" style="color: #ef4444;"><i data-lucide="trash-2"></i> Effacer les dates</button>
                        </div>
                    </div>

                    <!-- Vue Double Calendrier -->
                    <div class="pdp-calendar-container" id="pdp-calendar-viewport">
                        <!-- Généré dynamiquement -->
                    </div>

                    <!-- Légende -->
                    <div class="pdp-footer-legend">
                        <div class="pdp-legend-items">
                            <div class="pdp-legend-item">
                                <div class="pdp-legend-swatch swatch-dep"></div>
                                <span>Départ</span>
                            </div>
                            <div class="pdp-legend-item">
                                <div class="pdp-legend-swatch swatch-shoot"></div>
                                <span>Tournage</span>
                            </div>
                            <div class="pdp-legend-item">
                                <div class="pdp-legend-swatch swatch-standby"></div>
                                <span>Immobilisé</span>
                            </div>
                            <div class="pdp-legend-item">
                                <div class="pdp-legend-swatch swatch-ret"></div>
                                <span>Retour</span>
                            </div>
                        </div>
                        <div class="pdp-legend-hint">
                            ${isPunctual
                    ? 'En mode ponctuel, cliquez sur les jours pour composer votre calendrier de tournage.'
                    : 'Cliquez sur un jour pour placer le jalon actif ou sélectionnez une puce ci-dessus.'}
                        </div>
                    </div>
                </div>
            `;
            this.refreshIcons();
        }

        renderMilestonesHtml() {
            if (this.mode === 'punctual') {
                const count = this.shootDates.length;
                let shootDateText = "Aucune date définie";
                if (count === 1) {
                    shootDateText = `1 jour : ${this.formatDateShort(this.shootDates[0])}`;
                } else if (count > 1) {
                    shootDateText = `${count} jours (${this.formatDateShort(this.shootDates[0])} → ${this.formatDateShort(this.shootDates[count - 1])})`;
                }

                return `
                    <div class="pdp-milestone-card type-departure ${this.activeMilestone === 'departure' ? 'active' : ''}" data-milestone="departure">
                        <div class="pdp-milestone-header">
                            <span class="pdp-milestone-label"><i data-lucide="package-check"></i> Prépa / Départ</span>
                            <span class="pdp-step-badge">1</span>
                        </div>
                        <div class="pdp-milestone-date" id="pdp-date-departure">Non définie</div>
                        <div class="pdp-milestone-actions">
                            <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="departure" data-delta="-1">-1j</button>
                            <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="departure" data-delta="1">+1j</button>
                            <button type="button" class="pdp-mini-btn btn-clear" data-action="clear" data-target="departure" title="Effacer">×</button>
                        </div>
                    </div>

                    <div class="pdp-milestone-card type-shoot_dates ${this.activeMilestone === 'shoot_dates' ? 'active' : ''}" data-milestone="shoot_dates">
                        <div class="pdp-milestone-header">
                            <span class="pdp-milestone-label"><i data-lucide="clapperboard"></i> Dates Tournage</span>
                            <span class="pdp-step-badge">${count}j</span>
                        </div>
                        <div class="pdp-milestone-date ${count === 0 ? 'empty' : ''}" id="pdp-date-shoot_dates">${shootDateText}</div>
                        <div class="pdp-milestone-actions">
                            <button type="button" class="pdp-mini-btn btn-clear" data-action="clear-shoot-dates" title="Vider toutes les dates de tournage">
                                <i data-lucide="trash-2"></i> Vider
                            </button>
                        </div>
                    </div>

                    <div class="pdp-milestone-card type-return ${this.activeMilestone === 'return' ? 'active' : ''}" data-milestone="return">
                        <div class="pdp-milestone-header">
                            <span class="pdp-milestone-label"><i data-lucide="rotate-ccw"></i> Retour Matériel</span>
                            <span class="pdp-step-badge">Fin</span>
                        </div>
                        <div class="pdp-milestone-date" id="pdp-date-return">Non définie</div>
                        <div class="pdp-milestone-actions">
                            <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="return" data-delta="-1">-1j</button>
                            <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="return" data-delta="1">+1j</button>
                            <button type="button" class="pdp-mini-btn btn-clear" data-action="clear" data-target="return" title="Effacer">×</button>
                        </div>
                    </div>
                `;
            }

            // Mode continu historique
            return `
                <div class="pdp-milestone-card type-departure ${this.activeMilestone === 'departure' ? 'active' : ''}" data-milestone="departure">
                    <div class="pdp-milestone-header">
                        <span class="pdp-milestone-label"><i data-lucide="package-check"></i> Prépa / Départ</span>
                        <span class="pdp-step-badge">1</span>
                    </div>
                    <div class="pdp-milestone-date" id="pdp-date-departure">Non définie</div>
                    <div class="pdp-milestone-actions">
                        <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="departure" data-delta="-1">-1j</button>
                        <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="departure" data-delta="1">+1j</button>
                        <button type="button" class="pdp-mini-btn btn-clear" data-action="clear" data-target="departure" title="Effacer">×</button>
                    </div>
                </div>

                <div class="pdp-milestone-card type-shoot_start ${this.activeMilestone === 'shoot_start' ? 'active' : ''}" data-milestone="shoot_start">
                    <div class="pdp-milestone-header">
                        <span class="pdp-milestone-label"><i data-lucide="clapperboard"></i> Début Tournage</span>
                        <span class="pdp-step-badge">2</span>
                    </div>
                    <div class="pdp-milestone-date" id="pdp-date-shoot_start">Non définie</div>
                    <div class="pdp-milestone-actions">
                        <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="shoot_start" data-delta="-1">-1j</button>
                        <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="shoot_start" data-delta="1">+1j</button>
                        <button type="button" class="pdp-mini-btn btn-clear" data-action="clear" data-target="shoot_start" title="Effacer">×</button>
                    </div>
                </div>

                <div class="pdp-milestone-card type-shoot_end ${this.activeMilestone === 'shoot_end' ? 'active' : ''}" data-milestone="shoot_end">
                    <div class="pdp-milestone-header">
                        <span class="pdp-milestone-label"><i data-lucide="flag"></i> Fin Tournage</span>
                        <span class="pdp-step-badge">3</span>
                    </div>
                    <div class="pdp-milestone-date" id="pdp-date-shoot_end">Non définie</div>
                    <div class="pdp-milestone-actions">
                        <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="shoot_end" data-delta="-1">-1j</button>
                        <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="shoot_end" data-delta="1">+1j</button>
                        <button type="button" class="pdp-mini-btn btn-clear" data-action="clear" data-target="shoot_end" title="Effacer">×</button>
                    </div>
                </div>

                <div class="pdp-milestone-card type-return ${this.activeMilestone === 'return' ? 'active' : ''}" data-milestone="return">
                    <div class="pdp-milestone-header">
                        <span class="pdp-milestone-label"><i data-lucide="rotate-ccw"></i> Retour Matériel</span>
                        <span class="pdp-step-badge">4</span>
                    </div>
                    <div class="pdp-milestone-date" id="pdp-date-return">Non définie</div>
                    <div class="pdp-milestone-actions">
                        <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="return" data-delta="-1">-1j</button>
                        <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="return" data-delta="1">+1j</button>
                        <button type="button" class="pdp-mini-btn btn-clear" data-action="clear" data-target="return" title="Effacer">×</button>
                    </div>
                </div>
            `;
        }

        formatDateFrench(isoStr) {
            if (!isoStr) return null;
            const parts = isoStr.split('-');
            if (parts.length !== 3) return isoStr;
            const y = parseInt(parts[0], 10);
            const m = parseInt(parts[1], 10) - 1;
            const d = parseInt(parts[2], 10);
            const dateObj = new Date(y, m, d);
            if (isNaN(dateObj.getTime())) return isoStr;

            const days = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"];
            const dayName = days[dateObj.getDay()];
            const monthName = this.monthNames[m].substring(0, 4).toLowerCase();

            return `${dayName} ${d} ${monthName} ${y}`;
        }

        formatDateShort(isoStr) {
            if (!isoStr) return "—";
            const parts = isoStr.split('-');
            if (parts.length !== 3) return isoStr;
            return `${parts[2]}/${parts[1]}`;
        }

        toIsoString(dateObj) {
            const y = dateObj.getFullYear();
            const m = String(dateObj.getMonth() + 1).padStart(2, '0');
            const d = String(dateObj.getDate()).padStart(2, '0');
            return `${y}-${m}-${d}`;
        }

        addDays(isoStr, numDays) {
            if (!isoStr) return null;
            const parts = isoStr.split('-');
            const d = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
            d.setDate(d.getDate() + numDays);
            return this.toIsoString(d);
        }

        getDaysDiff(d1Str, d2Str) {
            if (!d1Str || !d2Str) return 0;
            const p1 = d1Str.split('-').map(Number);
            const p2 = d2Str.split('-').map(Number);
            const dt1 = Date.UTC(p1[0], p1[1] - 1, p1[2]);
            const dt2 = Date.UTC(p2[0], p2[1] - 1, p2[2]);
            return Math.round((dt2 - dt1) / (1000 * 60 * 60 * 24));
        }

        calculateIntervals() {
            if (this.mode !== 'punctual' || !this.shootDates || this.shootDates.length < 2) {
                return [];
            }
            const sorted = [...this.shootDates].sort();
            const intervals = [];

            for (let i = 0; i < sorted.length - 1; i++) {
                const d1 = sorted[i];
                const d2 = sorted[i + 1];
                const diff = this.getDaysDiff(d1, d2);

                if (diff > 1) {
                    const daysBetween = [];
                    let cur = this.addDays(d1, 1);
                    while (cur < d2) {
                        daysBetween.push(cur);
                        cur = this.addDays(cur, 1);
                    }

                    const key = `${d1}_${d2}`;
                    const isImmob = (this.interShootStatuses && key in this.interShootStatuses)
                        ? Boolean(this.interShootStatuses[key])
                        : Boolean(this.isImmobilized);

                    intervals.push({
                        start: d1,
                        end: d2,
                        key: key,
                        days: daysBetween,
                        daysCount: daysBetween.length,
                        is_immobilized: isImmob
                    });
                }
            }
            return intervals;
        }

        getIntervalForDate(dateIso) {
            const intervals = this.calculateIntervals();
            return intervals.find(inter => inter.days.includes(dateIso)) || null;
        }

        setIntervalImmobilization(key, isImmob) {
            if (!this.interShootStatuses) {
                this.interShootStatuses = {};
            }
            this.interShootStatuses[key] = Boolean(isImmob);
            this.syncInputs();
            this.updateMilestoneCards();
            this.renderIntervalsSection();
            this.renderCalendars();
        }

        renderIntervalsSection() {
            const container = document.getElementById('pdp-intervals-container');
            if (!container) return;

            if (this.mode !== 'punctual') {
                container.style.display = 'none';
                container.innerHTML = '';
                return;
            }

            const intervals = this.calculateIntervals();
            if (intervals.length === 0) {
                container.style.display = 'none';
                container.innerHTML = '';
                return;
            }

            container.style.display = 'block';
            let listHtml = '';
            intervals.forEach(inter => {
                const daysDesc = inter.daysCount === 1
                    ? `1 jour intermédiaire : ${this.formatDateShort(inter.days[0])}`
                    : `${inter.daysCount} jours intermédiaires : ${this.formatDateShort(inter.days[0])} → ${this.formatDateShort(inter.days[inter.days.length - 1])}`;

                listHtml += `
                    <div class="pdp-interval-card ${inter.is_immobilized ? 'is-immob' : 'is-free'}">
                        <div class="pdp-interval-left">
                            <span class="pdp-interval-badge">${inter.daysCount}j</span>
                            <div class="pdp-interval-text">
                                <strong>Du ${this.formatDateShort(inter.start)} au ${this.formatDateShort(inter.end)}</strong>
                                <span class="pdp-interval-detail">${daysDesc}</span>
                            </div>
                        </div>
                        <div class="pdp-interval-toggle-group">
                            <button type="button" class="pdp-interval-btn btn-immob ${inter.is_immobilized ? 'active' : ''}" data-key="${inter.key}" data-immob="true" title="Le véhicule reste réservé pour ce projet">
                                <i data-lucide="lock"></i> Immobilisé
                            </button>
                            <button type="button" class="pdp-interval-btn btn-free ${!inter.is_immobilized ? 'active' : ''}" data-key="${inter.key}" data-immob="false" title="Le véhicule retourne à la base et redevient disponible pour d'autres tournages">
                                <i data-lucide="rotate-ccw"></i> Relâché
                            </button>
                        </div>
                    </div>
                `;
            });

            container.innerHTML = `
                <div class="pdp-intervals-header">
                    <span class="pdp-intervals-title"><i data-lucide="sliders"></i> Gestion d'immobilisation par intervalle</span>
                    <span class="pdp-intervals-subtitle">${intervals.length} période(s) intermédiaire(s) configurables</span>
                </div>
                <div class="pdp-intervals-list">
                    ${listHtml}
                </div>
            `;
            this.refreshIcons();
        }

        syncInputs() {
            if (this.inputDateMode) this.inputDateMode.value = this.mode;
            if (this.inputIsImmobilized) this.inputIsImmobilized.value = this.isImmobilized ? 'true' : 'false';
            if (this.inputShootDates) this.inputShootDates.value = JSON.stringify(this.shootDates || []);
            if (this.inputDeparture) this.inputDeparture.value = this.dates.departure || '';
            if (this.inputShootStart) this.inputShootStart.value = this.dates.shoot_start || '';
            if (this.inputShootEnd) this.inputShootEnd.value = this.dates.shoot_end || '';
            if (this.inputReturn) this.inputReturn.value = this.dates.return || '';

            if (this.inputInterShootStatuses) {
                const intervals = this.calculateIntervals();
                const arrayData = intervals.map(inter => ({
                    start: inter.start,
                    end: inter.end,
                    is_immobilized: inter.is_immobilized
                }));
                this.inputInterShootStatuses.value = JSON.stringify(arrayData);
            }

            // Déclencher les événements de modification pour informer les écouteurs (conflits, validation)
            const inputs = [
                this.inputDateMode,
                this.inputIsImmobilized,
                this.inputShootDates,
                this.inputInterShootStatuses,
                this.inputDeparture,
                this.inputShootStart,
                this.inputShootEnd,
                this.inputReturn
            ];
            inputs.forEach(el => {
                if (el) {
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
        }

        updateMilestoneCards() {
            if (this.mode === 'punctual') {
                const depEl = document.getElementById('pdp-date-departure');
                const shootDatesEl = document.getElementById('pdp-date-shoot_dates');
                const immobEl = document.getElementById('pdp-date-immobilization');
                const retEl = document.getElementById('pdp-date-return');

                if (depEl) {
                    if (this.dates.departure) {
                        depEl.textContent = this.formatDateFrench(this.dates.departure);
                        depEl.classList.remove('empty');
                    } else {
                        depEl.textContent = "Non définie";
                        depEl.classList.add('empty');
                    }
                }

                if (shootDatesEl) {
                    const count = this.shootDates.length;
                    if (count === 0) {
                        shootDatesEl.textContent = "Aucune date définie";
                        shootDatesEl.classList.add('empty');
                    } else if (count === 1) {
                        shootDatesEl.textContent = `1 jour : ${this.formatDateFrench(this.shootDates[0])}`;
                        shootDatesEl.classList.remove('empty');
                    } else if (count <= 3) {
                        shootDatesEl.textContent = `${count} jours : ${this.shootDates.map(d => this.formatDateShort(d)).join(', ')}`;
                        shootDatesEl.classList.remove('empty');
                    } else {
                        shootDatesEl.textContent = `${count} jours (${this.formatDateShort(this.shootDates[0])} → ${this.formatDateShort(this.shootDates[count - 1])})`;
                        shootDatesEl.classList.remove('empty');
                    }
                }

                if (immobEl) {
                    const intervals = this.calculateIntervals();
                    if (intervals.length > 1) {
                        const immobCount = intervals.filter(i => i.is_immobilized).length;
                        const freeCount = intervals.length - immobCount;
                        if (immobCount > 0 && freeCount > 0) {
                            immobEl.innerHTML = `<i data-lucide="lock"></i> ${immobCount} / <i data-lucide="rotate-ccw"></i> ${freeCount}`;
                        } else if (immobCount > 0) {
                            immobEl.innerHTML = `<i data-lucide="lock"></i> ${immobCount} immobilisé(s)`;
                        } else {
                            immobEl.innerHTML = `<i data-lucide="rotate-ccw"></i> ${freeCount} relâché(s)`;
                        }
                    } else if (intervals.length === 1) {
                        immobEl.innerHTML = intervals[0].is_immobilized ? '<i data-lucide="lock"></i> Immobilisé sur place' : '<i data-lucide="rotate-ccw"></i> Relâché à la base';
                    } else {
                        immobEl.innerHTML = this.isImmobilized ? '<i data-lucide="lock"></i> Immobilisé par défaut' : '<i data-lucide="rotate-ccw"></i> Relâché par défaut';
                    }
                }

                if (retEl) {
                    if (this.dates.return) {
                        retEl.textContent = this.formatDateFrench(this.dates.return);
                        retEl.classList.remove('empty');
                    } else {
                        retEl.textContent = "Non définie";
                        retEl.classList.add('empty');
                    }
                }

                this.container.querySelectorAll('.pdp-milestone-card').forEach(c => {
                    const m = c.dataset.milestone;
                    c.classList.toggle('active', this.activeMilestone === m);
                });
            } else {
                // Mode continu
                const milestones = ['departure', 'shoot_start', 'shoot_end', 'return'];
                milestones.forEach(m => {
                    const el = document.getElementById(`pdp-date-${m}`);
                    const card = this.container.querySelector(`.pdp-milestone-card[data-milestone="${m}"]`);
                    if (el) {
                        if (this.dates[m]) {
                            el.textContent = this.formatDateFrench(this.dates[m]);
                            el.classList.remove('empty');
                        } else {
                            el.textContent = "Non définie";
                            el.classList.add('empty');
                        }
                    }
                    if (card) {
                        card.classList.toggle('active', this.activeMilestone === m);
                    }
                });
            }
            this.refreshIcons();
        }

        renderCalendars() {
            const viewport = this.container.querySelector('#pdp-calendar-viewport');
            if (!viewport) return;

            const m1Year = this.currentYear;
            const m1Month = this.currentMonth;

            // Deuxième mois
            let m2Year = m1Year;
            let m2Month = m1Month + 1;
            if (m2Month > 11) {
                m2Month = 0;
                m2Year++;
            }

            viewport.innerHTML = `
                ${this.buildMonthHtml(m1Year, m1Month, true, false)}
                ${this.buildMonthHtml(m2Year, m2Month, false, true)}
            `;

            // Reconnecter la navigation des mois
            const prevBtn = viewport.querySelector('#pdp-prev-month');
            const nextBtn = viewport.querySelector('#pdp-next-month');

            if (prevBtn) {
                prevBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.currentMonth--;
                    if (this.currentMonth < 0) {
                        this.currentMonth = 11;
                        this.currentYear--;
                    }
                    this.renderCalendars();
                });
            }

            if (nextBtn) {
                nextBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.currentMonth++;
                    if (this.currentMonth > 11) {
                        this.currentMonth = 0;
                        this.currentYear++;
                    }
                    this.renderCalendars();
                });
            }

            // Bind click sur chaque jour
            viewport.querySelectorAll('.pdp-day-cell:not(.empty)').forEach(cell => {
                cell.addEventListener('click', (e) => {
                    const dateStr = cell.dataset.date;
                    if (dateStr) {
                        this.handleDayClick(dateStr);
                    }
                });
            });

            this.refreshIcons();
        }

        buildMonthHtml(year, month, showPrev, showNext) {
            const firstDayIndex = new Date(year, month, 1).getDay(); // 0 = Dimanche
            const startOffset = (firstDayIndex + 6) % 7; // Convertir en Lundi = 0
            const daysInMonth = new Date(year, month + 1, 0).getDate();

            const todayIso = this.toIsoString(new Date());
            const isPunctual = (this.mode === 'punctual');

            const firstShoot = isPunctual ? (this.shootDates.length > 0 ? this.shootDates[0] : null) : this.dates.shoot_start;
            const lastShoot = isPunctual ? (this.shootDates.length > 0 ? this.shootDates[this.shootDates.length - 1] : null) : (this.dates.shoot_end || this.dates.shoot_start);

            let daysHtml = '';

            // Jours vides au début
            for (let i = 0; i < startOffset; i++) {
                daysHtml += `<div class="pdp-day-cell empty"></div>`;
            }

            // Jours du mois
            for (let d = 1; d <= daysInMonth; d++) {
                const dateIso = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;

                let classes = ['pdp-day-cell'];
                if (dateIso === todayIso) classes.push('is-today');

                const isDep = this.dates.departure === dateIso;
                const isRet = this.dates.return === dateIso;

                let isShootDay = false;
                let isStandbyDay = false;
                let isFreeInterDay = false;

                if (isPunctual) {
                    if (this.shootDates.includes(dateIso)) {
                        isShootDay = true;
                        classes.push('shoot-punctual-day');
                    } else if (firstShoot && lastShoot && dateIso > firstShoot && dateIso < lastShoot) {
                        const inter = this.getIntervalForDate(dateIso);
                        const isInterImmob = inter ? inter.is_immobilized : this.isImmobilized;
                        if (isInterImmob) {
                            isStandbyDay = true;
                            classes.push('intermediate-standby-day');
                        } else {
                            isFreeInterDay = true;
                            classes.push('intermediate-free-day');
                        }
                    }
                } else {
                    // Mode continu classique
                    const isShootStart = this.dates.shoot_start === dateIso;
                    const isShootEnd = this.dates.shoot_end === dateIso;

                    if (this.dates.shoot_start && this.dates.shoot_end) {
                        if (dateIso >= this.dates.shoot_start && dateIso <= this.dates.shoot_end) {
                            classes.push('in-shoot-range');
                            isShootDay = true;
                        }
                    } else if (isShootStart) {
                        isShootDay = true;
                    }

                    if (isShootStart) classes.push('shoot-start-day');
                    if (isShootEnd) classes.push('shoot-end-day');
                }

                if (isDep) classes.push('departure-day');
                if (isRet) classes.push('return-day');

                // Badges/dots si chevauchement de statuts sur le même jour
                let dotsHtml = '';
                const dots = [];
                if (isDep) dots.push('dot-dep');
                if (isShootDay) dots.push('dot-shoot');
                if (isRet) dots.push('dot-ret');

                if (dots.length > 1) {
                    dotsHtml = `<div class="pdp-day-badges">${dots.map(dt => `<div class="pdp-dot ${dt}"></div>`).join('')}</div>`;
                }

                let titleTooltip = '';
                if (isShootDay) titleTooltip = 'Jour de tournage';
                else if (isStandbyDay) titleTooltip = 'Véhicule immobilisé (bloqué pour ce tournage)';
                else if (isFreeInterDay) titleTooltip = 'Véhicule disponible à la base (non immobilisé)';
                else if (isDep) titleTooltip = 'Prépa / Enlèvement matériel';
                else if (isRet) titleTooltip = 'Restitution matériel';

                daysHtml += `
                    <div class="${classes.join(' ')}" data-date="${dateIso}" title="${titleTooltip}">
                        <span>${d}</span>
                        ${dotsHtml}
                    </div>
                `;
            }

            return `
                <div class="pdp-month-card">
                    <div class="pdp-month-header">
                        ${showPrev ? '<button type="button" class="pdp-nav-btn" id="pdp-prev-month" title="Mois précédent"><i data-lucide="chevron-left"></i></button>' : '<div class="pdp-nav-spacer"></div>'}
                        <div class="pdp-month-title">${this.monthNames[month]} ${year}</div>
                        ${showNext ? '<button type="button" class="pdp-nav-btn" id="pdp-next-month" title="Mois suivant"><i data-lucide="chevron-right"></i></button>' : '<div class="pdp-nav-spacer"></div>'}
                    </div>
                    <div class="pdp-weekdays">
                        ${this.weekdayNames.map(w => `<div>${w}</div>`).join('')}
                    </div>
                    <div class="pdp-days-grid">
                        ${daysHtml}
                    </div>
                </div>
            `;
        }

        handleDayClick(dateStr) {
            // Mode spécial : 1 Jour Complet (en mode continu)
            if (this.quickMode === 'shoot_1d' && this.mode === 'continuous') {
                this.dates.departure = this.addDays(dateStr, -1);
                this.dates.shoot_start = dateStr;
                this.dates.shoot_end = dateStr;
                this.dates.return = this.addDays(dateStr, 1);
                this.quickMode = null;
                this.activeMilestone = 'shoot_end';
                this.syncInputs();
                this.updateMilestoneCards();
                this.renderCalendars();
                return;
            }

            // Gestion des clics en mode Ponctuel
            if (this.mode === 'punctual') {
                if (this.activeMilestone === 'departure') {
                    this.dates.departure = dateStr;
                    this.activeMilestone = 'shoot_dates';
                } else if (this.activeMilestone === 'return') {
                    this.dates.return = dateStr;
                    this.activeMilestone = 'shoot_dates';
                } else {
                    // Clic pour ajouter ou retirer un jour de tournage ponctuel
                    const idx = this.shootDates.indexOf(dateStr);
                    if (idx >= 0) {
                        this.shootDates.splice(idx, 1);
                    } else {
                        this.shootDates.push(dateStr);
                    }
                    this.shootDates.sort();

                    if (this.shootDates.length > 0) {
                        this.dates.shoot_start = this.shootDates[0];
                        this.dates.shoot_end = this.shootDates[this.shootDates.length - 1];
                        if (!this.dates.departure || this.dates.departure > this.dates.shoot_start) {
                            this.dates.departure = this.dates.shoot_start;
                        }
                        if (!this.dates.return || this.dates.return < this.dates.shoot_end) {
                            this.dates.return = this.dates.shoot_end;
                        }
                    } else {
                        this.dates.shoot_start = null;
                        this.dates.shoot_end = null;
                    }
                }

                this.syncInputs();
                this.updateMilestoneCards();
                this.renderIntervalsSection();
                this.renderCalendars();
                return;
            }

            // Gestion en mode continu classique
            const current = this.activeMilestone;
            this.dates[current] = dateStr;

            // Logique de transition intelligente
            if (current === 'departure') {
                this.activeMilestone = 'shoot_start';
            } else if (current === 'shoot_start') {
                if (!this.dates.shoot_end || this.dates.shoot_end < dateStr) {
                    this.dates.shoot_end = dateStr;
                }
                this.activeMilestone = 'shoot_end';
            } else if (current === 'shoot_end') {
                if (this.dates.shoot_start && dateStr < this.dates.shoot_start) {
                    this.dates.shoot_end = this.dates.shoot_start;
                    this.dates.shoot_start = dateStr;
                }
                if (!this.dates.return || this.dates.return < this.dates.shoot_end) {
                    this.dates.return = this.addDays(this.dates.shoot_end, 1);
                }
                this.activeMilestone = 'return';
            } else if (current === 'return') {
                this.activeMilestone = 'departure';
            }

            this.syncInputs();
            this.updateMilestoneCards();
            this.renderCalendars();
        }

        applyAutoRangePreset() {
            if (this.mode === 'punctual') {
                if (this.shootDates.length === 0) {
                    alert("Veuillez d'abord sélectionner au moins une date de tournage sur le calendrier.");
                    this.activeMilestone = 'shoot_dates';
                    this.updateMilestoneCards();
                    return;
                }
                const first = this.shootDates[0];
                const last = this.shootDates[this.shootDates.length - 1];
                this.dates.departure = this.addDays(first, -1);
                this.dates.return = this.addDays(last, 1);
            } else {
                if (!this.dates.shoot_start) {
                    alert("Veuillez d'abord sélectionner une date de début de tournage.");
                    this.activeMilestone = 'shoot_start';
                    this.updateMilestoneCards();
                    return;
                }
                const shootStart = this.dates.shoot_start;
                const shootEnd = this.dates.shoot_end || shootStart;
                this.dates.departure = this.addDays(shootStart, -1);
                this.dates.shoot_end = shootEnd;
                this.dates.return = this.addDays(shootEnd, 1);
            }

            this.syncInputs();
            this.updateMilestoneCards();
            this.renderCalendars();
        }

        setMode(newMode) {
            if (this.mode === newMode) return;
            this.mode = newMode;

            if (newMode === 'punctual') {
                this.activeMilestone = 'shoot_dates';
                if (this.shootDates.length === 0) {
                    if (this.dates.shoot_start) {
                        this.shootDates.push(this.dates.shoot_start);
                    }
                    if (this.dates.shoot_end && this.dates.shoot_end !== this.dates.shoot_start) {
                        this.shootDates.push(this.dates.shoot_end);
                    }
                    this.shootDates.sort();
                }
            } else {
                this.activeMilestone = 'departure';
                if (this.shootDates.length > 0) {
                    this.dates.shoot_start = this.shootDates[0];
                    this.dates.shoot_end = this.shootDates[this.shootDates.length - 1];
                }
            }

            this.renderLayout();
            this.updateMilestoneCards();
            this.renderIntervalsSection();
            this.renderCalendars();
            this.syncInputs();
            this.refreshIcons();
        }

        toggleImmobilization() {
            this.isImmobilized = !this.isImmobilized;
            const intervals = this.calculateIntervals();
            intervals.forEach(inter => {
                this.interShootStatuses[inter.key] = this.isImmobilized;
            });
            this.renderLayout();
            this.updateMilestoneCards();
            this.renderIntervalsSection();
            this.renderCalendars();
            this.syncInputs();
            this.refreshIcons();
        }

        bindEvents() {
            // Bascule de Mode (Tabs)
            this.container.addEventListener('click', (e) => {
                const tab = e.target.closest('.pdp-mode-tab');
                if (tab) {
                    e.preventDefault();
                    const newMode = tab.dataset.mode;
                    if (newMode) {
                        this.setMode(newMode);
                    }
                }
            });

            // Clic sur les boutons de sélection d'intervalle
            this.container.addEventListener('click', (e) => {
                const btn = e.target.closest('.pdp-interval-btn');
                if (btn) {
                    e.preventDefault();
                    e.stopPropagation();
                    const key = btn.dataset.key;
                    const isImmob = btn.dataset.immob === 'true';
                    if (key) {
                        this.setIntervalImmobilization(key, isImmob);
                    }
                }
            });

            // Clic sur une carte de jalon pour l'activer ou basculer l'immobilisation
            this.container.addEventListener('click', (e) => {
                const card = e.target.closest('.pdp-milestone-card');
                if (card && !e.target.closest('.pdp-milestone-actions')) {
                    const milestone = card.dataset.milestone;
                    if (milestone === 'immobilization' || e.target.closest('#pdp-toggle-immob-btn')) {
                        e.preventDefault();
                        this.toggleImmobilization();
                        return;
                    }
                    if (milestone) {
                        this.activeMilestone = milestone;
                        this.quickMode = null;
                        this.updateMilestoneCards();
                    }
                }
            });

            // Actions sur les mini-boutons (+/- jours, clear, vider dates)
            this.container.addEventListener('click', (e) => {
                const btn = e.target.closest('.pdp-mini-btn');
                if (!btn) return;

                e.stopPropagation();
                const action = btn.dataset.action;
                const target = btn.dataset.target;

                if (action === 'clear') {
                    this.dates[target] = null;
                    this.syncInputs();
                    this.updateMilestoneCards();
                    this.renderCalendars();
                } else if (action === 'clear-shoot-dates') {
                    this.shootDates = [];
                    this.dates.shoot_start = null;
                    this.dates.shoot_end = null;
                    this.syncInputs();
                    this.updateMilestoneCards();
                    this.renderIntervalsSection();
                    this.renderCalendars();
                } else if (action === 'shift') {
                    const delta = parseInt(btn.dataset.delta, 10) || 0;
                    if (this.dates[target]) {
                        this.dates[target] = this.addDays(this.dates[target], delta);
                        this.syncInputs();
                        this.updateMilestoneCards();
                        this.renderCalendars();
                    } else if (this.dates.shoot_start) {
                        this.dates[target] = this.addDays(this.dates.shoot_start, delta);
                        this.syncInputs();
                        this.updateMilestoneCards();
                        this.renderCalendars();
                    }
                }
            });

            // Raccourci Auto Range
            this.container.addEventListener('click', (e) => {
                if (e.target.closest('#pdp-preset-auto-range')) {
                    e.preventDefault();
                    this.applyAutoRangePreset();
                }
            });

            // Raccourci Shoot 1 Jour (mode continu)
            this.container.addEventListener('click', (e) => {
                if (e.target.closest('#pdp-preset-1day')) {
                    e.preventDefault();
                    this.quickMode = 'shoot_1d';
                    this.activeMilestone = 'shoot_start';
                    this.updateMilestoneCards();
                    alert("👉 Cliquez sur le jour du tournage dans le calendrier pour appliquer le shoot d'un jour (Prépa J-1, Tournage, Retour J+1).");
                }
            });

            // Raccourci bascule immobilisation dans la barre d'outils
            this.container.addEventListener('click', (e) => {
                if (e.target.closest('#pdp-preset-toggle-immob')) {
                    e.preventDefault();
                    this.toggleImmobilization();
                }
            });

            // Raccourci Aujourd'hui
            this.container.addEventListener('click', (e) => {
                if (e.target.closest('#pdp-btn-today')) {
                    e.preventDefault();
                    const now = new Date();
                    this.currentYear = now.getFullYear();
                    this.currentMonth = now.getMonth();
                    this.renderCalendars();
                }
            });

            // Bouton Reset Tout
            this.container.addEventListener('click', (e) => {
                if (e.target.closest('#pdp-btn-reset')) {
                    e.preventDefault();
                    if (confirm("Voulez-vous réinitialiser toutes les dates de ce projet ?")) {
                        this.dates = {
                            departure: null,
                            shoot_start: null,
                            shoot_end: null,
                            return: null
                        };
                        this.shootDates = [];
                        this.activeMilestone = (this.mode === 'punctual') ? 'shoot_dates' : 'departure';
                        this.quickMode = null;
                        this.syncInputs();
                        this.updateMilestoneCards();
                        this.renderCalendars();
                    }
                }
            });
        }
    }

    // Exposer globalement
    window.ProjectTimelineDatePicker = ProjectTimelineDatePicker;

})(window, document);
