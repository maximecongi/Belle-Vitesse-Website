/**
 * safety-rules-catalog.js — Contrôleur d'interface d'administration du catalogue des règles de sécurité (BVSR).
 *
 * - Éditeur de paires FR / EN à puces (Entrée = nouvelle puce, Retour arrière = suppression d'une puce vide,
 *   monter / descendre / supprimer), avec signalement des traductions manquantes.
 * - Modales avec confirmation avant de fermer en perdant des modifications non enregistrées.
 * - Erreurs de validation affichées dans la modale.
 * - Aide à l'insertion des variables {technicians_and} / {technicians_or} (règles référents BV) avec rendu en direct.
 * - Aperçu du protocole BVSR complet pour une sélection de véhicules et de référents.
 */

document.addEventListener('DOMContentLoaded', function () {
    const ruleModal = document.getElementById('ruleModal');
    if (!ruleModal) return;

    // ── Helpers ──────────────────────────────────────────────────────────────
    function refreshIcons(root) {
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons(root ? { root: root } : undefined);
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    function plural(n, singular, pluralForm) {
        return n + ' ' + (n > 1 ? pluralForm : singular);
    }

    function show(el) { if (el) el.classList.remove('u-d-none'); }
    function hide(el) { if (el) el.classList.add('u-d-none'); }

    function showFormError(el, message, focusTarget) {
        if (!el) return;
        el.textContent = message;
        show(el);
        el.scrollIntoView({ block: 'nearest' });
        if (focusTarget) focusTarget.focus();
    }

    // ── Modale générique : ouverture / fermeture / confirmation de perte ─────
    function createModalController(modalEl, formEl, closeSelector) {
        if (!modalEl) return null;
        const footerDefault = modalEl.querySelector('.bvsr-footer-default');
        const discardBar = modalEl.querySelector('.bvsr-discard-bar');
        let snapshot = '';
        let submitting = false;

        function serialize() {
            return formEl ? new URLSearchParams(new FormData(formEl)).toString() : '';
        }

        function hideDiscardBar() {
            hide(discardBar);
            show(footerDefault);
        }

        function isOpen() {
            return modalEl.classList.contains('is-active');
        }

        function open() {
            submitting = false;
            hideDiscardBar();
            modalEl.classList.remove('u-d-none');
            modalEl.classList.add('is-active');
            modalEl.setAttribute('aria-hidden', 'false');
            document.body.classList.add('u-overflow-hidden');
        }

        // À appeler une fois le formulaire rempli, pour fixer l'état de référence.
        function markClean() {
            snapshot = serialize();
        }

        function forceClose() {
            hideDiscardBar();
            modalEl.classList.add('u-d-none');
            modalEl.classList.remove('is-active');
            modalEl.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('u-overflow-hidden');
        }

        function requestClose() {
            if (formEl && !submitting && serialize() !== snapshot) {
                hide(footerDefault);
                show(discardBar);
                const cancelBtn = discardBar && discardBar.querySelector('.bvsr-discard-cancel');
                if (cancelBtn) cancelBtn.focus();
                return;
            }
            forceClose();
        }

        modalEl.querySelectorAll(closeSelector).forEach(function (btn) {
            btn.addEventListener('click', requestClose);
        });
        modalEl.addEventListener('click', function (e) {
            if (e.target === modalEl) requestClose();
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && isOpen()) requestClose();
        });

        if (discardBar) {
            const cancelBtn = discardBar.querySelector('.bvsr-discard-cancel');
            const confirmBtn = discardBar.querySelector('.bvsr-discard-confirm');
            if (cancelBtn) cancelBtn.addEventListener('click', hideDiscardBar);
            if (confirmBtn) confirmBtn.addEventListener('click', forceClose);
        }

        if (formEl) {
            formEl.addEventListener('submit', function (e) {
                // La validation est enregistrée après ce listener : on lit defaultPrevented
                // une fois tous les listeners exécutés.
                queueMicrotask(function () {
                    if (!e.defaultPrevented) submitting = true;
                });
            });
        }

        return { open: open, markClean: markClean, requestClose: requestClose, forceClose: forceClose, isOpen: isOpen };
    }

    // ── Éditeur de paires FR / EN à puces ────────────────────────────────────
    function createPairEditor(options) {
        const container = options.container;
        if (!container) return null;

        function rows() {
            return Array.from(container.querySelectorAll('.bvsr-rule-item'));
        }

        function refresh() {
            const all = rows();
            all.forEach(function (row, idx) {
                const fr = row.querySelector('.bvsr-input-fr');
                const en = row.querySelector('.bvsr-input-en');
                const frVal = fr.value.trim();
                const enVal = en.value.trim();
                fr.classList.toggle('is-missing', !frVal && !!enVal);
                en.classList.toggle('is-missing', !!frVal && !enVal);
                row.querySelector('.btn-move-up').disabled = (idx === 0);
                row.querySelector('.btn-move-down').disabled = (idx === all.length - 1);
            });
            if (options.onChange) options.onChange(api);
        }

        function stats() {
            let filled = 0;
            let missing = 0;
            rows().forEach(function (row) {
                const frVal = row.querySelector('.bvsr-input-fr').value.trim();
                const enVal = row.querySelector('.bvsr-input-en').value.trim();
                if (frVal || enVal) filled++;
                if ((frVal || enVal) && !(frVal && enVal)) missing++;
            });
            return { total: rows().length, filled: filled, missing: missing };
        }

        function focusFr(row, atEnd) {
            const input = row && row.querySelector('.bvsr-input-fr');
            if (!input) return;
            input.focus();
            if (atEnd) input.setSelectionRange(input.value.length, input.value.length);
        }

        function addRow(fr, en, id, afterRow) {
            const row = document.createElement('div');
            row.className = 'bvsr-rule-item';
            row.innerHTML = `
                <div class="bvsr-bullet-indicator" aria-hidden="true">
                    <span class="bvsr-bullet-dot"></span>
                </div>
                <div class="bvsr-rule-fields">
                    ${options.idName ? `<input type="hidden" name="${options.idName}" value="${escapeHtml(id)}">` : ''}
                    <div class="bvsr-rule-input-group">
                        <span class="bvsr-lang-pill">FR</span>
                        <input type="text" name="${options.frName}" class="bvsr-rule-input bvsr-input-fr"
                            placeholder="${escapeHtml(options.frPlaceholder)}"
                            value="${escapeHtml(fr)}" autocomplete="off" aria-label="Texte français">
                    </div>
                    <div class="bvsr-rule-input-group">
                        <span class="bvsr-lang-pill bvsr-lang-pill--en">EN</span>
                        <input type="text" name="${options.enName}" class="bvsr-rule-input bvsr-input-en"
                            placeholder="${escapeHtml(options.enPlaceholder)}"
                            value="${escapeHtml(en)}" autocomplete="off" aria-label="Traduction anglaise">
                    </div>
                </div>
                <div class="bvsr-rule-actions">
                    <button type="button" class="bvsr-action-btn btn-move-up" title="Monter" aria-label="Monter">
                        <i data-lucide="arrow-up"></i>
                    </button>
                    <button type="button" class="bvsr-action-btn btn-move-down" title="Descendre" aria-label="Descendre">
                        <i data-lucide="arrow-down"></i>
                    </button>
                    <button type="button" class="bvsr-action-btn bvsr-action-btn--delete btn-delete-row" title="Supprimer" aria-label="Supprimer">
                        <i data-lucide="trash-2"></i>
                    </button>
                </div>
            `;

            const inputFr = row.querySelector('.bvsr-input-fr');
            const inputEn = row.querySelector('.bvsr-input-en');

            function addAfterAndFocus(e) {
                e.preventDefault();
                focusFr(addRow('', '', '', row));
            }

            inputFr.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    addAfterAndFocus(e);
                } else if (e.key === 'Backspace' && inputFr.value === '' && inputEn.value === '' && rows().length > 1) {
                    e.preventDefault();
                    const prev = row.previousElementSibling;
                    row.remove();
                    refresh();
                    focusFr(prev, true);
                }
            });
            inputEn.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') addAfterAndFocus(e);
            });
            inputFr.addEventListener('input', refresh);
            inputEn.addEventListener('input', refresh);

            row.querySelector('.btn-move-up').addEventListener('click', function () {
                const prev = row.previousElementSibling;
                if (prev) {
                    container.insertBefore(row, prev);
                    refresh();
                    inputFr.focus();
                }
            });
            row.querySelector('.btn-move-down').addEventListener('click', function () {
                const next = row.nextElementSibling;
                if (next) {
                    container.insertBefore(next, row);
                    refresh();
                    inputFr.focus();
                }
            });
            row.querySelector('.btn-delete-row').addEventListener('click', function () {
                if (options.keepOneRow && rows().length <= 1) {
                    inputFr.value = '';
                    inputEn.value = '';
                    refresh();
                    inputFr.focus();
                    return;
                }
                row.remove();
                refresh();
            });

            if (afterRow && afterRow.parentNode === container) {
                afterRow.after(row);
            } else {
                container.appendChild(row);
            }
            refreshIcons(row);
            refresh();
            return row;
        }

        // Remplit l'éditeur avec des listes FR / EN appariées par index.
        function load(listFr, listEn, ids) {
            container.innerHTML = '';
            const fr = listFr || [];
            const en = listEn || [];
            const count = Math.max(fr.length, en.length);
            for (let i = 0; i < count; i++) {
                addRow(fr[i] || '', en[i] || '', (ids && ids[i]) || '');
            }
            if (count === 0) addRow('', '', '');
            refresh();
        }

        // Première ligne où l'anglais est saisi sans le français (le français fait foi).
        function firstRowMissingFr() {
            return rows().find(function (row) {
                return !row.querySelector('.bvsr-input-fr').value.trim()
                    && row.querySelector('.bvsr-input-en').value.trim();
            }) || null;
        }

        const api = {
            addRow: addRow,
            load: load,
            rows: rows,
            stats: stats,
            focusFr: focusFr,
            firstRowMissingFr: firstRowMissingFr,
        };
        return api;
    }

    function renderMissingBadge(badge, missing) {
        if (!badge) return;
        if (missing > 0) {
            badge.innerHTML = '<i data-lucide="languages" class="u-w-14 u-h-14 u-m-0"></i> '
                + plural(missing, 'traduction manquante', 'traductions manquantes');
            show(badge);
            refreshIcons(badge);
        } else {
            hide(badge);
        }
    }

    // ═════════════════════════════════════════════════════════════════════════
    // MODALE D'ÉDITION DES CONSIGNES (générales / référents BV / véhicule)
    // ═════════════════════════════════════════════════════════════════════════
    const ruleForm = document.getElementById('ruleForm');
    const ruleController = createModalController(ruleModal, ruleForm, '.btn-close-rule-modal');

    const modalTitle = document.getElementById('modalTitle');
    const modalSubtitle = document.getElementById('modalSubtitle');
    const modalVehicleImg = document.getElementById('modalVehicleImg');
    const modalVehicleAvatarWrap = document.getElementById('modalVehicleAvatarWrap');
    const modalGeneralIconWrap = document.getElementById('modalGeneralIconWrap');
    const inputRuleScope = document.getElementById('modal_rule_scope');
    const inputVehicleId = document.getElementById('modal_vehicle_id');
    const inputLabel = document.getElementById('modal_label');
    const vehicleLabelGroup = document.getElementById('modal_vehicle_label_group');
    const vehicleEquipmentGroup = document.getElementById('modal_vehicle_equipment_group');
    const rulesContainer = document.getElementById('bvsr-rules-container');
    const emptyState = document.getElementById('bvsr-empty-state');
    const rulesCountBadge = document.getElementById('bvsr-rules-count-badge');
    const missingEnBadge = document.getElementById('bvsr-missing-en-badge');
    const formError = document.getElementById('bvsr-form-error');
    const btnAddRule = document.getElementById('btn-add-rule-item');
    const eqCheckboxes = document.querySelectorAll('.bvsr-eq-checkbox');
    const equipmentCountBadge = document.getElementById('bvsr-equipment-count-badge');

    const placeholderHelp = document.getElementById('bvsr-placeholder-help');
    const exampleTechniciansInput = document.getElementById('bvsr-example-technicians');
    const placeholderRendered = document.getElementById('bvsr-placeholder-rendered');
    let lastFocusedRuleInput = null;

    const ruleEditor = createPairEditor({
        container: rulesContainer,
        frName: 'rules_fr[]',
        enName: 'rules_en[]',
        frPlaceholder: 'Écrire une consigne de sécurité... (ex: Casque obligatoire en roulage)',
        enPlaceholder: 'Traduction anglaise... (ex: Helmet mandatory while moving)',
        keepOneRow: true,
        onChange: function (editor) {
            const s = editor.stats();
            if (rulesCountBadge) rulesCountBadge.textContent = plural(s.filled, 'consigne', 'consignes');
            if (emptyState) emptyState.classList.toggle('u-d-none', s.total > 0);
            renderMissingBadge(missingEnBadge, s.missing);
            renderPlaceholderPreview();
        },
    });

    function updateVehicleEquipmentCount() {
        if (!equipmentCountBadge) return;
        const checked = Array.from(eqCheckboxes).filter(function (cb) { return cb.checked; }).length;
        equipmentCountBadge.textContent = plural(checked, 'équipement coché', 'équipements cochés');
    }
    eqCheckboxes.forEach(function (cb) {
        cb.addEventListener('change', updateVehicleEquipmentCount);
    });

    if (btnAddRule) {
        btnAddRule.addEventListener('click', function () {
            ruleEditor.focusFr(ruleEditor.addRow('', '', ''));
        });
    }

    // ── Variables {technicians_and} / {technicians_or} ({technicians} = ancien nom de {technicians_and}) ──
    function formatNames(raw, conjunction) {
        const names = (raw || '').split(',').map(function (n) { return n.trim(); }).filter(Boolean);
        if (names.length <= 1) return names.join('');
        if (names.length === 2) return names.join(' ' + conjunction + ' ');
        return names.slice(0, -1).join(', ') + ' ' + conjunction + ' ' + names[names.length - 1];
    }

    function applyPlaceholders(text, lang) {
        const raw = exampleTechniciansInput ? exampleTechniciansInput.value : '';
        const andWord = lang === 'en' ? 'and' : 'et';
        const orWord = lang === 'en' ? 'or' : 'ou';
        return escapeHtml(text)
            .split('{technicians_or}').join('<strong>' + escapeHtml(formatNames(raw, orWord)) + '</strong>')
            .split('{technicians_and}').join('<strong>' + escapeHtml(formatNames(raw, andWord)) + '</strong>')
            .split('{technicians}').join('<strong>' + escapeHtml(formatNames(raw, andWord)) + '</strong>');
    }

    function renderPlaceholderPreview() {
        if (!placeholderRendered || !placeholderHelp || placeholderHelp.classList.contains('u-d-none')) return;
        const row = lastFocusedRuleInput && lastFocusedRuleInput.closest('.bvsr-rule-item');
        if (!row || !row.isConnected) {
            placeholderRendered.innerHTML = '<span class="u-text-muted">Cliquez dans une consigne pour voir son rendu.</span>';
            return;
        }
        const fr = row.querySelector('.bvsr-input-fr').value.trim();
        const en = row.querySelector('.bvsr-input-en').value.trim();
        placeholderRendered.innerHTML =
            '<span class="bvsr-pair-fr">' + (fr ? applyPlaceholders(fr, 'fr') : '<span class="u-text-muted">—</span>') + '</span>'
            + '<span class="bvsr-pair-en">' + (en ? applyPlaceholders(en, 'en') : '<span class="u-text-muted">—</span>') + '</span>';
    }

    if (rulesContainer) {
        rulesContainer.addEventListener('focusin', function (e) {
            if (e.target.classList.contains('bvsr-rule-input')) {
                lastFocusedRuleInput = e.target;
                renderPlaceholderPreview();
            }
        });
    }
    if (exampleTechniciansInput) {
        exampleTechniciansInput.addEventListener('input', renderPlaceholderPreview);
    }

    document.querySelectorAll('.bvsr-insert-var').forEach(function (btn) {
        // Empêche le bouton de voler le focus au champ en cours d'édition
        btn.addEventListener('mousedown', function (e) { e.preventDefault(); });
        btn.addEventListener('click', function () {
            let input = lastFocusedRuleInput;
            if (!input || !input.isConnected) {
                const lastRow = ruleEditor.rows().slice(-1)[0];
                input = lastRow && lastRow.querySelector('.bvsr-input-fr');
            }
            if (!input) return;
            const token = btn.getAttribute('data-insert');
            const start = input.selectionStart != null ? input.selectionStart : input.value.length;
            const end = input.selectionEnd != null ? input.selectionEnd : input.value.length;
            input.value = input.value.slice(0, start) + token + input.value.slice(end);
            input.focus();
            input.setSelectionRange(start + token.length, start + token.length);
            input.dispatchEvent(new Event('input', { bubbles: true }));
        });
    });

    // ── Ouverture de l'éditeur selon la section ──
    function openRuleEditor(config) {
        const isVehicle = config.scope === 'vehicle';

        if (inputRuleScope) inputRuleScope.value = config.scope;
        if (inputVehicleId) inputVehicleId.value = config.vehicleId || '';
        if (modalTitle) modalTitle.textContent = config.title;
        if (modalSubtitle) modalSubtitle.textContent = config.subtitle;
        if (modalVehicleImg && config.image) modalVehicleImg.src = config.image;

        (isVehicle ? show : hide)(modalVehicleAvatarWrap);
        (isVehicle ? hide : show)(modalGeneralIconWrap);
        (isVehicle ? show : hide)(vehicleLabelGroup);
        (isVehicle ? show : hide)(vehicleEquipmentGroup);
        (config.scope === 'bv_referents' ? show : hide)(placeholderHelp);
        if (inputLabel) inputLabel.value = isVehicle ? (config.label || '') : '';
        hide(formError);

        lastFocusedRuleInput = null;
        ruleEditor.load(config.rulesFr, config.rulesEn);

        const assigned = config.equipmentIds || [];
        eqCheckboxes.forEach(function (cb) {
            cb.checked = isVehicle && assigned.includes(cb.value);
        });
        updateVehicleEquipmentCount();

        ruleController.open();
        ruleController.markClean();
        setTimeout(function () {
            ruleEditor.focusFr(ruleEditor.rows()[0]);
        }, 60);
    }

    function readJsonAttr(el, attr, fallback) {
        try {
            return JSON.parse(el.getAttribute(attr) || '') || fallback;
        } catch (err) {
            console.error('Données BVSR illisibles (' + attr + ') :', err);
            return fallback;
        }
    }

    const editGeneralButton = document.querySelector('.btn-edit-general-rule');
    if (editGeneralButton) {
        editGeneralButton.addEventListener('click', function () {
            const rules = readJsonAttr(editGeneralButton, 'data-rules', {});
            openRuleEditor({
                scope: 'general',
                title: 'Modifier les Règles Générales de Sécurité',
                subtitle: "Consignes universelles applicables à l'ensemble des tournages",
                rulesFr: rules.rules_fr,
                rulesEn: rules.rules_en,
            });
        });
    }

    const editBvReferentsButton = document.querySelector('.btn-edit-bv-referents-rule');
    if (editBvReferentsButton) {
        editBvReferentsButton.addEventListener('click', function () {
            const rules = readJsonAttr(editBvReferentsButton, 'data-rules', {});
            openRuleEditor({
                scope: 'bv_referents',
                title: 'Modifier les Règles Référents Plateau BV',
                subtitle: 'Consignes spécifiques intégrées lorsque des techniciens BV sont sur le tournage',
                rulesFr: rules.rules_fr,
                rulesEn: rules.rules_en,
            });
        });
    }

    document.querySelectorAll('.btn-edit-vehicle-rule').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const cat = readJsonAttr(btn, 'data-cat', {});
            const vId = btn.getAttribute('data-id') || '';
            openRuleEditor({
                scope: 'vehicle',
                vehicleId: vId,
                title: 'Modifier les Règles : ' + (cat.name || cat.label || vId),
                subtitle: 'Véhicule Flotte — Protocole BVSR dynamique',
                image: cat.image || '/static/imgs/placeholders/vehicle.svg',
                label: cat.label || cat.name || vId,
                rulesFr: cat.rules_fr,
                rulesEn: cat.rules_en,
                equipmentIds: cat.equipment_ids,
            });
        });
    });

    // ── Validation avant enregistrement (erreurs affichées dans la modale) ──
    if (ruleForm) {
        ruleForm.addEventListener('submit', function (e) {
            hide(formError);

            if (inputRuleScope && inputRuleScope.value === 'vehicle' && inputLabel && !inputLabel.value.trim()) {
                e.preventDefault();
                showFormError(formError, "Le nom d'affichage du véhicule est obligatoire.", inputLabel);
                return;
            }

            const rowMissingFr = ruleEditor.firstRowMissingFr();
            if (rowMissingFr) {
                e.preventDefault();
                showFormError(formError, 'Une consigne a une traduction anglaise mais pas de texte français.',
                    rowMissingFr.querySelector('.bvsr-input-fr'));
                return;
            }

            if (ruleEditor.stats().filled === 0) {
                e.preventDefault();
                showFormError(formError, 'Veuillez renseigner au moins une consigne de sécurité.',
                    rulesContainer.querySelector('.bvsr-input-fr'));
            }
        });
    }

    // ═════════════════════════════════════════════════════════════════════════
    // MODALE DU CATALOGUE D'ÉQUIPEMENTS
    // ═════════════════════════════════════════════════════════════════════════
    const eqCatalogModal = document.getElementById('equipmentCatalogModal');
    const eqCatalogForm = document.getElementById('equipmentCatalogForm');
    const btnEditEquipmentCatalog = document.querySelector('.btn-edit-equipment-catalog');
    const eqFormError = document.getElementById('bvsr-eq-form-error');
    const eqMissingBadge = document.getElementById('bvsr-eq-missing-en-badge');
    const btnAddCatalogEqItem = document.getElementById('btn-add-catalog-eq-item');

    if (eqCatalogModal && btnEditEquipmentCatalog) {
        const eqController = createModalController(eqCatalogModal, eqCatalogForm, '.btn-close-eq-modal');
        const eqEditor = createPairEditor({
            container: document.getElementById('eq-catalog-items-container'),
            idName: 'equipment_id[]',
            frName: 'equipment_fr[]',
            enName: 'equipment_en[]',
            frPlaceholder: "Nom de l'équipement en français...",
            enPlaceholder: 'Traduction anglaise...',
            keepOneRow: false,
            onChange: function (editor) {
                renderMissingBadge(eqMissingBadge, editor.stats().missing);
            },
        });

        btnEditEquipmentCatalog.addEventListener('click', function () {
            const items = readJsonAttr(btnEditEquipmentCatalog, 'data-catalog', []);
            hide(eqFormError);
            eqEditor.load(
                items.map(function (it) { return it.label_fr || ''; }),
                items.map(function (it) { return it.label_en || ''; }),
                items.map(function (it) { return it.id || ''; })
            );
            eqController.open();
            eqController.markClean();
            setTimeout(function () {
                eqEditor.focusFr(eqEditor.rows()[0]);
            }, 60);
        });

        if (btnAddCatalogEqItem) {
            btnAddCatalogEqItem.addEventListener('click', function () {
                eqEditor.focusFr(eqEditor.addRow('', '', ''));
            });
        }

        if (eqCatalogForm) {
            eqCatalogForm.addEventListener('submit', function (e) {
                hide(eqFormError);
                const rowMissingFr = eqEditor.firstRowMissingFr();
                if (rowMissingFr) {
                    e.preventDefault();
                    showFormError(eqFormError, 'Un équipement a une traduction anglaise mais pas de nom français.',
                        rowMissingFr.querySelector('.bvsr-input-fr'));
                }
            });
        }
    }

    // ═════════════════════════════════════════════════════════════════════════
    // MODALE D'APERÇU DU PROTOCOLE
    // ═════════════════════════════════════════════════════════════════════════
    const previewModal = document.getElementById('protocolPreviewModal');
    const btnOpenPreview = document.querySelector('.btn-open-protocol-preview');

    if (previewModal && btnOpenPreview) {
        const previewController = createModalController(previewModal, null, '.btn-close-preview-modal');
        const previewFrame = document.getElementById('bvsr-preview-frame');
        const previewPdfLink = document.getElementById('bvsr-preview-pdf-link');
        const previewTechnicians = document.getElementById('bvsr-preview-technicians');
        const previewVehicleCbs = previewModal.querySelectorAll('.bvsr-preview-vehicle-cb');
        const baseUrl = previewModal.getAttribute('data-preview-url');
        let debounceTimer = null;

        function buildPreviewUrl(extra) {
            const params = new URLSearchParams();
            previewVehicleCbs.forEach(function (cb) {
                if (cb.checked) params.append('vehicle', cb.value);
            });
            const techs = previewTechnicians ? previewTechnicians.value.trim() : '';
            if (techs) params.set('technicians', techs);
            Object.keys(extra || {}).forEach(function (k) { params.set(k, extra[k]); });
            const qs = params.toString();
            return baseUrl + (qs ? '?' + qs : '');
        }

        function reloadPreview() {
            if (previewFrame) previewFrame.src = buildPreviewUrl();
            if (previewPdfLink) previewPdfLink.href = buildPreviewUrl({ format: 'pdf' });
        }

        function scheduleReload() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(reloadPreview, 350);
        }

        previewVehicleCbs.forEach(function (cb) {
            cb.addEventListener('change', reloadPreview);
        });
        if (previewTechnicians) previewTechnicians.addEventListener('input', scheduleReload);

        btnOpenPreview.addEventListener('click', function () {
            previewController.open();
            reloadPreview();
        });
    }
});
