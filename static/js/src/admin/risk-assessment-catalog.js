/**
 * risk-assessment-catalog.js — Contrôleur d'interface d'administration pour l'Analyse des Risques (BVRS).
 *
 * 1. Vue d'ensemble du Catalogue (/admin/fleet/risk-assessment) :
 *    - Recherche textuelle instantanée (titres, catégories, descriptions, consignes)
 *    - Filtres par pilules (Tous, Majeurs, EN incomplet)
 *    - Accordéons par catégories, bouton global « Tout déplier »
 *    - Dépliage des risques spécifiques par véhicule
 *
 * 2. Écran d'édition Master-Detail (/admin/fleet/risk-assessment/edit/...) :
 *    - Sidebar : liste réordonnable (glisser-déposer au sein d'une catégorie), filtres et recherche
 *    - Onglet Édition : niveau, catégorie (création inline), champs bilingues, recommandations
 *    - Onglet Aperçu PDF : même balisage et même feuille de style que le PDF WeasyPrint
 *    - Barre inférieure : état modifié, Annuler / Enregistrer (AJAX)
 *    - Modale anti-perte de données avant tout changement de risque
 *
 * Les modifications ne touchent la liste en mémoire (risksList) qu'après un enregistrement
 * réussi : Annuler / Ignorer restaurent toujours l'état serveur.
 */

(function () {
    'use strict';

    const MISSING_SENTINELS = ['traduction manquante', 'traduction anglaise manquante'];

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /** Une valeur EN est manquante si vide ou égale à un ancien texte de remplissage. */
    function isMissingTranslation(value) {
        const v = (value || '').trim();
        return !v || MISSING_SENTINELS.includes(v.toLowerCase());
    }

    /** Nettoie une valeur EN héritée (ancien texte de remplissage → chaîne vide). */
    function cleanEn(value) {
        return isMissingTranslation(value) ? '' : String(value).trim();
    }

    /** Miroir de services.admin.risk_assessment_config.check_risk_translation_status. */
    function computeTranslationStatus(risk) {
        let missing = 0;
        if (isMissingTranslation(risk.title_en)) missing++;
        if (isMissingTranslation(risk.description_en)) missing++;
        const recsFr = risk.recommendations_fr || risk.recommendations || [];
        const recsEn = risk.recommendations_en || [];
        recsFr.forEach(function (_, idx) {
            if (isMissingTranslation(recsEn[idx])) missing++;
        });
        return { is_complete: missing === 0, missing_count: missing };
    }

    function refreshIcons() {
        if (window.lucide) window.lucide.createIcons();
    }

    /** Pilules de filtre ERP : actif = admin-btn-primary, inactif = admin-btn-quaternary. */
    function setActivePill(pills, activeBtn) {
        pills.forEach(function (b) {
            const on = b === activeBtn;
            b.classList.toggle('active', on);
            b.classList.toggle('admin-btn-primary', on);
            b.classList.toggle('admin-btn-quaternary', !on);
            b.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
    }

    /** Badge de niveau (.badge-pill) : MAJEUR = danger, STANDARD = warning. */
    function levelBadgeHtml(level) {
        return level === 'major'
            ? '<span class="badge-pill badge-pill-xs" data-val="danger">Majeur</span>'
            : '<span class="badge-pill badge-pill-xs" data-val="warning">Standard</span>';
    }

    function flash(message, category) {
        if (typeof window.showFlash === 'function') {
            window.showFlash(message, category || 'info');
        } else if (category === 'error') {
            window.alert(message);
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // 1. VUE D'ENSEMBLE DU CATALOGUE
    // ══════════════════════════════════════════════════════════════════════════
    function initCatalogOverview() {
        const page = document.querySelector('.bvrs-page');
        if (!page) return;

        // Champ de recherche standard de l'ERP (macro list_header_actions → #searchInput)
        const searchInput = document.getElementById('searchInput');
        const searchForm = searchInput ? searchInput.closest('form') : null;
        const btnToggleAll = document.getElementById('btn-toggle-all-accordions');
        const riskRows = page.querySelectorAll('.bvrs-row');
        const groupWrappers = page.querySelectorAll('.bvrs-group-wrapper');
        const groupButtons = page.querySelectorAll('.bvrs-group');
        const vehicleCards = page.querySelectorAll('.bvrs-vehicle-card');
        const moreButtons = page.querySelectorAll('.bvrs-more');

        function setGroupExpanded(btn, expanded) {
            btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            const wrapper = btn.closest('.bvrs-group-wrapper');
            const content = wrapper ? wrapper.querySelector('.bvrs-group__content') : null;
            if (content) content.classList.toggle('u-d-none', !expanded);
        }

        /**
         * Bandeau « Voir les X risques » (data-action="vehicle") ou
         * « Afficher les X autres risques » (data-action="extra").
         */
        function setMoreExpanded(btn, expanded) {
            const card = btn.closest('.bvrs-vehicle-card');
            if (card) {
                const targets = btn.dataset.action === 'extra'
                    ? card.querySelectorAll('.bvrs-extra-cat')
                    : card.querySelectorAll('.bvrs-vehicle-collapsible-content');
                targets.forEach(function (el) { el.classList.toggle('u-d-none', !expanded); });
            }
            btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            btn.textContent = expanded ? btn.dataset.labelHide : btn.dataset.labelShow;
        }

        // Le filtrage utilise une classe dédiée (bvrs-filtered-out) pour ne jamais
        // interférer avec l'état replié/déplié (u-d-none) des groupes et véhicules.
        function applySearch() {
            const q = (searchInput ? searchInput.value : '').trim().toLowerCase();

            riskRows.forEach(function (row) {
                row.classList.toggle('bvrs-filtered-out', !!q && !(row.dataset.searchText || '').includes(q));
            });

            groupWrappers.forEach(function (wrapper) {
                const hasVisible = !!wrapper.querySelector('.bvrs-row:not(.bvrs-filtered-out)');
                wrapper.classList.toggle('bvrs-filtered-out', !hasVisible);
                // Recherche active : déplier les groupes contenant des résultats
                if (q && hasVisible) {
                    const btn = wrapper.querySelector('.bvrs-group');
                    if (btn) setGroupExpanded(btn, true);
                }
            });

            vehicleCards.forEach(function (card) {
                const hasVisible = !!card.querySelector('.bvrs-row:not(.bvrs-filtered-out)');
                const vName = (card.querySelector('.bvrs-vehicle__name')?.textContent || '').toLowerCase();
                card.classList.toggle('bvrs-filtered-out', !!q && !hasVisible && !vName.includes(q));

                if (q && hasVisible) {
                    card.querySelectorAll('.bvrs-more').forEach(function (btn) { setMoreExpanded(btn, true); });
                }
            });
        }

        if (searchInput) {
            // Filtrage instantané côté client : pas de rechargement à la validation
            if (searchForm) searchForm.addEventListener('submit', function (e) { e.preventDefault(); });
            searchInput.addEventListener('input', applySearch);
            if (searchInput.value) applySearch();  // ?q= pré-rempli par la macro
        }

        groupButtons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                setGroupExpanded(this, this.getAttribute('aria-expanded') !== 'true');
            });
        });

        moreButtons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                setMoreExpanded(this, this.getAttribute('aria-expanded') !== 'true');
            });
        });

        if (btnToggleAll) {
            const label = btnToggleAll.querySelector('.js-toggle-all-label');
            btnToggleAll.addEventListener('click', function () {
                const expand = btnToggleAll.getAttribute('aria-expanded') !== 'true';
                groupButtons.forEach(function (btn) { setGroupExpanded(btn, expand); });
                moreButtons.forEach(function (btn) { setMoreExpanded(btn, expand); });
                btnToggleAll.setAttribute('aria-expanded', expand ? 'true' : 'false');
                if (label) label.textContent = expand ? 'Tout replier' : 'Tout déplier';

                // Lucide remplace <i> par <svg> : on réinjecte l'icône voulue
                const icon = btnToggleAll.querySelector('[data-lucide], svg.lucide');
                if (icon) {
                    const next = document.createElement('i');
                    next.className = 'admin-header__icon';
                    next.setAttribute('data-lucide', expand ? 'chevrons-down-up' : 'chevrons-up-down');
                    icon.replaceWith(next);
                    refreshIcons();
                }
            });
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // 2. ÉDITEUR MASTER-DETAIL (GÉNÉRAL & VÉHICULE)
    // ══════════════════════════════════════════════════════════════════════════
    function initMasterDetailEditor() {
        const page = document.querySelector('.bvrs-edit-page');
        if (!page) return;

        function readJson(id, fallback) {
            const el = document.getElementById(id);
            if (!el) return fallback;
            try { return JSON.parse(el.textContent || ''); } catch (e) { return fallback; }
        }

        const scope = readJson('bvrs-scope-data', 'general');
        const vehicleKey = readJson('bvrs-vehicle-key-data', '');
        const csrfToken = readJson('bvrs-csrf-token', '');
        const urls = {
            save: page.dataset.urlSave,
            del: page.dataset.urlDelete,
            reorder: page.dataset.urlReorder
        };

        // Liste « serveur » : ne change qu'après un enregistrement / suppression réussi.
        let risksList = readJson('bvrs-risks-data', []).map(normalizeRisk);
        // Catégories communes (risques généraux + tous les véhicules) : [{fr, en}]
        const sharedCategories = readJson('bvrs-categories-data', [])
            .filter(function (c) { return c && c.fr; })
            .map(function (c) { return { fr: String(c.fr).trim().toUpperCase(), en: String(c.en || '').trim() }; });

        const $ = function (id) { return document.getElementById(id); };

        // Sidebar
        const sidebarList = $('sidebar-risks-list');
        const sidebarCount = $('sidebar-risks-count');
        const sidebarSearchInput = $('sidebar-search-input');
        const sidebarFilterBtns = page.querySelectorAll('.bvrs-filter-pills .filter-pill');
        const btnAddRisk = $('btn-add-risk');

        // En-tête & onglets
        const detailTitle = $('detail-risk-title');
        const detailLevelBadge = $('detail-risk-level-badge');
        const detailTransBadge = $('detail-risk-trans-badge');
        const tabBtnEdit = $('tab-btn-edit');
        const tabBtnPdf = $('tab-btn-pdf');
        const tabPaneEdit = $('tab-pane-edit');
        const tabPanePdf = $('tab-pane-pdf');

        // Formulaire
        const form = $('form-edit-risk');
        const btnLevelMajor = $('btn-level-major');
        const btnLevelStandard = $('btn-level-standard');
        const fieldCategorySelect = $('field-category-select');
        const wrapNewCat = $('wrap-new-cat');
        const inputNewCat = $('input-new-cat');
        const inputNewCatEn = $('input-new-cat-en');
        const btnConfirmNewCat = $('btn-confirm-new-cat');
        const btnCancelNewCat = $('btn-cancel-new-cat');
        const fieldTitleFr = $('field-title-fr');
        const fieldTitleEn = $('field-title-en');
        const fieldDescFr = $('field-desc-fr');
        const fieldDescEn = $('field-desc-en');
        const badgeTitleEnStatus = $('badge-title-en-status');
        const badgeDescEnStatus = $('badge-desc-en-status');
        const recsCountElem = $('recs-count');
        const btnAddRec = $('btn-add-rec');
        const recsList = $('recs-list');
        const btnDeleteRisk = $('btn-delete-risk');

        // Aperçu PDF
        const btnLangFr = $('btn-lang-fr');
        const btnLangEn = $('btn-lang-en');
        const pdfPreviewSheet = $('pdf-preview-sheet');

        // Barre inférieure & modale
        const bottomBar = $('bvrs-bottom-bar');
        const btnCancelRisk = $('btn-cancel-risk');
        const btnSaveRisk = $('btn-save-risk');
        const btnSaveRiskLabel = $('btn-save-risk-label');
        const unsavedModal = $('bvrs-unsaved-modal');
        const btnModalDiscard = $('btn-modal-discard');
        const btnModalSave = $('btn-modal-save');

        // État
        let activeRiskId = null;
        let draftNewRisk = null;      // risque créé via « Ajouter », pas encore enregistré
        let isDirty = false;
        let isSaving = false;
        let pendingAction = null;     // action différée par la modale anti-perte
        let activeFilter = 'all';
        let sidebarSearchQuery = '';
        let currentTab = 'edit';
        let previewLang = 'fr';
        let currentLevel = 'standard';

        function normalizeRisk(r) {
            const recsFr = (r.recommendations_fr || r.recommendations || []).slice();
            const recsEn = (r.recommendations_en || []).slice();
            return Object.assign({}, r, {
                id: String(r.id),
                level: r.level === 'major' ? 'major' : 'standard',
                title_fr: r.title_fr || r.title || '',
                title_en: cleanEn(r.title_en),
                description_fr: r.description_fr || r.description || '',
                description_en: cleanEn(r.description_en),
                category_fr: (r.category_fr || r.category || '').trim(),
                category_en: (r.category_en || '').trim(),
                recommendations_fr: recsFr,
                recommendations_en: recsFr.map(function (_, i) { return cleanEn(recsEn[i]); })
            });
        }

        function allRisks() {
            return draftNewRisk ? [draftNewRisk].concat(risksList) : risksList;
        }

        function findRisk(id) {
            return allRisks().find(function (r) { return r.id === String(id); }) || null;
        }

        function catKey(r) {
            return (r.category_fr || 'GÉNÉRAL').trim().toUpperCase();
        }

        // ── Requêtes JSON ──
        function postJson(url, payload) {
            return fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify(Object.assign({ scope: scope, vehicle_key: vehicleKey }, payload))
            }).then(function (res) {
                return res.json().catch(function () { return {}; }).then(function (data) {
                    if (!res.ok || data.status !== 'success') {
                        throw new Error(data.message || ('Erreur HTTP ' + res.status));
                    }
                    return data;
                });
            });
        }

        // ── Sidebar ──
        function renderSidebar() {
            if (!sidebarList) return;
            sidebarList.innerHTML = '';
            const q = sidebarSearchQuery.trim().toLowerCase();

            const groups = new Map();
            allRisks().forEach(function (r) {
                const key = catKey(r);
                if (!groups.has(key)) groups.set(key, []);
                groups.get(key).push(r);
            });

            let visibleTotal = 0;
            groups.forEach(function (risks, name) {
                const visible = risks.filter(function (r) {
                    if (activeFilter === 'major' && r.level !== 'major') return false;
                    if (activeFilter === 'en-incomplete' && computeTranslationStatus(r).is_complete) return false;
                    if (q) {
                        const hay = (r.title_fr + ' ' + r.title_en + ' ' + name).toLowerCase();
                        if (!hay.includes(q)) return false;
                    }
                    return true;
                });
                if (!visible.length) return;
                visibleTotal += visible.length;

                const groupEl = document.createElement('div');
                groupEl.className = 'bvrs-side-grp';
                groupEl.innerHTML = '<span>' + escapeHtml(name) + '</span><span>' + visible.length + '</span>';
                sidebarList.appendChild(groupEl);

                visible.forEach(function (risk) {
                    sidebarList.appendChild(buildSidebarItem(risk));
                });
            });

            if (!visibleTotal) {
                const empty = document.createElement('div');
                empty.className = 'empty-state';
                empty.innerHTML = '<div class="empty-state-desc">' +
                    (allRisks().length ? 'Aucun risque ne correspond.' : 'Aucun risque configuré.') + '</div>';
                sidebarList.appendChild(empty);
            }

            if (sidebarCount) sidebarCount.textContent = risksList.length;
            // Reflète le brouillon en cours sur l'élément actif
            if (isDirty) updateActiveSidebarItem(collectCurrentFormData());
        }

        function buildSidebarItem(risk) {
            const isMajor = risk.level === 'major';
            const status = computeTranslationStatus(risk);
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'bvrs-side-it' + (isMajor ? ' bvrs-side-it--major' : '') + (risk.id === activeRiskId ? ' is-selected' : '');
            item.dataset.riskId = risk.id;
            item.dataset.category = catKey(risk);
            item.draggable = !(draftNewRisk && risk.id === draftNewRisk.id);
            item.innerHTML =
                '<span class="bvrs-hd" title="Glisser pour réorganiser" aria-hidden="true"></span>' +
                '<span class="bvrs-side-it__title">' + escapeHtml(risk.title_fr || 'Sans titre') + '</span>' +
                (status.is_complete ? '' : '<span class="badge-pill badge-pill-xs bvrs-en-tag" data-val="neutral" title="Traduction EN incomplète">EN</span>') +
                levelBadgeHtml(risk.level).replace('class="badge-pill badge-pill-xs"', 'class="badge-pill badge-pill-xs bvrs-level-tag"');
            if (risk.id === activeRiskId) item.setAttribute('aria-current', 'true');

            item.addEventListener('click', function () {
                if (risk.id === activeRiskId) return;
                guard(function () { selectRisk(risk.id); });
            });
            attachRiskDragAndDrop(item);
            return item;
        }

        function updateActiveSidebarItem(data) {
            if (!sidebarList) return;
            const item = sidebarList.querySelector('.bvrs-side-it[data-risk-id="' + CSS.escape(String(activeRiskId)) + '"]');
            if (!item) return;
            const isMajor = data.level === 'major';
            item.classList.toggle('bvrs-side-it--major', isMajor);
            const titleEl = item.querySelector('.bvrs-side-it__title');
            if (titleEl) titleEl.textContent = data.title_fr || 'Sans titre';
            const badge = item.querySelector('.bvrs-level-tag');
            if (badge) {
                badge.textContent = isMajor ? 'Majeur' : 'Standard';
                badge.dataset.val = isMajor ? 'danger' : 'warning';
            }
            const complete = computeTranslationStatus(data).is_complete;
            let enTag = item.querySelector('.bvrs-en-tag');
            if (!complete && !enTag) {
                enTag = document.createElement('span');
                enTag.className = 'badge-pill badge-pill-xs bvrs-en-tag';
                enTag.dataset.val = 'neutral';
                enTag.title = 'Traduction EN incomplète';
                enTag.textContent = 'EN';
                item.insertBefore(enTag, badge);
            } else if (complete && enTag) {
                enTag.remove();
            }
        }

        // ── Glisser-déposer des risques (au sein d'une même catégorie) ──
        let draggedRiskId = null;
        function attachRiskDragAndDrop(el) {
            el.addEventListener('dragstart', function (e) {
                draggedRiskId = el.dataset.riskId;
                e.dataTransfer.effectAllowed = 'move';
                el.classList.add('is-dragging');
            });
            el.addEventListener('dragend', function () {
                draggedRiskId = null;
                el.classList.remove('is-dragging');
                sidebarList.querySelectorAll('.bvrs-drag-over').forEach(function (i) { i.classList.remove('bvrs-drag-over'); });
            });
            el.addEventListener('dragover', function (e) {
                const dragged = draggedRiskId ? findRisk(draggedRiskId) : null;
                if (!dragged || catKey(dragged) !== el.dataset.category) return;
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                el.classList.add('bvrs-drag-over');
            });
            el.addEventListener('dragleave', function () {
                el.classList.remove('bvrs-drag-over');
            });
            el.addEventListener('drop', function (e) {
                e.preventDefault();
                el.classList.remove('bvrs-drag-over');
                const targetId = el.dataset.riskId;
                if (!draggedRiskId || draggedRiskId === targetId) return;
                const fromIdx = risksList.findIndex(function (r) { return r.id === draggedRiskId; });
                const toIdx = risksList.findIndex(function (r) { return r.id === targetId; });
                if (fromIdx < 0 || toIdx < 0) return;

                const previousOrder = risksList.slice();
                const moved = risksList.splice(fromIdx, 1)[0];
                risksList.splice(toIdx, 0, moved);
                renderSidebar();

                postJson(urls.reorder, { risk_ids: risksList.map(function (r) { return r.id; }) })
                    .catch(function (err) {
                        risksList = previousOrder;
                        renderSidebar();
                        flash("Impossible d'enregistrer le nouvel ordre : " + err.message, 'error');
                    });
            });
        }

        // ── Garde anti-perte : exécute l'action ou ouvre la modale ──
        function guard(action) {
            if (!isDirty) {
                action();
                return;
            }
            pendingAction = action;
            openModal();
        }

        function openModal() {
            if (!unsavedModal) return;
            unsavedModal.classList.add('is-active');
            unsavedModal.setAttribute('aria-hidden', 'false');
            if (btnModalSave) btnModalSave.focus();
        }

        function closeModal() {
            if (!unsavedModal) return;
            unsavedModal.classList.remove('is-active');
            unsavedModal.setAttribute('aria-hidden', 'true');
        }

        /** Abandonne le brouillon : restaure l'état serveur du risque actif. */
        function discardChanges() {
            isDirty = false;
            updateBottomBar();
            if (draftNewRisk && draftNewRisk.id === activeRiskId) {
                draftNewRisk = null;
                activeRiskId = risksList.length ? risksList[0].id : null;
            }
            if (activeRiskId) {
                selectRisk(activeRiskId);
            } else {
                showEmptyState();
            }
        }

        function selectRisk(riskId) {
            const risk = findRisk(riskId);
            if (!risk) return;
            // Quitter un brouillon de création non enregistré le supprime
            if (draftNewRisk && draftNewRisk.id !== risk.id) draftNewRisk = null;

            activeRiskId = risk.id;
            isDirty = false;
            updateBottomBar();
            populateForm(risk);
            renderSidebar();
            setFormDisabled(false);

            if (history.replaceState) {
                history.replaceState(null, '', '#risk-' + encodeURIComponent(risk.id));
            }
            if (currentTab === 'pdf') renderPdfPreview();
        }

        function showEmptyState() {
            activeRiskId = null;
            renderSidebar();
            if (detailTitle) detailTitle.textContent = 'Aucun risque configuré';
            if (detailLevelBadge) detailLevelBadge.classList.add('u-d-none');
            if (detailTransBadge) detailTransBadge.classList.add('u-d-none');
            if (form) form.reset();
            if (recsList) recsList.innerHTML = '';
            if (recsCountElem) recsCountElem.textContent = '0';
            if (pdfPreviewSheet) pdfPreviewSheet.innerHTML = '';
            setFormDisabled(true);
        }

        function setFormDisabled(disabled) {
            if (!form) return;
            form.querySelectorAll('input, textarea, select, button').forEach(function (el) {
                el.disabled = disabled;
            });
            if (tabBtnPdf) tabBtnPdf.disabled = disabled;
        }

        // ── Formulaire ──
        function populateForm(risk) {
            currentLevel = risk.level;
            updateLevelSegmentedUI(currentLevel);

            if (fieldTitleFr) fieldTitleFr.value = risk.title_fr;
            if (fieldTitleEn) fieldTitleEn.value = risk.title_en;
            if (fieldDescFr) fieldDescFr.value = risk.description_fr;
            if (fieldDescEn) fieldDescEn.value = risk.description_en;
            if (wrapNewCat) wrapNewCat.classList.add('u-d-none');

            populateCategorySelect(risk.category_fr);
            populateRecommendations(risk);
            updateHeader(risk);
            updateEnFieldStates();
        }

        function updateLevelSegmentedUI(level) {
            if (btnLevelMajor) btnLevelMajor.setAttribute('aria-pressed', level === 'major' ? 'true' : 'false');
            if (btnLevelStandard) btnLevelStandard.setAttribute('aria-pressed', level === 'major' ? 'false' : 'true');
        }

        function updateHeader(risk) {
            if (detailTitle) detailTitle.textContent = risk.title_fr || 'Sans titre';
            if (detailLevelBadge) {
                const isMajor = risk.level === 'major';
                detailLevelBadge.textContent = isMajor ? 'Majeur' : 'Standard';
                detailLevelBadge.dataset.val = isMajor ? 'danger' : 'warning';
                detailLevelBadge.classList.remove('u-d-none');
            }
            if (detailTransBadge) {
                const status = computeTranslationStatus(risk);
                detailTransBadge.textContent = 'EN INCOMPLET · ' + status.missing_count +
                    ' CHAMP' + (status.missing_count > 1 ? 'S' : '');
                detailTransBadge.classList.toggle('u-d-none', status.is_complete);
            }
        }

        function toggleMissing(field, badge) {
            if (!field) return;
            const missing = isMissingTranslation(field.value);
            field.classList.toggle('is-missing', missing);
            if (badge) badge.classList.toggle('u-d-none', !missing);
        }

        function updateEnFieldStates() {
            toggleMissing(fieldTitleEn, badgeTitleEnStatus);
            toggleMissing(fieldDescEn, badgeDescEnStatus);
            if (recsList) {
                recsList.querySelectorAll('.bvrs-rec-input-en').forEach(function (ta) { toggleMissing(ta); });
            }
        }

        function findSharedCategory(fr) {
            const key = (fr || '').trim().toUpperCase();
            return sharedCategories.find(function (c) { return c.fr === key; }) || null;
        }

        /** Ajoute (ou complète la traduction d') une catégorie dans la liste commune. */
        function registerSharedCategory(fr, en) {
            const key = (fr || '').trim().toUpperCase();
            if (!key) return;
            const existing = findSharedCategory(key);
            if (!existing) {
                sharedCategories.push({ fr: key, en: (en || '').trim() });
            } else if (!existing.en && en) {
                existing.en = en.trim();
            }
        }

        function appendCategoryOption(parent, cat, selected) {
            const opt = document.createElement('option');
            opt.value = cat;
            opt.textContent = cat;
            opt.selected = cat === selected;
            parent.appendChild(opt);
        }

        /**
         * Menu des catégories : celles déjà utilisées sur cet écran, puis toutes les autres
         * catégories communes (généraux + véhicules) pour pouvoir les réutiliser.
         */
        function populateCategorySelect(selectedCategory) {
            if (!fieldCategorySelect) return;
            fieldCategorySelect.innerHTML = '';

            const sel = (selectedCategory || '').trim().toUpperCase();
            const local = [];
            allRisks().forEach(function (r) {
                const c = catKey(r);
                if (c && !local.includes(c)) local.push(c);
            });
            if (sel && !local.includes(sel) && !findSharedCategory(sel)) local.push(sel);
            const others = sharedCategories
                .map(function (c) { return c.fr; })
                .filter(function (c) { return !local.includes(c); });
            if (!local.length && !others.length) local.push('GÉNÉRAL');

            if (others.length && local.length) {
                const groupLocal = document.createElement('optgroup');
                groupLocal.label = 'Utilisées ici';
                local.forEach(function (c) { appendCategoryOption(groupLocal, c, sel); });
                fieldCategorySelect.appendChild(groupLocal);

                const groupOthers = document.createElement('optgroup');
                groupOthers.label = 'Autres catégories';
                others.forEach(function (c) { appendCategoryOption(groupOthers, c, sel); });
                fieldCategorySelect.appendChild(groupOthers);
            } else {
                local.concat(others).forEach(function (c) { appendCategoryOption(fieldCategorySelect, c, sel); });
            }

            const newOpt = document.createElement('option');
            newOpt.value = '__new__';
            newOpt.textContent = '+ Nouvelle catégorie…';
            fieldCategorySelect.appendChild(newOpt);
        }

        /** Catégorie EN : celle du risque si inchangée, sinon celle de la liste commune. */
        function resolveCategoryEn(categoryFr) {
            const key = categoryFr.toUpperCase();
            const active = findRisk(activeRiskId);
            if (active && catKey(active) === key && active.category_en) return active.category_en;
            const shared = findSharedCategory(key);
            if (shared && shared.en) return shared.en;
            const sibling = risksList.find(function (r) { return catKey(r) === key && r.category_en; });
            return sibling ? sibling.category_en : categoryFr;
        }

        function populateRecommendations(risk) {
            if (!recsList) return;
            recsList.innerHTML = '';
            risk.recommendations_fr.forEach(function (fr, i) {
                addRecommendationRow(fr, risk.recommendations_en[i] || '');
            });
            updateRecsCount();
            refreshIcons();
        }

        let draggedRecRow = null;
        function addRecommendationRow(frVal, enVal) {
            if (!recsList) return null;
            const row = document.createElement('div');
            row.className = 'bvrs-recrow';
            row.innerHTML =
                '<span class="bvrs-hd" title="Glisser pour réorganiser" aria-hidden="true"></span>' +
                '<textarea class="form-input bvrs-rec-input-fr" rows="3" placeholder="Recommandation en français" aria-label="Recommandation (FR)"></textarea>' +
                '<textarea class="form-input bvrs-rec-input-en" rows="3" placeholder="Traduction manquante" aria-label="Recommendation (EN)"></textarea>' +
                '<button type="button" class="admin-btn admin-btn-secondary admin-btn-sm bvrs-rec-btn-remove" title="Supprimer cette recommandation" aria-label="Supprimer cette recommandation">' +
                '<i data-lucide="x" aria-hidden="true"></i></button>';

            const frArea = row.querySelector('.bvrs-rec-input-fr');
            const enArea = row.querySelector('.bvrs-rec-input-en');
            frArea.value = frVal || '';
            enArea.value = enVal || '';
            toggleMissing(enArea);

            row.querySelector('.bvrs-rec-btn-remove').addEventListener('click', function () {
                row.remove();
                updateRecsCount();
                onFormChange();
            });

            // Glisser uniquement depuis la poignée (sinon la sélection de texte devient impossible)
            const handle = row.querySelector('.bvrs-hd');
            handle.addEventListener('mousedown', function () { row.draggable = true; });
            row.addEventListener('dragstart', function (e) {
                draggedRecRow = row;
                e.dataTransfer.effectAllowed = 'move';
                row.classList.add('is-dragging');
            });
            row.addEventListener('dragend', function () {
                row.draggable = false;
                draggedRecRow = null;
                row.classList.remove('is-dragging');
                recsList.querySelectorAll('.bvrs-drag-over').forEach(function (r) { r.classList.remove('bvrs-drag-over'); });
            });
            row.addEventListener('dragover', function (e) {
                if (!draggedRecRow || draggedRecRow === row) return;
                e.preventDefault();
                row.classList.add('bvrs-drag-over');
            });
            row.addEventListener('dragleave', function () { row.classList.remove('bvrs-drag-over'); });
            row.addEventListener('drop', function (e) {
                e.preventDefault();
                row.classList.remove('bvrs-drag-over');
                if (!draggedRecRow || draggedRecRow === row) return;
                const rows = Array.from(recsList.children);
                const before = rows.indexOf(draggedRecRow) > rows.indexOf(row);
                recsList.insertBefore(draggedRecRow, before ? row : row.nextSibling);
                onFormChange();
            });

            recsList.appendChild(row);
            return row;
        }

        function updateRecsCount() {
            if (recsCountElem && recsList) {
                recsCountElem.textContent = recsList.querySelectorAll('.bvrs-recrow').length;
            }
        }

        function collectCurrentFormData() {
            const base = findRisk(activeRiskId) || {};
            const categoryFr = (fieldCategorySelect && fieldCategorySelect.value !== '__new__')
                ? fieldCategorySelect.value
                : (base.category_fr || 'GÉNÉRAL');

            const recsFr = [];
            const recsEn = [];
            if (recsList) {
                recsList.querySelectorAll('.bvrs-recrow').forEach(function (row) {
                    const fr = row.querySelector('.bvrs-rec-input-fr').value.trim();
                    const en = row.querySelector('.bvrs-rec-input-en').value.trim();
                    if (fr || en) {
                        recsFr.push(fr);
                        recsEn.push(en);
                    }
                });
            }

            // On part du risque d'origine pour préserver d'éventuels champs non édités ici.
            const data = Object.assign({}, base, {
                id: activeRiskId,
                level: currentLevel,
                category_fr: categoryFr,
                category_en: resolveCategoryEn(categoryFr),
                title_fr: fieldTitleFr ? fieldTitleFr.value.trim() : '',
                title_en: fieldTitleEn ? fieldTitleEn.value.trim() : '',
                description_fr: fieldDescFr ? fieldDescFr.value.trim() : '',
                description_en: fieldDescEn ? fieldDescEn.value.trim() : '',
                recommendations_fr: recsFr,
                recommendations_en: recsEn
            });
            delete data._translation_status;
            delete data.title;
            delete data.description;
            delete data.recommendations;
            delete data.category;
            return data;
        }

        function onFormChange() {
            if (!activeRiskId) return;
            const data = collectCurrentFormData();
            updateHeader(data);
            updateEnFieldStates();
            updateActiveSidebarItem(data);
            isDirty = true;
            updateBottomBar();
            if (currentTab === 'pdf') renderPdfPreview();
        }

        function updateBottomBar() {
            if (bottomBar) bottomBar.classList.toggle('u-d-none', !isDirty);
        }

        // ── Enregistrement ──
        function saveActiveRisk(onSuccess) {
            if (isSaving || !activeRiskId) return;
            const data = collectCurrentFormData();
            if (!data.title_fr) {
                flash('Le titre du risque en français est obligatoire.', 'error');
                if (currentTab !== 'edit' && tabBtnEdit) tabBtnEdit.click();
                if (fieldTitleFr) fieldTitleFr.focus();
                return;
            }

            isSaving = true;
            if (btnSaveRisk) btnSaveRisk.disabled = true;
            if (btnModalSave) btnModalSave.disabled = true;
            if (btnSaveRiskLabel) btnSaveRiskLabel.textContent = 'Enregistrement…';

            postJson(urls.save, { risk: data })
                .then(function (res) {
                    const saved = normalizeRisk(res.risk);
                    registerSharedCategory(saved.category_fr, saved.category_en);
                    const idx = risksList.findIndex(function (r) { return r.id === saved.id; });
                    if (idx >= 0) {
                        risksList[idx] = saved;
                    } else {
                        // Nouveau risque : le serveur l'ajoute en fin de liste
                        risksList.push(saved);
                    }
                    if (draftNewRisk && draftNewRisk.id === saved.id) draftNewRisk = null;
                    isDirty = false;
                    flash('Risque enregistré.', 'success');
                    if (onSuccess) {
                        onSuccess();
                    } else {
                        selectRisk(saved.id);
                    }
                })
                .catch(function (err) {
                    flash("Erreur lors de l'enregistrement : " + err.message, 'error');
                })
                .finally(function () {
                    isSaving = false;
                    if (btnSaveRisk) btnSaveRisk.disabled = false;
                    if (btnModalSave) btnModalSave.disabled = false;
                    if (btnSaveRiskLabel) btnSaveRiskLabel.textContent = 'Enregistrer ce risque';
                });
        }

        // ── Suppression ──
        function deleteActiveRisk() {
            if (!activeRiskId) return;
            if (!window.confirm('Supprimer ce risque le retire de tous les futurs protocoles. Êtes-vous sûr de vouloir continuer ?')) return;

            const removeLocally = function () {
                const idx = risksList.findIndex(function (r) { return r.id === activeRiskId; });
                if (idx >= 0) risksList.splice(idx, 1);
                draftNewRisk = null;
                isDirty = false;
                updateBottomBar();
                if (risksList.length) {
                    selectRisk(risksList[Math.min(Math.max(idx, 0), risksList.length - 1)].id);
                } else {
                    showEmptyState();
                }
            };

            // Brouillon jamais enregistré : rien à supprimer côté serveur
            if (draftNewRisk && draftNewRisk.id === activeRiskId) {
                removeLocally();
                return;
            }

            if (btnDeleteRisk) btnDeleteRisk.disabled = true;
            postJson(urls.del, { risk_id: activeRiskId })
                .then(function () {
                    flash('Risque supprimé.', 'success');
                    removeLocally();
                })
                .catch(function (err) {
                    flash('Erreur lors de la suppression : ' + err.message, 'error');
                })
                .finally(function () {
                    if (btnDeleteRisk) btnDeleteRisk.disabled = false;
                });
        }

        // ── Création ──
        function addNewRisk() {
            const active = findRisk(activeRiskId);
            const categoryFr = active ? active.category_fr : 'GÉNÉRAL';
            draftNewRisk = normalizeRisk({
                id: 'risk_' + Date.now(),
                category_fr: categoryFr,
                category_en: active ? active.category_en : '',
                level: 'standard',
                title_fr: '',
                recommendations_fr: [''],
                recommendations_en: ['']
            });
            if (sidebarSearchInput) sidebarSearchInput.value = '';
            sidebarSearchQuery = '';
            selectRisk(draftNewRisk.id);
            if (currentTab !== 'edit' && tabBtnEdit) tabBtnEdit.click();
            isDirty = true;
            updateBottomBar();
            if (detailTitle) detailTitle.textContent = 'Nouveau risque';
            if (fieldTitleFr) fieldTitleFr.focus();
        }

        // ── Aperçu PDF : même balisage que templates/pdf/risk_assessment.html ──
        const ICON_MAJOR = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" class="bvrs-risk-icon-svg bvrs-icon-major"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2" fill="#DC2626" stroke="#DC2626"/><line x1="12" x2="12" y1="8" y2="12" stroke="#FFFFFF" stroke-width="2.5" stroke-linecap="round"/><circle cx="12" cy="16" r="1.2" fill="#FFFFFF"/></svg>';
        const ICON_STANDARD = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" class="bvrs-risk-icon-svg bvrs-icon-standard"><circle cx="12" cy="12" r="10" fill="#FFC845" stroke="#FFC845"/><line x1="12" x2="12" y1="8" y2="12" stroke="#18181B" stroke-width="2.5" stroke-linecap="round"/><circle cx="12" cy="16" r="1.2" fill="#18181B"/></svg>';

        function riskCardHtml(risk, isEn, extraClass) {
            const isMajor = risk.level === 'major';
            const title = isEn ? (risk.title_en || risk.title_fr) : risk.title_fr;
            const desc = isEn ? (risk.description_en || risk.description_fr) : risk.description_fr;
            const recs = isEn
                ? risk.recommendations_fr.map(function (fr, i) { return risk.recommendations_en[i] || fr; })
                : risk.recommendations_fr;
            const badge = isMajor
                ? '<span class="bvrs-badge-major">' + (isEn ? 'HIGH RISK' : 'RISQUE MAJEUR') + '</span>'
                : '<span class="bvrs-badge-standard">' + (isEn ? 'RISK' : 'RISQUE') + '</span>';

            const recsHtml = recs.length ? (
                '<div class="bvrs-recs-box">' +
                '<div class="bvrs-recs-title">' + (isEn ? 'Recommendations' : 'Recommandations') + '</div>' +
                '<table class="bvrs-recs-table"><tbody>' +
                recs.map(function (r) {
                    return '<tr class="bvrs-rec-row"><td class="bvrs-rec-check">✓</td><td class="bvrs-rec-text">' + escapeHtml(r) + '</td></tr>';
                }).join('') +
                '</tbody></table></div>'
            ) : '';

            return '<div class="bvrs-risk-card ' + (isMajor ? 'bvrs-risk-card--major' : 'bvrs-risk-card--standard') + (extraClass ? ' ' + extraClass : '') + '">' +
                '<div class="bvrs-risk-header">' +
                '<div class="bvrs-risk-header-cell bvrs-risk-icon-cell">' + (isMajor ? ICON_MAJOR : ICON_STANDARD) + '</div>' +
                '<div class="bvrs-risk-header-cell"><span class="bvrs-risk-title">' + escapeHtml(title || 'Sans titre') + '</span> ' + badge + '</div>' +
                '</div>' +
                '<div class="bvrs-risk-desc">' + escapeHtml(desc) + '</div>' +
                recsHtml +
                '</div>';
        }

        function renderPdfPreview() {
            if (!pdfPreviewSheet || !activeRiskId) return;
            const current = normalizeRisk(collectCurrentFormData());
            const isEn = previewLang === 'en';
            const banner = (isEn ? (current.category_en || current.category_fr) : current.category_fr) || 'GÉNÉRAL';

            // Voisin : risque suivant de la même catégorie (sinon le précédent), atténué
            const sameCat = risksList.filter(function (r) { return catKey(r) === catKey(current); });
            const pos = sameCat.findIndex(function (r) { return r.id === current.id; });
            const neighbour = pos >= 0 ? (sameCat[pos + 1] || sameCat[pos - 1]) : sameCat[0];

            pdfPreviewSheet.innerHTML =
                '<div class="bvrs-category-banner">' + escapeHtml(banner) + '</div>' +
                riskCardHtml(current, isEn) +
                (neighbour && neighbour.id !== current.id ? riskCardHtml(neighbour, isEn, 'bvrs-card-dimmed') : '');
        }

        // ── Événements ──
        if (form) form.addEventListener('submit', function (e) { e.preventDefault(); });

        if (btnAddRisk) btnAddRisk.addEventListener('click', function () { guard(addNewRisk); });

        if (sidebarSearchInput) {
            sidebarSearchInput.addEventListener('input', function () {
                sidebarSearchQuery = this.value;
                renderSidebar();
            });
        }

        sidebarFilterBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                setActivePill(sidebarFilterBtns, this);
                activeFilter = this.dataset.filter || 'all';
                renderSidebar();
            });
        });

        function switchTab(tab) {
            currentTab = tab;
            const isPdf = tab === 'pdf';
            if (tabBtnEdit) tabBtnEdit.setAttribute('aria-selected', isPdf ? 'false' : 'true');
            if (tabBtnPdf) tabBtnPdf.setAttribute('aria-selected', isPdf ? 'true' : 'false');
            if (tabPaneEdit) tabPaneEdit.classList.toggle('u-d-none', isPdf);
            if (tabPanePdf) tabPanePdf.classList.toggle('u-d-none', !isPdf);
            if (isPdf) renderPdfPreview();
        }
        if (tabBtnEdit) tabBtnEdit.addEventListener('click', function () { switchTab('edit'); });
        if (tabBtnPdf) tabBtnPdf.addEventListener('click', function () { switchTab('pdf'); });

        function setPreviewLang(lang) {
            previewLang = lang;
            if (btnLangFr) btnLangFr.setAttribute('aria-pressed', lang === 'fr' ? 'true' : 'false');
            if (btnLangEn) btnLangEn.setAttribute('aria-pressed', lang === 'en' ? 'true' : 'false');
            renderPdfPreview();
        }
        if (btnLangFr) btnLangFr.addEventListener('click', function () { setPreviewLang('fr'); });
        if (btnLangEn) btnLangEn.addEventListener('click', function () { setPreviewLang('en'); });

        function setLevel(level) {
            if (currentLevel === level) return;
            currentLevel = level;
            updateLevelSegmentedUI(level);
            onFormChange();
        }
        if (btnLevelMajor) btnLevelMajor.addEventListener('click', function () { setLevel('major'); });
        if (btnLevelStandard) btnLevelStandard.addEventListener('click', function () { setLevel('standard'); });

        let lastCategoryValue = '';
        if (fieldCategorySelect) {
            fieldCategorySelect.addEventListener('focus', function () { lastCategoryValue = this.value; });
            fieldCategorySelect.addEventListener('change', function () {
                if (this.value === '__new__') {
                    if (wrapNewCat) wrapNewCat.classList.remove('u-d-none');
                    if (inputNewCatEn) inputNewCatEn.value = '';
                    if (inputNewCat) {
                        inputNewCat.value = '';
                        inputNewCat.focus();
                    }
                    return;
                }
                lastCategoryValue = this.value;
                if (wrapNewCat) wrapNewCat.classList.add('u-d-none');
                onFormChange();
            });
        }

        function confirmNewCategory() {
            const newCat = inputNewCat ? inputNewCat.value.trim().toUpperCase() : '';
            if (!newCat) {
                if (inputNewCat) inputNewCat.focus();
                return;
            }
            const newCatEn = inputNewCatEn ? inputNewCatEn.value.trim().toUpperCase() : '';
            // Catégorie déjà existante ailleurs : on la réutilise telle quelle
            registerSharedCategory(newCat, newCatEn);
            populateCategorySelect(newCat);
            lastCategoryValue = newCat;
            if (wrapNewCat) wrapNewCat.classList.add('u-d-none');
            onFormChange();
        }

        function cancelNewCategory() {
            if (wrapNewCat) wrapNewCat.classList.add('u-d-none');
            if (fieldCategorySelect) {
                const active = findRisk(activeRiskId);
                fieldCategorySelect.value = lastCategoryValue || (active ? catKey(active) : '');
            }
        }

        if (btnConfirmNewCat) btnConfirmNewCat.addEventListener('click', confirmNewCategory);
        if (btnCancelNewCat) btnCancelNewCat.addEventListener('click', cancelNewCategory);
        [inputNewCat, inputNewCatEn].forEach(function (input) {
            if (!input) return;
            input.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') { e.preventDefault(); confirmNewCategory(); }
                if (e.key === 'Escape') { e.preventDefault(); cancelNewCategory(); }
            });
        });

        [fieldTitleFr, fieldTitleEn, fieldDescFr, fieldDescEn].forEach(function (input) {
            if (input) input.addEventListener('input', onFormChange);
        });
        // Délégation pour les textareas de recommandations
        if (recsList) {
            recsList.addEventListener('input', function (e) {
                if (e.target.matches('textarea')) onFormChange();
            });
        }

        if (btnAddRec) {
            btnAddRec.addEventListener('click', function () {
                const row = addRecommendationRow('', '');
                updateRecsCount();
                refreshIcons();
                onFormChange();
                if (row) row.querySelector('.bvrs-rec-input-fr').focus();
            });
        }

        if (btnDeleteRisk) btnDeleteRisk.addEventListener('click', deleteActiveRisk);
        if (btnCancelRisk) btnCancelRisk.addEventListener('click', discardChanges);
        if (btnSaveRisk) btnSaveRisk.addEventListener('click', function () { saveActiveRisk(); });

        // Modale anti-perte
        // Fermeture (× de la macro admin_modal) = rester sur le risque courant
        if (unsavedModal) {
            unsavedModal.querySelectorAll('[data-modal-close]').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    pendingAction = null;
                    closeModal();
                });
            });
        }
        if (btnModalDiscard) {
            btnModalDiscard.addEventListener('click', function () {
                const action = pendingAction;
                pendingAction = null;
                closeModal();
                discardChanges();
                if (action) action();
            });
        }
        if (btnModalSave) {
            btnModalSave.addEventListener('click', function () {
                const action = pendingAction;
                saveActiveRisk(function () {
                    pendingAction = null;
                    closeModal();
                    if (action) action();
                });
            });
        }
        if (unsavedModal) {
            unsavedModal.addEventListener('click', function (e) {
                if (e.target === unsavedModal) { pendingAction = null; closeModal(); }
            });
            document.addEventListener('keydown', function (e) {
                if (e.key === 'Escape' && unsavedModal.classList.contains('is-active')) {
                    pendingAction = null;
                    closeModal();
                }
            });
        }

        window.addEventListener('beforeunload', function (e) {
            if (isDirty) {
                e.preventDefault();
                e.returnValue = '';
            }
        });

        // Initialisation (sélection via #risk-<id> si présent)
        let initialId = risksList.length ? risksList[0].id : null;
        const hash = decodeURIComponent((window.location.hash || '').replace(/^#risk-/, ''));
        if (hash && findRisk(hash)) initialId = hash;

        if (initialId) {
            selectRisk(initialId);
            const activeItem = sidebarList && sidebarList.querySelector('.bvrs-side-it.is-selected');
            if (activeItem && activeItem.scrollIntoView) activeItem.scrollIntoView({ block: 'nearest' });
        } else {
            showEmptyState();
        }
        refreshIcons();
    }

    document.addEventListener('DOMContentLoaded', function () {
        initCatalogOverview();
        initMasterDetailEditor();
    });
})();
