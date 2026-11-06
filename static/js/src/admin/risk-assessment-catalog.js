/**
 * risk-assessment-catalog.js — Contrôleur d'interface d'administration pour l'Analyse des Risques (BVRS).
 * 
 * Permet l'édition complète et interactive des risques généraux et spécifiques par véhicule :
 * - Niveau d'alerte (Risque Majeur / Risque Standard)
 * - Catégorisation, titres bilingues FR / EN, descriptions bilingues
 * - Recommandations dynamiques avec coches ✓
 * - Réorganisation (monter / descendre), suppression et ajout
 * - Sérialisation JSON avant soumission
 */

document.addEventListener('DOMContentLoaded', function () {
    const modal = document.getElementById('riskModal');
    if (!modal) return;

    const modalTitle = document.getElementById('riskModalTitle');
    const modalSubtitle = document.getElementById('riskModalSubtitle');
    const inputAction = document.getElementById('modal_risk_action');
    const inputVehicleKey = document.getElementById('modal_risk_vehicle_key');
    const inputLabel = document.getElementById('modal_risk_label');
    const wrapVehicleLabel = document.getElementById('modal_vehicle_label_wrap');
    const risksContainer = document.getElementById('bvrs-risks-container');
    const emptyState = document.getElementById('bvrs-risks-empty-state');
    const btnAddRisk = document.getElementById('btn-add-risk-item');
    const countBadge = document.getElementById('bvrs-risks-count-badge');
    const form = document.getElementById('riskForm');
    const modalIconWrap = document.getElementById('modalRiskIconWrap');

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function updateCount() {
        if (!risksContainer || !countBadge) return;
        const items = risksContainer.querySelectorAll('.bvrs-risk-edit-card');
        const count = items.length;
        countBadge.textContent = count + (count > 1 ? ' risques' : ' risque');

        if (emptyState) {
            if (count === 0) {
                emptyState.classList.remove('u-d-none');
            } else {
                emptyState.classList.add('u-d-none');
            }
        }
    }

    function openModal() {
        modal.classList.remove('u-d-none');
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('u-overflow-hidden');
        if (window.lucide) window.lucide.createIcons();
    }

    function closeModal() {
        modal.classList.add('u-d-none');
        modal.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('u-overflow-hidden');
    }

    // Fermeture modale
    document.querySelectorAll('.btn-close-risk-modal').forEach(function (btn) {
        btn.addEventListener('click', closeModal);
    });

    modal.addEventListener('click', function (e) {
        if (e.target === modal) closeModal();
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !modal.classList.contains('u-d-none')) {
            closeModal();
        }
    });

    function createRecElement(recFr, recEn) {
        const wrap = document.createElement('div');
        wrap.className = 'u-flex u-align-center u-gap-2 bvrs-rec-item u-mb-1';
        wrap.innerHTML = `
            <span class="u-text-success u-font-bold">✓</span>
            <input type="text" class="form-input form-input-sm u-flex-1 bvrs-rec-fr" placeholder="Recommandation FR..." value="${escapeHtml(recFr || '')}">
            <input type="text" class="form-input form-input-sm u-flex-1 bvrs-rec-en" placeholder="Recommendation EN (optionnel)..." value="${escapeHtml(recEn || '')}">
            <button type="button" class="admin-btn admin-btn-2xs admin-btn-danger btn-del-rec" title="Supprimer la recommandation">
                <i data-lucide="x"></i>
            </button>
        `;
        wrap.querySelector('.btn-del-rec').addEventListener('click', function () {
            wrap.remove();
        });
        return wrap;
    }

    function renderRiskCard(risk) {
        const card = document.createElement('div');
        const isMajor = (risk.level === 'major');
        card.className = `admin-card u-p-3 u-bg-white u-border bvrs-risk-edit-card ${isMajor ? 'bvrs-risk-edit-card--major' : 'bvrs-risk-edit-card--standard'}`;

        const level = risk.level || 'standard';
        const category = risk.category_fr || risk.category || 'ZONE DE TOURNAGE';
        const titleFr = risk.title_fr || risk.title || '';
        const titleEn = risk.title_en || '';
        const descFr = risk.description_fr || risk.description || '';
        const descEn = risk.description_en || '';
        const recsFr = risk.recommendations_fr || risk.recommendations || [];
        const recsEn = risk.recommendations_en || [];

        card.innerHTML = `
            <div class="u-flex u-justify-between u-align-center u-mb-3 u-flex-wrap u-gap-2">
                <div class="u-flex u-align-center u-gap-2 u-flex-wrap">
                    <select class="form-input form-input-sm bvrs-risk-level-select u-w-auto u-font-bold">
                        <option value="major" ${level === 'major' ? 'selected' : ''} class="u-text-danger">⚠️ RISQUE MAJEUR</option>
                        <option value="standard" ${level === 'standard' ? 'selected' : ''} class="u-text-warning">⚠️ RISQUE STANDARD</option>
                    </select>
                    <input type="text" class="form-input form-input-sm bvrs-risk-category-input u-w-220 u-text-2xs u-uppercase" placeholder="Catégorie (ex: ZONE DE TOURNAGE)" value="${escapeHtml(category)}">
                </div>
                <div class="u-flex u-align-center u-gap-1">
                    <button type="button" class="admin-btn admin-btn-xs admin-btn-secondary btn-move-risk-up" title="Monter">
                        <i data-lucide="chevron-up"></i>
                    </button>
                    <button type="button" class="admin-btn admin-btn-xs admin-btn-secondary btn-move-risk-down" title="Descendre">
                        <i data-lucide="chevron-down"></i>
                    </button>
                    <button type="button" class="admin-btn admin-btn-xs admin-btn-danger btn-delete-risk" title="Supprimer ce risque">
                        <i data-lucide="trash-2"></i>
                    </button>
                </div>
            </div>

            <div class="u-grid u-gap-2 u-grid-cols-2 u-mb-2">
                <div>
                    <label class="form-label u-text-2xs u-font-bold u-mb-1">Titre (FR) <span class="u-text-danger">*</span></label>
                    <input type="text" class="form-input form-input-sm bvrs-risk-title-fr" placeholder="ex: Intrusion dans la zone de roulage" value="${escapeHtml(titleFr)}" required>
                </div>
                <div>
                    <label class="form-label u-text-2xs u-font-bold u-mb-1">Titre (EN)</label>
                    <input type="text" class="form-input form-input-sm bvrs-risk-title-en" placeholder="ex: Intrusion into the Driving Area" value="${escapeHtml(titleEn)}">
                </div>
            </div>

            <div class="u-grid u-gap-2 u-grid-cols-2 u-mb-3">
                <div>
                    <label class="form-label u-text-2xs u-font-bold u-mb-1">Description du danger (FR)</label>
                    <textarea class="form-input form-input-sm bvrs-risk-desc-fr u-h-60" placeholder="Description détaillée du danger en français...">${escapeHtml(descFr)}</textarea>
                </div>
                <div>
                    <label class="form-label u-text-2xs u-font-bold u-mb-1">Description du danger (EN)</label>
                    <textarea class="form-input form-input-sm bvrs-risk-desc-en u-h-60" placeholder="Detailed description in English...">${escapeHtml(descEn)}</textarea>
                </div>
            </div>

            <div class="u-border-top u-pt-2">
                <div class="u-flex u-justify-between u-align-center u-mb-2">
                    <span class="u-text-2xs u-uppercase u-font-bold u-text-muted">Recommandations (Coches ✓)</span>
                    <button type="button" class="admin-btn admin-btn-2xs admin-btn-secondary btn-add-rec">
                        <i data-lucide="plus"></i> Ajouter une recommandation
                    </button>
                </div>
                <div class="bvrs-recs-container u-flex u-flex-column u-gap-1"></div>
            </div>
        `;

        // Switch niveau dynamique
        const levelSelect = card.querySelector('.bvrs-risk-level-select');
        levelSelect.addEventListener('change', function () {
            if (this.value === 'major') {
                card.classList.remove('bvrs-risk-edit-card--standard');
                card.classList.add('bvrs-risk-edit-card--major');
            } else {
                card.classList.remove('bvrs-risk-edit-card--major');
                card.classList.add('bvrs-risk-edit-card--standard');
            }
        });

        // Déplacement / suppression
        card.querySelector('.btn-delete-risk').addEventListener('click', function () {
            if (confirm('Voulez-vous supprimer ce risque du catalogue ?')) {
                card.remove();
                updateCount();
            }
        });

        card.querySelector('.btn-move-risk-up').addEventListener('click', function () {
            const prev = card.previousElementSibling;
            if (prev) {
                risksContainer.insertBefore(card, prev);
            }
        });

        card.querySelector('.btn-move-risk-down').addEventListener('click', function () {
            const next = card.nextElementSibling;
            if (next) {
                risksContainer.insertBefore(next, card);
            }
        });

        // Recommandations
        const recsContainer = card.querySelector('.bvrs-recs-container');
        const maxLen = Math.max(recsFr.length, recsEn.length);
        for (let i = 0; i < maxLen; i++) {
            recsContainer.appendChild(createRecElement(recsFr[i] || '', recsEn[i] || ''));
        }

        card.querySelector('.btn-add-rec').addEventListener('click', function () {
            const newRec = createRecElement('', '');
            recsContainer.appendChild(newRec);
            const input = newRec.querySelector('.bvrs-rec-fr');
            if (input) input.focus();
            if (window.lucide) window.lucide.createIcons();
        });

        return card;
    }

    function populateRisks(risksList) {
        risksContainer.innerHTML = '';
        if (Array.isArray(risksList)) {
            risksList.forEach(function (r) {
                risksContainer.appendChild(renderRiskCard(r));
            });
        }
        updateCount();
        if (window.lucide) window.lucide.createIcons();
    }

    // ── Bouton Édition Risques Généraux ──
    const btnEditGeneral = document.querySelector('.btn-edit-general-risks');
    if (btnEditGeneral) {
        btnEditGeneral.addEventListener('click', function () {
            inputAction.value = 'save_general';
            inputVehicleKey.value = '';
            wrapVehicleLabel.classList.add('u-d-none');
            if (inputLabel) inputLabel.removeAttribute('required');

            modalTitle.textContent = 'Modifier les Risques Généraux : Véhicules Travelling';
            modalSubtitle.textContent = 'Consignes transversales applicables à tous les tournages travelling Belle Vitesse';
            modalIconWrap.className = 'badge-pill u-bg-danger-light u-text-danger';
            modalIconWrap.innerHTML = '<i data-lucide="shield-alert" class="u-w-24 u-h-24 u-m-0"></i>';

            let risksData = [];
            try {
                risksData = JSON.parse(this.dataset.risks || '[]');
            } catch (err) {
                console.error('Erreur parsing risks dataset :', err);
            }
            populateRisks(risksData);
            openModal();
        });
    }

    // ── Boutons Édition Risques Véhicules ──
    document.querySelectorAll('.btn-edit-vehicle-risks').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const vKey = this.dataset.key || '';
            let catData = {};
            try {
                catData = JSON.parse(this.dataset.cat || '{}');
            } catch (err) {
                console.error('Erreur parsing cat dataset :', err);
            }

            inputAction.value = 'save_vehicle';
            inputVehicleKey.value = vKey;
            wrapVehicleLabel.classList.remove('u-d-none');
            if (inputLabel) {
                inputLabel.setAttribute('required', 'required');
                inputLabel.value = catData.label || catData.name || vKey;
            }

            modalTitle.textContent = 'Modifier les Risques Spécifiques Véhicule';
            modalSubtitle.textContent = `Famille : ${catData.label || catData.name || vKey}`;
            if (catData.image) {
                modalIconWrap.className = 'bvsr-modal-avatar';
                modalIconWrap.innerHTML = `<img src="${escapeHtml(catData.image)}" alt="${escapeHtml(catData.name || vKey)}" class="bvsr-vehicle-img">`;
            } else {
                modalIconWrap.className = 'badge-pill u-bg-waiver-light u-text-waiver';
                modalIconWrap.innerHTML = '<i data-lucide="truck" class="u-w-24 u-h-24 u-m-0"></i>';
            }

            populateRisks(catData.risks || []);
            openModal();
        });
    });

    // ── Bouton Ajouter un risque ──
    if (btnAddRisk) {
        btnAddRisk.addEventListener('click', function () {
            const newRisk = {
                level: 'standard',
                category_fr: 'ZONE DE TOURNAGE',
                category_en: 'SHOOTING AREA',
                title_fr: '',
                title_en: '',
                description_fr: '',
                description_en: '',
                recommendations_fr: [''],
                recommendations_en: ['']
            };
            const card = renderRiskCard(newRisk);
            risksContainer.appendChild(card);
            updateCount();
            if (window.lucide) window.lucide.createIcons();

            const inputTitle = card.querySelector('.bvrs-risk-title-fr');
            if (inputTitle) {
                inputTitle.focus();
                inputTitle.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    }

    // ── Soumission Formulaire & Sérialisation JSON ──
    form.addEventListener('submit', function (e) {
        const cards = risksContainer.querySelectorAll('.bvrs-risk-edit-card');
        const serialized = [];

        for (let i = 0; i < cards.length; i++) {
            const card = cards[i];
            const level = card.querySelector('.bvrs-risk-level-select').value;
            const catFr = card.querySelector('.bvrs-risk-category-input').value.trim() || 'ZONE DE TOURNAGE';
            const titleFr = card.querySelector('.bvrs-risk-title-fr').value.trim();
            const titleEn = card.querySelector('.bvrs-risk-title-en').value.trim();
            const descFr = card.querySelector('.bvrs-risk-desc-fr').value.trim();
            const descEn = card.querySelector('.bvrs-risk-desc-en').value.trim();

            if (!titleFr) {
                alert(`Veuillez renseigner un titre en français pour le risque n° ${i + 1}.`);
                e.preventDefault();
                card.querySelector('.bvrs-risk-title-fr').focus();
                return;
            }

            const recsFr = [];
            const recsEn = [];
            card.querySelectorAll('.bvrs-rec-item').forEach(function (recItem) {
                const rFr = recItem.querySelector('.bvrs-rec-fr').value.trim();
                const rEn = recItem.querySelector('.bvrs-rec-en').value.trim();
                if (rFr || rEn) {
                    recsFr.push(rFr || rEn);
                    recsEn.push(rEn || rFr);
                }
            });

            serialized.push({
                id: titleFr.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, ''),
                level: level,
                category_fr: catFr,
                category_en: catFr,
                title_fr: titleFr,
                title_en: titleEn || titleFr,
                description_fr: descFr,
                description_en: descEn || descFr,
                recommendations_fr: recsFr,
                recommendations_en: recsEn
            });
        }

        const jsonInput = document.getElementById('modal_risks_json');
        jsonInput.value = JSON.stringify(serialized);
    });
});

