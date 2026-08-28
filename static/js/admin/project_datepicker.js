/**
 * ProjectTimelineDatePicker - Belle Vitesse
 * Sélecteur de dates interactif multi-jalons pour projets
 * (Prépa / Départ, Début Tournage, Fin Tournage, Retour)
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

            this.inputDeparture = document.getElementById(options.inputDepartureId || 'departure_date_input');
            this.inputShootStart = document.getElementById(options.inputShootStartId || 'shoot_start_input');
            this.inputShootEnd = document.getElementById(options.inputShootEndId || 'shoot_end_input');
            this.inputReturn = document.getElementById(options.inputReturnId || 'return_date_input');

            // État des dates (Format 'YYYY-MM-DD')
            this.dates = {
                departure: this.inputDeparture ? this.inputDeparture.value || null : null,
                shoot_start: this.inputShootStart ? this.inputShootStart.value || null : null,
                shoot_end: this.inputShootEnd ? this.inputShootEnd.value || null : null,
                return: this.inputReturn ? this.inputReturn.value || null : null
            };

            // Jalon actif sélectionné ('departure', 'shoot_start', 'shoot_end', 'return')
            this.activeMilestone = 'departure';
            this.quickMode = null; // 'shoot_1d', 'auto_range', or null

            // Mois affiché pour le 1er calendrier
            const initialDate = this.dates.shoot_start || this.dates.departure || new Date();
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
            this.renderCalendars();
            this.bindEvents();
        }

        renderLayout() {
            this.container.innerHTML = `
                <div class="project-datepicker-container">
                    <!-- Cartes des 4 Jalons -->
                    <div class="pdp-milestones-grid">
                        <div class="pdp-milestone-card type-departure" data-milestone="departure">
                            <div class="pdp-milestone-header">
                                <span class="pdp-milestone-label">📦 Prépa / Départ</span>
                                <span class="pdp-step-badge">1</span>
                            </div>
                            <div class="pdp-milestone-date" id="pdp-date-departure">Non définie</div>
                            <div class="pdp-milestone-actions">
                                <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="departure" data-delta="-1">-1j</button>
                                <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="departure" data-delta="1">+1j</button>
                                <button type="button" class="pdp-mini-btn btn-clear" data-action="clear" data-target="departure" title="Effacer">×</button>
                            </div>
                        </div>

                        <div class="pdp-milestone-card type-shoot_start" data-milestone="shoot_start">
                            <div class="pdp-milestone-header">
                                <span class="pdp-milestone-label">🎬 Début Tournage</span>
                                <span class="pdp-step-badge">2</span>
                            </div>
                            <div class="pdp-milestone-date" id="pdp-date-shoot_start">Non définie</div>
                            <div class="pdp-milestone-actions">
                                <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="shoot_start" data-delta="-1">-1j</button>
                                <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="shoot_start" data-delta="1">+1j</button>
                                <button type="button" class="pdp-mini-btn btn-clear" data-action="clear" data-target="shoot_start" title="Effacer">×</button>
                            </div>
                        </div>

                        <div class="pdp-milestone-card type-shoot_end" data-milestone="shoot_end">
                            <div class="pdp-milestone-header">
                                <span class="pdp-milestone-label">🏁 Fin Tournage</span>
                                <span class="pdp-step-badge">3</span>
                            </div>
                            <div class="pdp-milestone-date" id="pdp-date-shoot_end">Non définie</div>
                            <div class="pdp-milestone-actions">
                                <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="shoot_end" data-delta="-1">-1j</button>
                                <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="shoot_end" data-delta="1">+1j</button>
                                <button type="button" class="pdp-mini-btn btn-clear" data-action="clear" data-target="shoot_end" title="Effacer">×</button>
                            </div>
                        </div>

                        <div class="pdp-milestone-card type-return" data-milestone="return">
                            <div class="pdp-milestone-header">
                                <span class="pdp-milestone-label">🔄 Retour Matériel</span>
                                <span class="pdp-step-badge">4</span>
                            </div>
                            <div class="pdp-milestone-date" id="pdp-date-return">Non définie</div>
                            <div class="pdp-milestone-actions">
                                <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="return" data-delta="-1">-1j</button>
                                <button type="button" class="pdp-mini-btn btn-shift" data-action="shift" data-target="return" data-delta="1">+1j</button>
                                <button type="button" class="pdp-mini-btn btn-clear" data-action="clear" data-target="return" title="Effacer">×</button>
                            </div>
                        </div>
                    </div>

                    <!-- Barre d'outils et Raccourcis -->
                    <div class="pdp-toolbar">
                        <div class="pdp-presets-group">
                            <span class="pdp-preset-label">⚡ Raccourcis :</span>
                            <button type="button" class="pdp-preset-btn btn-highlight" id="pdp-preset-auto-range" title="Caler automatiquement la Prépa à J-1 et le Retour à J+1 autour de la plage de shoot">
                                🪄 Auto Prépa (J-1) / Retour (J+1)
                            </button>
                            <button type="button" class="pdp-preset-btn" id="pdp-preset-1day" title="Cliquez sur le jour du tournage pour créer un shoot d'1 jour avec prépa J-1 et retour J+1">
                                ⚡ Shoot 1 jour complet
                            </button>
                        </div>
                        <div class="pdp-actions-group">
                            <button type="button" class="pdp-preset-btn" id="pdp-btn-today">Aujourd'hui</button>
                            <button type="button" class="pdp-preset-btn pdp-btn-reset" id="pdp-btn-reset" style="color: #ef4444;">↺ Effacer les dates</button>
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
                                <span>Prépa / Départ</span>
                            </div>
                            <div class="pdp-legend-item">
                                <div class="pdp-legend-swatch swatch-shoot"></div>
                                <span>Tournage</span>
                            </div>
                            <div class="pdp-legend-item">
                                <div class="pdp-legend-swatch swatch-ret"></div>
                                <span>Retour Matériel</span>
                            </div>
                        </div>
                        <div style="font-style: italic;">
                            Cliquez sur un jour pour placer le jalon actif ou sélectionnez une puce ci-dessus.
                        </div>
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
            return `${parts[2]}/${parts[1]}/${parts[0]}`;
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

        updateMilestoneCards() {
            // Mettre à jour les labels de date
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

            // Synchroniser avec les inputs du formulaire
            if (this.inputDeparture) this.inputDeparture.value = this.dates.departure || '';
            if (this.inputShootStart) this.inputShootStart.value = this.dates.shoot_start || '';
            if (this.inputShootEnd) this.inputShootEnd.value = this.dates.shoot_end || '';
            if (this.inputReturn) this.inputReturn.value = this.dates.return || '';
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
        }

        buildMonthHtml(year, month, showPrev, showNext) {
            const firstDayIndex = new Date(year, month, 1).getDay(); // 0 = Dimanche
            const startOffset = (firstDayIndex + 6) % 7; // Convertir en Lundi = 0
            const daysInMonth = new Date(year, month + 1, 0).getDate();

            const todayIso = this.toIsoString(new Date());

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
                const isShootStart = this.dates.shoot_start === dateIso;
                const isShootEnd = this.dates.shoot_end === dateIso;
                const isRet = this.dates.return === dateIso;

                // Plage de tournage
                if (this.dates.shoot_start && this.dates.shoot_end) {
                    if (dateIso >= this.dates.shoot_start && dateIso <= this.dates.shoot_end) {
                        classes.push('in-shoot-range');
                    }
                }

                if (isShootStart) classes.push('shoot-start-day');
                if (isShootEnd) classes.push('shoot-end-day');
                if (isDep) classes.push('departure-day');
                if (isRet) classes.push('return-day');

                // Badges/dots si chevauchement
                let dotsHtml = '';
                const dots = [];
                if (isDep) dots.push('dot-dep');
                if (isShootStart || isShootEnd) dots.push('dot-shoot');
                if (isRet) dots.push('dot-ret');

                if (dots.length > 1) {
                    dotsHtml = `<div class="pdp-day-badges">${dots.map(dt => `<div class="pdp-dot ${dt}"></div>`).join('')}</div>`;
                }

                daysHtml += `
                    <div class="${classes.join(' ')}" data-date="${dateIso}">
                        <span>${d}</span>
                        ${dotsHtml}
                    </div>
                `;
            }

            return `
                <div class="pdp-month-card">
                    <div class="pdp-month-header">
                        ${showPrev ? '<button type="button" class="pdp-nav-btn" id="pdp-prev-month" title="Mois précédent">‹</button>' : '<div style="width:32px;"></div>'}
                        <div class="pdp-month-title">${this.monthNames[month]} ${year}</div>
                        ${showNext ? '<button type="button" class="pdp-nav-btn" id="pdp-next-month" title="Mois suivant">›</button>' : '<div style="width:32px;"></div>'}
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
            // Mode spécial : 1 Jour Complet
            if (this.quickMode === 'shoot_1d') {
                this.dates.departure = this.addDays(dateStr, -1);
                this.dates.shoot_start = dateStr;
                this.dates.shoot_end = dateStr;
                this.dates.return = this.addDays(dateStr, 1);
                this.quickMode = null;
                this.activeMilestone = 'shoot_end';
                this.updateMilestoneCards();
                this.renderCalendars();
                return;
            }

            // Mode normal : assigner le jalon actif
            const current = this.activeMilestone;
            this.dates[current] = dateStr;

            // Logique de transition intelligente
            if (current === 'departure') {
                this.activeMilestone = 'shoot_start';
            } else if (current === 'shoot_start') {
                // Si la date de fin n'est pas encore définie ou antérieure, on la positionne par défaut
                if (!this.dates.shoot_end || this.dates.shoot_end < dateStr) {
                    this.dates.shoot_end = dateStr;
                }
                this.activeMilestone = 'shoot_end';
            } else if (current === 'shoot_end') {
                // Si la date de fin est antérieure à la date de début, inverser ou ajuster
                if (this.dates.shoot_start && dateStr < this.dates.shoot_start) {
                    this.dates.shoot_end = this.dates.shoot_start;
                    this.dates.shoot_start = dateStr;
                }
                // Si le retour n'est pas défini, proposer J+1
                if (!this.dates.return || this.dates.return < this.dates.shoot_end) {
                    this.dates.return = this.addDays(this.dates.shoot_end, 1);
                }
                this.activeMilestone = 'return';
            } else if (current === 'return') {
                // Terminé, on reste ou boucle
                this.activeMilestone = 'departure';
            }

            this.updateMilestoneCards();
            this.renderCalendars();
        }

        applyAutoRangePreset() {
            // Si on a un début et fin de shoot, on cale prépa J-1 et retour J+1
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

            this.updateMilestoneCards();
            this.renderCalendars();
        }

        bindEvents() {
            // Clic sur une carte de jalon pour l'activer
            this.container.addEventListener('click', (e) => {
                const card = e.target.closest('.pdp-milestone-card');
                if (card && !e.target.closest('.pdp-milestone-actions')) {
                    const milestone = card.dataset.milestone;
                    if (milestone) {
                        this.activeMilestone = milestone;
                        this.quickMode = null;
                        this.updateMilestoneCards();
                    }
                }
            });

            // Actions sur les mini-boutons (+/- jours, clear)
            this.container.addEventListener('click', (e) => {
                const btn = e.target.closest('.pdp-mini-btn');
                if (!btn) return;

                e.stopPropagation();
                const action = btn.dataset.action;
                const target = btn.dataset.target;

                if (action === 'clear') {
                    this.dates[target] = null;
                    this.updateMilestoneCards();
                    this.renderCalendars();
                } else if (action === 'shift') {
                    const delta = parseInt(btn.dataset.delta, 10) || 0;
                    if (this.dates[target]) {
                        this.dates[target] = this.addDays(this.dates[target], delta);
                        this.updateMilestoneCards();
                        this.renderCalendars();
                    } else if (this.dates.shoot_start) {
                        this.dates[target] = this.addDays(this.dates.shoot_start, delta);
                        this.updateMilestoneCards();
                        this.renderCalendars();
                    }
                }
            });

            // Raccourci Auto Range
            const autoRangeBtn = this.container.querySelector('#pdp-preset-auto-range');
            if (autoRangeBtn) {
                autoRangeBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.applyAutoRangePreset();
                });
            }

            // Raccourci Shoot 1 Jour
            const shoot1dBtn = this.container.querySelector('#pdp-preset-1day');
            if (shoot1dBtn) {
                shoot1dBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.quickMode = 'shoot_1d';
                    this.activeMilestone = 'shoot_start';
                    this.updateMilestoneCards();
                    alert("👉 Cliquez sur le jour du tournage dans le calendrier pour appliquer le shoot d'un jour (Prépa J-1, Tournage, Retour J+1).");
                });
            }

            // Raccourci Aujourd'hui
            const todayBtn = this.container.querySelector('#pdp-btn-today');
            if (todayBtn) {
                todayBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    const now = new Date();
                    this.currentYear = now.getFullYear();
                    this.currentMonth = now.getMonth();
                    this.renderCalendars();
                });
            }

            // Bouton Reset Tout
            const resetBtn = this.container.querySelector('#pdp-btn-reset');
            if (resetBtn) {
                resetBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    if (confirm("Voulez-vous réinitialiser toutes les dates de ce projet ?")) {
                        this.dates = {
                            departure: null,
                            shoot_start: null,
                            shoot_end: null,
                            return: null
                        };
                        this.activeMilestone = 'departure';
                        this.quickMode = null;
                        this.updateMilestoneCards();
                        this.renderCalendars();
                    }
                });
            }
        }
    }

    // Exposer globalement
    window.ProjectTimelineDatePicker = ProjectTimelineDatePicker;

})(window, document);
