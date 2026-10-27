/**
 * safety-rules-catalog.js — Contrôleur d'interface d'administration pour le catalogue des règles de sécurité (BVSR).
 * 
 * Implémente l'Éditeur de Liste à Puces Dynamique conforme à la DA Belle Vitesse :
 * - Création automatique d'une nouvelle puce à l'appui sur 'Entrée'
 * - Suppression d'une puce vide à l'appui sur 'Retour arrière'
 * - Réorganisation des puces (monter / descendre) et suppression unitaire
 * - Appariement bilingue Français (prioritaire) & Anglais avec bascule d'affichage
 * - Gestion accessible de la modale .admin-modal-container
 */

document.addEventListener('DOMContentLoaded', function () {
    const modal = document.getElementById('ruleModal');
    if (!modal) return;

    const modalTitle = document.getElementById('modalTitle');
    const modalSubtitle = document.getElementById('modalSubtitle');
    const modalVehicleImg = document.getElementById('modalVehicleImg');
    const inputVehicleId = document.getElementById('modal_vehicle_id');
    const inputLabel = document.getElementById('modal_label');
    const rulesContainer = document.getElementById('bvsr-rules-container');
    const emptyState = document.getElementById('bvsr-empty-state');
    const btnAddRule = document.getElementById('btn-add-rule-item');
    const rulesCountBadge = document.getElementById('bvsr-rules-count-badge');
    const toggleEn = document.getElementById('bvsr-toggle-en');
    const form = document.getElementById('ruleForm');

    // ── Helper d'échappement HTML sécurisé ──
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ── Mise à jour de l'état (compteur, boutons réorganisation, empty state) ──
    function updateRulesState() {
        if (!rulesContainer) return;
        const items = rulesContainer.querySelectorAll('.bvsr-rule-item');
        const count = items.length;

        if (rulesCountBadge) {
            rulesCountBadge.textContent = count + (count > 1 ? ' consignes' : ' consigne');
        }

        if (emptyState) {
            if (count === 0) {
                emptyState.classList.remove('u-d-none');
            } else {
                emptyState.classList.add('u-d-none');
            }
        }

        items.forEach(function (item, idx) {
            const btnUp = item.querySelector('.btn-move-up');
            const btnDown = item.querySelector('.btn-move-down');
            if (btnUp) btnUp.disabled = (idx === 0);
            if (btnDown) btnDown.disabled = (idx === count - 1);
        });
    }

    // ── Création et insertion d'un point de liste à puces ──
    function addRuleItem(ruleFr = '', ruleEn = '', insertAfterElement = null) {
        if (!rulesContainer) return null;

        const row = document.createElement('div');
        row.className = 'bvsr-rule-item';

        row.innerHTML = `
            <div class="bvsr-bullet-indicator" aria-hidden="true">
                <span class="bvsr-bullet-dot"></span>
            </div>
            <div class="bvsr-rule-fields">
                <div class="bvsr-rule-input-group">
                    <span class="bvsr-lang-pill">FR</span>
                    <input type="text" name="rules_fr[]" class="bvsr-rule-input bvsr-input-fr"
                        placeholder="Écrire une consigne de sécurité... (ex: Casque obligatoire en roulage)"
                        value="${escapeHtml(ruleFr)}" autocomplete="off">
                </div>
                <div class="bvsr-rule-input-group bvsr-group-en">
                    <span class="bvsr-lang-pill bvsr-lang-pill--en">EN</span>
                    <input type="text" name="rules_en[]" class="bvsr-rule-input bvsr-input-en"
                        placeholder="Traduction anglaise (optionnel)... (ex: Helmet mandatory while moving)"
                        value="${escapeHtml(ruleEn)}" autocomplete="off">
                </div>
            </div>
            <div class="bvsr-rule-actions">
                <button type="button" class="bvsr-action-btn btn-move-up" title="Monter cette consigne" aria-label="Monter">
                    <i data-lucide="arrow-up"></i>
                </button>
                <button type="button" class="bvsr-action-btn btn-move-down" title="Descendre cette consigne" aria-label="Descendre">
                    <i data-lucide="arrow-down"></i>
                </button>
                <button type="button" class="bvsr-action-btn bvsr-action-btn--delete btn-delete-rule" title="Supprimer cette consigne" aria-label="Supprimer">
                    <i data-lucide="trash-2"></i>
                </button>
            </div>
        `;

        const inputFr = row.querySelector('.bvsr-input-fr');
        const inputEn = row.querySelector('.bvsr-input-en');
        const btnUp = row.querySelector('.btn-move-up');
        const btnDown = row.querySelector('.btn-move-down');
        const btnDelete = row.querySelector('.btn-delete-rule');

        // ── Navigation clavier intelligente : Entrée = Nouvelle puce instantanée ──
        if (inputFr) {
            inputFr.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const newRow = addRuleItem('', '', row);
                    if (newRow) {
                        const newFr = newRow.querySelector('.bvsr-input-fr');
                        if (newFr) newFr.focus();
                    }
                } else if (e.key === 'Backspace' && inputFr.value === '' && (!inputEn || inputEn.value === '')) {
                    const allItems = rulesContainer.querySelectorAll('.bvsr-rule-item');
                    if (allItems.length > 1) {
                        e.preventDefault();
                        const prev = row.previousElementSibling;
                        row.remove();
                        updateRulesState();
                        if (prev) {
                            const prevInput = prev.querySelector('.bvsr-input-fr');
                            if (prevInput) {
                                prevInput.focus();
                                prevInput.setSelectionRange(prevInput.value.length, prevInput.value.length);
                            }
                        }
                    }
                }
            });
        }

        if (inputEn) {
            inputEn.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const newRow = addRuleItem('', '', row);
                    if (newRow) {
                        const newFr = newRow.querySelector('.bvsr-input-fr');
                        if (newFr) newFr.focus();
                    }
                }
            });
        }

        // ── Actions monter / descendre ──
        if (btnUp) {
            btnUp.addEventListener('click', function () {
                const prev = row.previousElementSibling;
                if (prev && prev.classList.contains('bvsr-rule-item')) {
                    rulesContainer.insertBefore(row, prev);
                    updateRulesState();
                    inputFr.focus();
                }
            });
        }

        if (btnDown) {
            btnDown.addEventListener('click', function () {
                const next = row.nextElementSibling;
                if (next && next.classList.contains('bvsr-rule-item')) {
                    rulesContainer.insertBefore(next, row);
                    updateRulesState();
                    inputFr.focus();
                }
            });
        }

        // ── Suppression ──
        if (btnDelete) {
            btnDelete.addEventListener('click', function () {
                const allItems = rulesContainer.querySelectorAll('.bvsr-rule-item');
                if (allItems.length <= 1) {
                    inputFr.value = '';
                    if (inputEn) inputEn.value = '';
                    inputFr.focus();
                } else {
                    row.remove();
                    updateRulesState();
                }
            });
        }

        // Insertion dans le DOM
        if (insertAfterElement && insertAfterElement.parentNode === rulesContainer) {
            insertAfterElement.after(row);
        } else {
            rulesContainer.appendChild(row);
        }

        updateRulesState();

        // Ré-instanciation des icônes Lucide sur la nouvelle ligne
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons({ root: row });
        }

        return row;
    }

    // ── Bouton "+ Ajouter une consigne" ──
    if (btnAddRule) {
        btnAddRule.addEventListener('click', function () {
            const newRow = addRuleItem('', '');
            if (newRow) {
                const newFr = newRow.querySelector('.bvsr-input-fr');
                if (newFr) newFr.focus();
            }
        });
    }

    // ── Bascule d'affichage des traductions anglaises ──
    if (toggleEn) {
        toggleEn.addEventListener('change', function () {
            if (rulesContainer) {
                if (toggleEn.checked) {
                    rulesContainer.classList.remove('is-en-hidden');
                } else {
                    rulesContainer.classList.add('is-en-hidden');
                }
            }
        });
    }

    // ── Ouverture / Fermeture de la Modale ──
    function openModal() {
        modal.classList.remove('u-d-none');
        modal.classList.add('is-active');
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('u-overflow-hidden');
    }

    function closeModal() {
        modal.classList.add('u-d-none');
        modal.classList.remove('is-active');
        modal.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('u-overflow-hidden');
    }

    const modalVehicleAvatarWrap = document.getElementById('modalVehicleAvatarWrap');
    const modalGeneralIconWrap = document.getElementById('modalGeneralIconWrap');
    const inputIsGeneral = document.getElementById('modal_is_general');
    const vehicleLabelGroup = document.getElementById('modal_vehicle_label_group');

    // ── Bouton "Modifier les règles générales" ──
    const editGeneralButton = document.querySelector('.btn-edit-general-rule');
    if (editGeneralButton) {
        editGeneralButton.addEventListener('click', function () {
            try {
                const dataRaw = editGeneralButton.getAttribute('data-rules') || "{}";
                const rulesObj = JSON.parse(dataRaw);

                if (modalTitle) modalTitle.textContent = "Modifier les Règles Générales de Sécurité";
                if (modalSubtitle) modalSubtitle.textContent = "Consignes universelles applicables à l'ensemble des tournages";

                if (modalVehicleAvatarWrap) modalVehicleAvatarWrap.classList.add('u-d-none');
                if (modalGeneralIconWrap) modalGeneralIconWrap.classList.remove('u-d-none');
                if (vehicleLabelGroup) vehicleLabelGroup.classList.add('u-d-none');

                if (inputIsGeneral) inputIsGeneral.value = "1";
                if (inputVehicleId) inputVehicleId.value = "";
                if (inputLabel) {
                    inputLabel.value = "Règles Générales";
                    inputLabel.removeAttribute('required');
                }

                if (rulesContainer) {
                    rulesContainer.innerHTML = "";
                }

                const rulesFr = rulesObj.rules_fr || [];
                const rulesEn = rulesObj.rules_en || [];
                const maxLen = Math.max(rulesFr.length, rulesEn.length);

                if (maxLen === 0) {
                    addRuleItem('', '');
                } else {
                    for (let i = 0; i < maxLen; i++) {
                        addRuleItem(rulesFr[i] || '', rulesEn[i] || '');
                    }
                }

                openModal();

                setTimeout(function () {
                    const firstInput = rulesContainer.querySelector('.bvsr-input-fr');
                    if (firstInput) firstInput.focus();
                }, 60);

            } catch (err) {
                console.error("Erreur chargement règles générales:", err);
            }
        });
    }

    // Boutons "Modifier" sur chaque carte du catalogue de véhicules
    const editButtons = document.querySelectorAll('.btn-edit-vehicle-rule');
    editButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            try {
                const vId = btn.getAttribute('data-id') || btn.getAttribute('data-key') || "";
                const dataRaw = btn.getAttribute('data-cat') || "{}";
                const cat = JSON.parse(dataRaw);

                const vehName = cat.name || cat.label || vId;
                const vehLabel = cat.label || cat.name || vId;
                const vehImg = cat.image || '/static/imgs/placeholders/vehicle.svg';

                if (modalTitle) modalTitle.textContent = "Modifier les Règles : " + vehName;
                if (modalSubtitle) modalSubtitle.textContent = "Véhicule Flotte — Protocole BVSR dynamique";
                if (modalVehicleImg) modalVehicleImg.src = vehImg;

                if (modalVehicleAvatarWrap) modalVehicleAvatarWrap.classList.remove('u-d-none');
                if (modalGeneralIconWrap) modalGeneralIconWrap.classList.add('u-d-none');
                if (vehicleLabelGroup) vehicleLabelGroup.classList.remove('u-d-none');

                if (inputIsGeneral) inputIsGeneral.value = "0";
                if (inputVehicleId) inputVehicleId.value = vId;
                if (inputLabel) {
                    inputLabel.value = vehLabel;
                    inputLabel.setAttribute('required', 'required');
                }

                if (rulesContainer) {
                    rulesContainer.innerHTML = "";
                }

                const rulesFr = cat.rules_fr || [];
                const rulesEn = cat.rules_en || [];
                const maxLen = Math.max(rulesFr.length, rulesEn.length);

                if (maxLen === 0) {
                    addRuleItem('', '');
                } else {
                    for (let i = 0; i < maxLen; i++) {
                        addRuleItem(rulesFr[i] || '', rulesEn[i] || '');
                    }
                }

                openModal();

                setTimeout(function () {
                    const firstInput = rulesContainer.querySelector('.bvsr-input-fr');
                    if (firstInput) {
                        firstInput.focus();
                    } else if (inputLabel) {
                        inputLabel.focus();
                    }
                }, 60);

            } catch (err) {
                console.error("Erreur chargement règle véhicule:", err);
            }
        });
    });

    // Fermeture par les boutons dédiés
    const closeButtons = modal.querySelectorAll('.btn-close-rule-modal, [data-modal-close]');
    closeButtons.forEach(function (btn) {
        btn.addEventListener('click', closeModal);
    });

    // Fermeture par clic sur l'arrière-plan
    modal.addEventListener('click', function (e) {
        if (e.target === modal) {
            closeModal();
        }
    });

    // Fermeture par touche Escape
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal.classList.contains('is-active')) {
            closeModal();
        }
    });

    // Validation formulaire avant soumission
    if (form) {
        form.addEventListener('submit', function (e) {
            const frInputs = rulesContainer.querySelectorAll('.bvsr-input-fr');
            let hasAtLeastOne = false;
            frInputs.forEach(function (inp) {
                if (inp.value.trim().length > 0) hasAtLeastOne = true;
            });

            if (!hasAtLeastOne) {
                e.preventDefault();
                alert("Veuillez renseigner au moins une consigne de sécurité.");
                const first = rulesContainer.querySelector('.bvsr-input-fr');
                if (first) first.focus();
            }
        });
    }
});
