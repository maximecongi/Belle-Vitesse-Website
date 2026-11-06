/**
 * risk-assessment-catalog.js — Contrôleur d'interface d'administration pour l'Analyse des Risques (BVRS).
 * 
 * Version 2.0 (Design System Belle Vitesse) :
 * - Navigation par onglets de catégories horizontaux (Pill Tabs) avec compteur dynamique
 * - Vue « Tous les risques » et filtres par catégorie dédiée
 * - Cartes accordéons compactes (dépliables/repliables) avec prévisualisation bilingue
 * - Switch de sévérité ergonomique (Majeur / Standard)
 * - Création dynamique de nouvelles catégories à la volée
 * - Réorganisation et suppression contextuelles
 * - Sérialisation JSON robuste avant soumission
 */

function initRiskAssessmentCatalog() {
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
    const btnToggleAllCards = document.getElementById('btn-toggle-all-cards');
    const toggleAllLabel = document.getElementById('toggle-all-label');
    const countBadge = document.getElementById('bvrs-risks-count-badge');
    const activeCatName = document.getElementById('bvrs-active-cat-name');
    const activeCatDisplay = document.getElementById('bvrs-active-cat-display');
    const btnRenameCategory = document.getElementById('btn-rename-category');
    const renameCatWrap = document.getElementById('bvrs-rename-cat-wrap');
    const renameCatInput = document.getElementById('bvrs-rename-cat-input');
    const btnConfirmRename = document.getElementById('btn-confirm-rename-cat');
    const btnCancelRename = document.getElementById('btn-cancel-rename-cat');
    const tabsContainer = document.getElementById('bvrs-category-tabs');
    const form = document.getElementById('riskForm');
    const modalIconWrap = document.getElementById('modalRiskIconWrap');

    // Badges KPI d'en-tête de modale
    const headerMajorCount = document.getElementById('modalRiskMajorCount');
    const headerStdCount = document.getElementById('modalRiskStdCount');
    const headerTotalCount = document.getElementById('modalRiskTotalCount');

    let currentActiveCategory = 'all';

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function openModal() {
        modal.classList.remove('u-d-none');
        modal.classList.add('is-active');
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('u-overflow-hidden');
        if (window.lucide) window.lucide.createIcons();
    }

    function closeModal() {
        modal.classList.add('u-d-none');
        modal.classList.remove('is-active');
        modal.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('u-overflow-hidden');
    }

    // Gestion de la fermeture modale
    document.querySelectorAll('.btn-close-risk-modal').forEach(function (btn) {
        btn.addEventListener('click', closeModal);
    });

    modal.addEventListener('click', function (e) {
        if (e.target === modal) closeModal();
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && (modal.classList.contains('is-active') || !modal.classList.contains('u-d-none'))) {
            closeModal();
        }
    });

    // ── Extraction des catégories uniques ──
    function getCategoriesList() {
        const categories = [];
        const cards = risksContainer.querySelectorAll('.bvrs-risk-accordion');
        cards.forEach(function (card) {
            const cat = (card.dataset.category || '').trim().toUpperCase();
            if (cat && !categories.includes(cat)) {
                categories.push(cat);
            }
        });
        if (categories.length === 0) {
            categories.push('ZONE DE TOURNAGE');
        }
        return categories;
    }

    // ── Mise à jour des onglets et compteurs ──
    function refreshTabsAndCounters() {
        if (!tabsContainer || !risksContainer) return;

        const cards = risksContainer.querySelectorAll('.bvrs-risk-accordion');
        let totalCount = cards.length;
        let majorCount = 0;
        let stdCount = 0;

        const catCounts = {};
        cards.forEach(function (card) {
            const isMajor = card.classList.contains('bvrs-risk-accordion--major');
            if (isMajor) majorCount++; else stdCount++;

            const cat = (card.dataset.category || '').trim().toUpperCase() || 'ZONE DE TOURNAGE';
            catCounts[cat] = (catCounts[cat] || 0) + 1;
        });

        // 1. Mise à jour des badges d'en-tête
        if (headerMajorCount) {
            headerMajorCount.textContent = `${majorCount} majeur${majorCount > 1 ? 's' : ''}`;
        }
        if (headerStdCount) {
            headerStdCount.textContent = `${stdCount} standard${stdCount > 1 ? 's' : ''}`;
        }
        if (headerTotalCount) {
            headerTotalCount.textContent = `${totalCount} risque${totalCount > 1 ? 's' : ''}`;
        }

        // 2. Construction des onglets de catégories
        tabsContainer.innerHTML = '';

        // Onglet « Tous les risques »
        const allTab = document.createElement('button');
        allTab.type = 'button';
        allTab.className = `bvrs-category-tab ${currentActiveCategory === 'all' ? 'is-active' : ''}`;
        allTab.innerHTML = `<span>Tous les risques</span><span class="bvrs-tab-badge">${totalCount}</span>`;
        allTab.addEventListener('click', function () {
            setActiveCategory('all');
        });
        tabsContainer.appendChild(allTab);

        // Onglets par catégorie
        const categories = getCategoriesList();
        categories.forEach(function (cat) {
            const count = catCounts[cat] || 0;
            const tab = document.createElement('button');
            tab.type = 'button';
            tab.className = `bvrs-category-tab ${currentActiveCategory === cat ? 'is-active' : ''}`;
            tab.innerHTML = `<span>${escapeHtml(cat)}</span><span class="bvrs-tab-badge">${count}</span>`;
            tab.title = 'Cliquer pour filtrer • Double-cliquer pour renommer';
            tab.addEventListener('click', function () {
                setActiveCategory(cat);
            });
            // Double-clic sur l'onglet pour renommer directement
            tab.addEventListener('dblclick', function (e) {
                e.preventDefault();
                setActiveCategory(cat);
                openRenameCategory();
            });
            tabsContainer.appendChild(tab);
        });

        // Pilule '+ Catégorie' intégrée en dernière position du ruban d'onglets (mêmes proportions exactes)
        const addCatPill = document.createElement('button');
        addCatPill.type = 'button';
        addCatPill.className = 'bvrs-category-tab bvrs-category-tab--add';
        addCatPill.title = 'Créer une nouvelle catégorie';
        addCatPill.innerHTML = `<span>Catégorie</span><span class="bvrs-tab-badge bvrs-tab-badge--add"><i data-lucide="plus" class="u-w-12 u-h-12"></i></span>`;
        addCatPill.addEventListener('click', function (e) {
            e.stopPropagation();
            showInlineCategoryInput(addCatPill);
        });
        tabsContainer.appendChild(addCatPill);

        // Vérifier si la catégorie active existe toujours
        if (currentActiveCategory !== 'all' && !categories.includes(currentActiveCategory)) {
            currentActiveCategory = 'all';
        }

        filterRisks();
        if (window.lucide) window.lucide.createIcons();
    }

    // ── Saisie inline d'une nouvelle catégorie dans le ruban ──
    function showInlineCategoryInput(targetPill) {
        const wrap = document.createElement('div');
        wrap.className = 'bvrs-category-tab-inline-wrap';
        wrap.innerHTML = `
            <input type="text" class="bvrs-category-inline-input" placeholder="NOM CATÉGORIE..." maxlength="40">
            <button type="button" class="bvrs-category-inline-btn bvrs-category-inline-btn--confirm" title="Valider (Entrée ↵)">
                <i data-lucide="check" class="u-w-14 u-h-14"></i>
            </button>
            <button type="button" class="bvrs-category-inline-btn bvrs-category-inline-btn--cancel" title="Annuler (Échap)">
                <i data-lucide="x" class="u-w-14 u-h-14"></i>
            </button>
        `;

        targetPill.replaceWith(wrap);
        if (window.lucide) window.lucide.createIcons();

        const input = wrap.querySelector('.bvrs-category-inline-input');
        const btnConfirm = wrap.querySelector('.bvrs-category-inline-btn--confirm');
        const btnCancel = wrap.querySelector('.bvrs-category-inline-btn--cancel');

        function cancel() {
            wrap.replaceWith(targetPill);
            if (window.lucide) window.lucide.createIcons();
        }

        function confirmCategory() {
            const val = input.value.trim().toUpperCase();
            if (!val) {
                cancel();
                return;
            }

            const newRisk = {
                level: 'standard',
                category_fr: val,
                category_en: val,
                title_fr: '',
                title_en: '',
                description_fr: '',
                description_en: '',
                recommendations_fr: [''],
                recommendations_en: ['']
            };

            const card = renderRiskAccordion(newRisk);
            risksContainer.appendChild(card);
            currentActiveCategory = val;
            refreshTabsAndCounters();

            // Déplier et focaliser immédiatement la nouvelle carte
            card.classList.add('is-expanded');
            const body = card.querySelector('.bvrs-risk-accordion-body');
            if (body) body.classList.remove('u-d-none');
            if (window.lucide) window.lucide.createIcons();

            const inputTitle = card.querySelector('.bvrs-risk-title-fr');
            if (inputTitle) {
                inputTitle.focus();
                card.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

        btnConfirm.addEventListener('click', confirmCategory);
        btnCancel.addEventListener('click', cancel);

        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                confirmCategory();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                cancel();
            }
        });

        input.focus();
    }

    function setActiveCategory(cat) {
        currentActiveCategory = cat;
        refreshTabsAndCounters();
    }

    function filterRisks() {
        const cards = risksContainer.querySelectorAll('.bvrs-risk-accordion');
        let visibleCount = 0;

        cards.forEach(function (card) {
            const cardCat = (card.dataset.category || '').trim().toUpperCase() || 'ZONE DE TOURNAGE';
            const matches = (currentActiveCategory === 'all' || cardCat === currentActiveCategory);

            if (matches) {
                card.classList.remove('u-d-none');
                visibleCount++;
            } else {
                card.classList.add('u-d-none');
            }
        });

        // Mise à jour du sous-titre de contexte et du bouton renommer
        if (activeCatDisplay && renameCatWrap) {
            activeCatDisplay.classList.remove('u-d-none');
            renameCatWrap.classList.add('u-d-none');
        }

        if (activeCatName) {
            activeCatName.textContent = (currentActiveCategory === 'all' ? 'Tous les risques' : currentActiveCategory);
        }
        if (countBadge) {
            countBadge.textContent = `${visibleCount} risque${visibleCount > 1 ? 's' : ''}`;
        }

        if (btnRenameCategory) {
            if (currentActiveCategory === 'all') {
                btnRenameCategory.classList.add('u-d-none');
            } else {
                btnRenameCategory.classList.remove('u-d-none');
            }
        }

        // État vide
        if (emptyState) {
            if (visibleCount === 0) {
                emptyState.classList.remove('u-d-none');
            } else {
                emptyState.classList.add('u-d-none');
            }
        }

        // Mise à jour de l'état du bouton Tout déplier / replier
        updateToggleAllButton();
    }

    function updateToggleAllButton() {
        if (!btnToggleAllCards || !toggleAllLabel) return;
        const visibleCards = risksContainer.querySelectorAll('.bvrs-risk-accordion:not(.u-d-none)');
        if (visibleCards.length === 0) return;

        let hasCollapsed = false;
        visibleCards.forEach(function (card) {
            if (!card.classList.contains('is-expanded')) {
                hasCollapsed = true;
            }
        });

        if (hasCollapsed) {
            toggleAllLabel.textContent = 'Tout déplier';
        } else {
            toggleAllLabel.textContent = 'Tout replier';
        }
    }

    // ── Logique de renommage de catégorie ──
    function openRenameCategory() {
        if (currentActiveCategory === 'all') return;
        if (activeCatDisplay && renameCatWrap && renameCatInput) {
            activeCatDisplay.classList.add('u-d-none');
            renameCatWrap.classList.remove('u-d-none');
            renameCatInput.value = currentActiveCategory;
            if (window.lucide) window.lucide.createIcons();
            renameCatInput.focus();
            renameCatInput.select();
        }
    }

    function cancelRenameCategory() {
        if (activeCatDisplay && renameCatWrap) {
            renameCatWrap.classList.add('u-d-none');
            activeCatDisplay.classList.remove('u-d-none');
        }
    }

    function confirmRenameCategory() {
        if (!renameCatInput) return;
        const oldCat = currentActiveCategory;
        const newCat = renameCatInput.value.trim().toUpperCase();

        if (!newCat || newCat === oldCat) {
            cancelRenameCategory();
            return;
        }

        // Mettre à jour toutes les cartes associées à l'ancienne catégorie
        const cards = risksContainer.querySelectorAll('.bvrs-risk-accordion');
        cards.forEach(function (card) {
            if ((card.dataset.category || '').trim().toUpperCase() === oldCat) {
                card.dataset.category = newCat;
                const tag = card.querySelector('.bvrs-risk-cat-tag');
                if (tag) tag.textContent = newCat;
            }
        });

        // Synchroniser tous les selects de catégories dans les cartes
        synchronizeAllCategorySelects();

        currentActiveCategory = newCat;
        cancelRenameCategory();
        refreshTabsAndCounters();
    }

    function synchronizeAllCategorySelects() {
        const allCats = getCategoriesList();
        document.querySelectorAll('.bvrs-risk-accordion').forEach(function (c) {
            const select = c.querySelector('.bvrs-risk-category-select');
            if (select) {
                const currentVal = c.dataset.category;
                select.innerHTML = '';
                allCats.forEach(function (catName) {
                    const opt = document.createElement('option');
                    opt.value = catName;
                    opt.textContent = catName;
                    if (catName === currentVal) opt.selected = true;
                    select.appendChild(opt);
                });
                const optNew = document.createElement('option');
                optNew.value = '__new__';
                optNew.textContent = '+ Nouvelle catégorie...';
                select.appendChild(optNew);
            }
        });
    }

    if (btnRenameCategory) {
        btnRenameCategory.addEventListener('click', openRenameCategory);
    }
    if (btnConfirmRename) {
        btnConfirmRename.addEventListener('click', confirmRenameCategory);
    }
    if (btnCancelRename) {
        btnCancelRename.addEventListener('click', cancelRenameCategory);
    }
    if (renameCatInput) {
        renameCatInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                confirmRenameCategory();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                cancelRenameCategory();
            }
        });
    }

    // ── Création d'une recommandation individuelle ──
    function createRecElement(recFr, recEn, onRecChange) {
        const wrap = document.createElement('div');
        wrap.className = 'u-flex u-align-center u-gap-2 bvrs-rec-item u-mb-1';
        wrap.innerHTML = `
            <span class="u-text-success u-font-bold">✓</span>
            <input type="text" class="form-input form-input-sm u-flex-1 bvrs-rec-fr" placeholder="Recommandation FR..." value="${escapeHtml(recFr || '')}">
            <input type="text" class="form-input form-input-sm u-flex-1 bvrs-rec-en" placeholder="Recommendation EN (optionnel)..." value="${escapeHtml(recEn || '')}">
            <button type="button" class="admin-btn admin-btn-xs admin-btn-danger btn-del-rec" title="Supprimer la recommandation">
                <i data-lucide="x"></i>
            </button>
        `;
        wrap.querySelector('.btn-del-rec').addEventListener('click', function () {
            wrap.remove();
            if (onRecChange) onRecChange();
        });
        return wrap;
    }

    // ── Création d'une carte accordéon de risque ──
    function renderRiskAccordion(risk) {
        const card = document.createElement('div');
        const level = risk.level || 'standard';
        const isMajor = (level === 'major');
        const category = (risk.category_fr || risk.category || 'ZONE DE TOURNAGE').trim().toUpperCase();
        const titleFr = risk.title_fr || risk.title || '';
        const titleEn = risk.title_en || '';
        const descFr = risk.description_fr || risk.description || '';
        const descEn = risk.description_en || '';
        const recsFr = risk.recommendations_fr || risk.recommendations || [];
        const recsEn = risk.recommendations_en || [];
        const maxRecs = Math.max(recsFr.length, recsEn.length);

        card.className = `admin-card bvrs-risk-accordion ${isMajor ? 'bvrs-risk-accordion--major' : 'bvrs-risk-accordion--standard'}`;
        card.dataset.category = category;

        card.innerHTML = `
            <!-- En-tête synthétique cliquable (Toujours visible) -->
            <div class="bvrs-risk-accordion-header">
                <div class="bvrs-risk-header-left">
                    <button type="button" class="bvrs-level-pill ${isMajor ? 'bvrs-level-pill--major' : 'bvrs-level-pill--standard'}" title="Cliquer pour basculer Majeur / Standard">
                        ${isMajor ? 'MAJEUR' : 'STANDARD'}
                    </button>
                    <span class="bvrs-risk-cat-tag">${escapeHtml(category)}</span>
                    <div class="bvrs-risk-title-preview">
                        <strong class="bvrs-risk-title-fr-text">${escapeHtml(titleFr || 'Nouveau risque sans titre')}</strong>
                        <span class="bvrs-risk-title-en-text ${titleEn ? '' : 'u-d-none'}">${titleEn ? ' / ' + escapeHtml(titleEn) : ''}</span>
                    </div>
                </div>
                <div class="bvrs-risk-header-right">
                    <span class="badge-pill u-bg-neutral-light u-text-muted u-text-2xs bvrs-rec-count-pill">${maxRecs} consigne${maxRecs > 1 ? 's' : ''}</span>
                    <div class="bvrs-risk-header-actions" onclick="event.stopPropagation();">
                        <button type="button" class="bvsr-action-btn btn-move-risk-up" title="Monter dans la catégorie">
                            <i data-lucide="chevron-up"></i>
                        </button>
                        <button type="button" class="bvsr-action-btn btn-move-risk-down" title="Descendre dans la catégorie">
                            <i data-lucide="chevron-down"></i>
                        </button>
                        <button type="button" class="bvsr-action-btn bvsr-action-btn--delete btn-delete-risk" title="Supprimer ce risque">
                            <i data-lucide="trash-2"></i>
                        </button>
                    </div>
                    <button type="button" class="bvrs-accordion-chevron" aria-label="Déplier / Replier">
                        <i data-lucide="chevron-down"></i>
                    </button>
                </div>
            </div>

            <!-- Corps détaillé d'édition (Dépliable) -->
            <div class="bvrs-risk-accordion-body u-d-none">
                <!-- Ligne de configuration : Sévérité & Catégorie -->
                <div class="u-flex u-align-center u-justify-between u-gap-3 u-mb-3 u-flex-wrap">
                    <div class="u-flex u-align-center u-gap-2">
                        <label class="form-label u-text-xs u-font-bold u-m-0">Niveau de risque :</label>
                        <div class="bvrs-level-toggle">
                            <button type="button" class="bvrs-level-btn bvrs-level-btn--major ${isMajor ? 'is-active' : ''}" data-level="major">
                                MAJEUR
                            </button>
                            <button type="button" class="bvrs-level-btn bvrs-level-btn--standard ${!isMajor ? 'is-active' : ''}" data-level="standard">
                                STANDARD
                            </button>
                        </div>
                        <input type="hidden" class="bvrs-risk-level-input" value="${level}">
                    </div>

                    <div class="u-flex u-align-center u-gap-2 u-flex-1 u-justify-end">
                        <label class="form-label u-text-xs u-font-bold u-m-0">Catégorie :</label>
                        <select class="form-input form-input-sm bvrs-risk-category-select u-w-auto">
                            <!-- Rempli dynamiquement -->
                        </select>
                        <input type="text" class="form-input form-input-sm bvrs-risk-category-custom u-w-180 u-d-none" placeholder="Nom de la nouvelle catégorie...">
                    </div>
                </div>

                <!-- Grille bilingue Titres -->
                <div class="u-grid u-gap-2 u-grid-cols-2 u-mb-3">
                    <div>
                        <label class="form-label u-text-xs u-font-bold u-mb-1">Titre du Risque (FR) <span class="u-text-danger">*</span></label>
                        <input type="text" class="form-input form-input-sm bvrs-risk-title-fr" placeholder="ex: Intrusion dans la zone de roulage" value="${escapeHtml(titleFr)}" required>
                    </div>
                    <div>
                        <label class="form-label u-text-xs u-font-bold u-mb-1">Titre du Risque (EN)</label>
                        <input type="text" class="form-input form-input-sm bvrs-risk-title-en" placeholder="ex: Intrusion into the Driving Area" value="${escapeHtml(titleEn)}">
                    </div>
                </div>

                <!-- Grille bilingue Descriptions -->
                <div class="u-grid u-gap-2 u-grid-cols-2 u-mb-3">
                    <div>
                        <label class="form-label u-text-xs u-font-bold u-mb-1">Description détaillée du danger (FR)</label>
                        <textarea class="form-input form-input-sm bvrs-risk-desc-fr u-h-60" placeholder="Explication du risque et scénarios potentiels...">${escapeHtml(descFr)}</textarea>
                    </div>
                    <div>
                        <label class="form-label u-text-xs u-font-bold u-mb-1">Description détaillée du danger (EN)</label>
                        <textarea class="form-input form-input-sm bvrs-risk-desc-en u-h-60" placeholder="Detailed description in English...">${escapeHtml(descEn)}</textarea>
                    </div>
                </div>

                <!-- Recommandations & Mesures de prévention -->
                <div class="u-border-top u-pt-2">
                    <div class="u-flex u-justify-between u-align-center u-mb-2">
                        <span class="u-text-2xs u-uppercase u-font-bold u-text-muted">Recommandations</span>
                        <button type="button" class="admin-btn admin-btn-xs admin-btn-secondary btn-add-rec">
                            <i data-lucide="plus"></i> Ajouter une recommandation
                        </button>
                    </div>
                    <div class="bvrs-recs-container u-flex u-flex-column u-gap-1"></div>
                </div>
            </div>
        `;

        const header = card.querySelector('.bvrs-risk-accordion-header');
        const body = card.querySelector('.bvrs-risk-accordion-body');
        const titleFrInput = card.querySelector('.bvrs-risk-title-fr');
        const titleEnInput = card.querySelector('.bvrs-risk-title-en');
        const titleFrPreview = card.querySelector('.bvrs-risk-title-fr-text');
        const titleEnPreview = card.querySelector('.bvrs-risk-title-en-text');
        const levelPill = card.querySelector('.bvrs-level-pill');
        const levelHiddenInput = card.querySelector('.bvrs-risk-level-input');
        const levelButtons = card.querySelectorAll('.bvrs-level-btn');
        const catTag = card.querySelector('.bvrs-risk-cat-tag');
        const catSelect = card.querySelector('.bvrs-risk-category-select');
        const catCustomInput = card.querySelector('.bvrs-risk-category-custom');
        const recCountPill = card.querySelector('.bvrs-rec-count-pill');
        const recsContainer = card.querySelector('.bvrs-recs-container');
        const btnAddRec = card.querySelector('.btn-add-rec');

        // 1. Dépliage / Repliage accordéon
        function toggleExpand() {
            const isExpanded = card.classList.contains('is-expanded');
            if (isExpanded) {
                card.classList.remove('is-expanded');
                body.classList.add('u-d-none');
            } else {
                card.classList.add('is-expanded');
                body.classList.remove('u-d-none');
                if (window.lucide) window.lucide.createIcons();
            }
            updateToggleAllButton();
        }

        header.addEventListener('click', function (e) {
            // Ignorer si clic dans actions ou sur le badge de niveau direct
            if (e.target.closest('.bvrs-risk-header-actions') || e.target.closest('.bvrs-level-pill')) {
                return;
            }
            toggleExpand();
        });

        // 2. Mise à jour synchrone du titre en temps réel
        titleFrInput.addEventListener('input', function () {
            const val = this.value.trim();
            titleFrPreview.textContent = val || 'Nouveau risque sans titre';
        });

        titleEnInput.addEventListener('input', function () {
            const val = this.value.trim();
            if (val) {
                titleEnPreview.textContent = ' / ' + val;
                titleEnPreview.classList.remove('u-d-none');
            } else {
                titleEnPreview.textContent = '';
                titleEnPreview.classList.add('u-d-none');
            }
        });

        // 3. Bascule du niveau (Majeur / Standard)
        function setLevel(newLevel) {
            levelHiddenInput.value = newLevel;
            const isNowMajor = (newLevel === 'major');

            if (isNowMajor) {
                card.classList.remove('bvrs-risk-accordion--standard');
                card.classList.add('bvrs-risk-accordion--major');
                levelPill.className = 'bvrs-level-pill bvrs-level-pill--major';
                levelPill.textContent = 'MAJEUR';
            } else {
                card.classList.remove('bvrs-risk-accordion--major');
                card.classList.add('bvrs-risk-accordion--standard');
                levelPill.className = 'bvrs-level-pill bvrs-level-pill--standard';
                levelPill.textContent = 'STANDARD';
            }

            levelButtons.forEach(function (btn) {
                if (btn.dataset.level === newLevel) {
                    btn.classList.add('is-active');
                } else {
                    btn.classList.remove('is-active');
                }
            });

            refreshTabsAndCounters();
        }

        // Clic sur badge pill rapide dans l'en-tête
        levelPill.addEventListener('click', function (e) {
            e.stopPropagation();
            const current = levelHiddenInput.value;
            setLevel(current === 'major' ? 'standard' : 'major');
        });

        // Clic sur boutons segmentés dans le corps
        levelButtons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                setLevel(this.dataset.level);
            });
        });

        // 4. Catégorie & Sélecteur dynamique
        function updateCategoryOptions() {
            const allCats = getCategoriesList();
            const currentCat = card.dataset.category || 'ZONE DE TOURNAGE';

            catSelect.innerHTML = '';
            allCats.forEach(function (c) {
                const opt = document.createElement('option');
                opt.value = c;
                opt.textContent = c;
                if (c === currentCat) opt.selected = true;
                catSelect.appendChild(opt);
            });

            const newOpt = document.createElement('option');
            newOpt.value = '__new__';
            newOpt.textContent = '+ Nouvelle catégorie...';
            catSelect.appendChild(newOpt);
        }

        updateCategoryOptions();

        catSelect.addEventListener('change', function () {
            if (this.value === '__new__') {
                catCustomInput.classList.remove('u-d-none');
                catCustomInput.value = '';
                catCustomInput.focus();
            } else {
                catCustomInput.classList.add('u-d-none');
                applyCategory(this.value);
            }
        });

        catCustomInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const val = this.value.trim().toUpperCase();
                if (val) {
                    applyCategory(val);
                    catCustomInput.classList.add('u-d-none');
                }
            }
        });

        catCustomInput.addEventListener('blur', function () {
            const val = this.value.trim().toUpperCase();
            if (val) {
                applyCategory(val);
                catCustomInput.classList.add('u-d-none');
            } else {
                catCustomInput.classList.add('u-d-none');
                catSelect.value = card.dataset.category;
            }
        });

        function applyCategory(newCat) {
            newCat = newCat.trim().toUpperCase() || 'ZONE DE TOURNAGE';
            card.dataset.category = newCat;
            catTag.textContent = newCat;
            refreshTabsAndCounters();
            synchronizeAllCategorySelects();
        }

        // 5. Recommandations
        function updateRecCounter() {
            const count = recsContainer.querySelectorAll('.bvrs-rec-item').length;
            recCountPill.textContent = `${count} consigne${count > 1 ? 's' : ''}`;
        }

        if (maxRecs > 0) {
            for (let i = 0; i < maxRecs; i++) {
                recsContainer.appendChild(createRecElement(recsFr[i] || '', recsEn[i] || '', updateRecCounter));
            }
        }

        btnAddRec.addEventListener('click', function () {
            const el = createRecElement('', '', updateRecCounter);
            recsContainer.appendChild(el);
            updateRecCounter();
            if (window.lucide) window.lucide.createIcons();
            const input = el.querySelector('.bvrs-rec-fr');
            if (input) input.focus();
        });

        // 6. Monter / Descendre / Supprimer
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

        card.querySelector('.btn-delete-risk').addEventListener('click', function () {
            if (confirm('Voulez-vous supprimer ce risque du protocole ?')) {
                card.remove();
                refreshTabsAndCounters();
            }
        });

        return card;
    }

    // ── Remplissage initial de la liste ──
    function populateRisks(risksList) {
        risksContainer.innerHTML = '';
        currentActiveCategory = 'all';

        if (Array.isArray(risksList) && risksList.length > 0) {
            risksList.forEach(function (r) {
                risksContainer.appendChild(renderRiskAccordion(r));
            });
        }

        refreshTabsAndCounters();
        if (window.lucide) window.lucide.createIcons();
    }

    // ── Ouverture modale pour Risques Généraux ──
    function handleEditGeneral(btn) {
        inputAction.value = 'save_general';
        inputVehicleKey.value = '';
        wrapVehicleLabel.classList.add('u-d-none');
        if (inputLabel) inputLabel.removeAttribute('required');

        modalTitle.textContent = 'Modifier les Risques Généraux : Véhicules Travelling';
        modalSubtitle.textContent = 'Consignes transversales applicables à tous les tournages travelling Belle Vitesse';
        modalIconWrap.className = 'badge-pill u-bg-danger-light u-text-danger';
        modalIconWrap.innerHTML = '<i data-lucide="shield-alert" class="u-w-24 u-h-24 u-m-0"></i>';

        let risksData = [];
        const scriptTag = document.getElementById('bvrs-general-risks-json');
        if (scriptTag && scriptTag.textContent) {
            try {
                risksData = JSON.parse(scriptTag.textContent);
            } catch (e) {
                console.error('Erreur parsing bvrs-general-risks-json :', e);
            }
        }
        if (!risksData || risksData.length === 0) {
            try {
                risksData = JSON.parse(btn.dataset.risks || '[]');
            } catch (err) {
                console.error('Erreur parsing risks dataset :', err);
            }
        }
        populateRisks(risksData);
        openModal();
    }

    // ── Ouverture modale pour Risques Spécifiques Véhicule ──
    function handleEditVehicle(btn) {
        const vKey = btn.dataset.key || '';
        const vId = btn.dataset.id || vKey;
        let catData = null;

        const scriptTag = document.getElementById('bvrs-vehicle-catalog-json');
        if (scriptTag && scriptTag.textContent) {
            try {
                const fullCatalog = JSON.parse(scriptTag.textContent);
                catData = fullCatalog[vKey] || fullCatalog[vId];
            } catch (e) {
                console.error('Erreur parsing bvrs-vehicle-catalog-json :', e);
            }
        }

        if (!catData) {
            try {
                catData = JSON.parse(btn.dataset.cat || '{}');
            } catch (err) {
                console.error('Erreur parsing cat dataset :', err);
                catData = {};
            }
        }

        inputAction.value = 'save_vehicle';
        inputVehicleKey.value = vKey;
        wrapVehicleLabel.classList.remove('u-d-none');
        if (inputLabel) {
            inputLabel.setAttribute('required', 'required');
            inputLabel.value = catData.label || catData.name || vKey;
        }

        modalTitle.textContent = 'Modifier les Risques Spécifiques';
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
    }

    // ── Délégation d'événements pour les boutons d'ouverture (100% fiable) ──
    document.addEventListener('click', function (e) {
        const btnVeh = e.target.closest('.btn-edit-vehicle-risks');
        if (btnVeh) {
            e.preventDefault();
            handleEditVehicle(btnVeh);
            return;
        }

        const btnGen = e.target.closest('.btn-edit-general-risks');
        if (btnGen) {
            e.preventDefault();
            handleEditGeneral(btnGen);
            return;
        }
    });

    // ── Bouton Tout Déplier / Tout Replier ──
    if (btnToggleAllCards) {
        btnToggleAllCards.addEventListener('click', function () {
            const visibleCards = risksContainer.querySelectorAll('.bvrs-risk-accordion:not(.u-d-none)');
            if (visibleCards.length === 0) return;

            let hasCollapsed = false;
            visibleCards.forEach(function (card) {
                if (!card.classList.contains('is-expanded')) {
                    hasCollapsed = true;
                }
            });

            visibleCards.forEach(function (card) {
                const body = card.querySelector('.bvrs-risk-accordion-body');
                if (hasCollapsed) {
                    card.classList.add('is-expanded');
                    if (body) body.classList.remove('u-d-none');
                } else {
                    card.classList.remove('is-expanded');
                    if (body) body.classList.add('u-d-none');
                }
            });

            if (window.lucide) window.lucide.createIcons();
            updateToggleAllButton();
        });
    }


    // ── Bouton Ajouter un Risque ──
    if (btnAddRisk) {
        btnAddRisk.addEventListener('click', function () {
            const defaultCat = (currentActiveCategory === 'all')
                ? (getCategoriesList()[0] || 'ZONE DE TOURNAGE')
                : currentActiveCategory;

            const newRisk = {
                level: 'standard',
                category_fr: defaultCat,
                category_en: defaultCat,
                title_fr: '',
                title_en: '',
                description_fr: '',
                description_en: '',
                recommendations_fr: [''],
                recommendations_en: ['']
            };

            const card = renderRiskAccordion(newRisk);
            risksContainer.appendChild(card);
            refreshTabsAndCounters();

            // Déplier et focaliser
            card.classList.add('is-expanded');
            const body = card.querySelector('.bvrs-risk-accordion-body');
            if (body) body.classList.remove('u-d-none');
            if (window.lucide) window.lucide.createIcons();

            const inputTitle = card.querySelector('.bvrs-risk-title-fr');
            if (inputTitle) {
                inputTitle.focus();
                card.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    }

    // ── Soumission Formulaire & Sérialisation JSON ──
    form.addEventListener('submit', function (e) {
        const cards = risksContainer.querySelectorAll('.bvrs-risk-accordion');
        const serialized = [];

        for (let i = 0; i < cards.length; i++) {
            const card = cards[i];
            const level = card.querySelector('.bvrs-risk-level-input').value || 'standard';
            const catFr = (card.dataset.category || 'ZONE DE TOURNAGE').trim().toUpperCase();
            const titleFr = card.querySelector('.bvrs-risk-title-fr').value.trim();
            const titleEn = card.querySelector('.bvrs-risk-title-en').value.trim();
            const descFr = card.querySelector('.bvrs-risk-desc-fr').value.trim();
            const descEn = card.querySelector('.bvrs-risk-desc-en').value.trim();

            if (!titleFr) {
                e.preventDefault();
                alert(`Veuillez renseigner un titre en français pour le risque n° ${i + 1}.`);
                // Basculer sur la catégorie du risque erroné et déplier la carte
                setActiveCategory(catFr);
                card.classList.add('is-expanded');
                const body = card.querySelector('.bvrs-risk-accordion-body');
                if (body) body.classList.remove('u-d-none');
                card.querySelector('.bvrs-risk-title-fr').focus();
                card.scrollIntoView({ behavior: 'smooth', block: 'center' });
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
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRiskAssessmentCatalog);
} else {
    initRiskAssessmentCatalog();
}
