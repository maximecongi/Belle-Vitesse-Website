/**
 * inspection-autosave.js — Sauvegarde automatique locale (localStorage) et résilience hors-ligne
 * pour les formulaires d'inspection (Check-out & Check-in).
 *
 * Évite la perte des données de saisie (jauges, kilomètres, cases à cocher, notes)
 * en cas de coupure 4G sur le terrain ou rechargement involontaire de la page.
 */

(function () {
    'use strict';

    const STORAGE_PREFIX = 'bv_autosave_';
    const MAX_DRAFT_AGE_HOURS = 48;

    function getStorageKey() {
        const path = window.location.pathname || 'inspection';
        return STORAGE_PREFIX + encodeURIComponent(path);
    }

    function formatTimeAgo(timestamp) {
        if (!timestamp) return 'récemment';
        const date = new Date(timestamp);
        const now = new Date();
        const diffMinutes = Math.floor((now - date) / (1000 * 60));

        if (diffMinutes < 1) return "à l'instant";
        if (diffMinutes < 60) return `il y a ${diffMinutes} min`;

        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const isToday = date.toDateString() === now.toDateString();

        if (isToday) {
            return `aujourd'hui à ${hours}:${minutes}`;
        }
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        return `le ${day}/${month} à ${hours}:${minutes}`;
    }

    function serializeForm(form) {
        const data = {};
        const elements = form.elements;

        for (let i = 0; i < elements.length; i++) {
            const el = elements[i];
            const name = el.name;

            // Ignorer les champs sans nom, les tokens CSRF et les fichiers (non sérialisables en texte)
            if (!name || name === 'csrf_token' || el.type === 'file' || el.type === 'password') {
                continue;
            }

            if (el.type === 'checkbox') {
                data[name] = el.checked;
            } else if (el.type === 'radio') {
                if (el.checked) {
                    data[name] = el.value;
                }
            } else {
                data[name] = el.value;
            }
        }

        return {
            timestamp: Date.now(),
            fields: data
        };
    }

    function saveDraft(form) {
        try {
            const serialized = serializeForm(form);
            // Si le formulaire est totalement vide, ne pas encombrer le localStorage
            const nonEmp = Object.keys(serialized.fields).filter(k => {
                const val = serialized.fields[k];
                return val !== '' && val !== false && val !== null;
            });
            if (nonEmp.length === 0) return;

            localStorage.setItem(getStorageKey(), JSON.stringify(serialized));
        } catch (e) {
            console.warn('Impossible de sauvegarder le brouillon dans localStorage :', e);
        }
    }

    function clearDraft() {
        try {
            localStorage.removeItem(getStorageKey());
        } catch (e) {
            // Ignorer silencieusement
        }
    }

    function restoreDraft(form, fields) {
        if (!form || !fields) return;

        Object.keys(fields).forEach(name => {
            const val = fields[name];
            const elements = form.querySelectorAll(`[name="${name}"]`);

            if (elements.length === 0) return;

            if (elements.length === 1 && elements[0].type === 'checkbox') {
                elements[0].checked = Boolean(val);
                elements[0].dispatchEvent(new Event('change', { bubbles: true }));
            } else if (elements[0].type === 'radio') {
                elements.forEach(radio => {
                    if (radio.value === String(val)) {
                        radio.checked = true;
                        radio.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                });
            } else {
                elements.forEach(el => {
                    el.value = val;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));

                    // Mettre à jour l'affichage des sélecteurs riches personnalisés si existants
                    const parentRich = el.closest('.rich-select');
                    if (parentRich) {
                        const triggerLabel = parentRich.querySelector('.badge-select-trigger span:first-child');
                        const selectedBtn = parentRich.querySelector(`.rich-select-option[data-id="${val}"]`);
                        if (triggerLabel && selectedBtn) {
                            const nameAttr = selectedBtn.getAttribute('data-name');
                            if (nameAttr) triggerLabel.textContent = nameAttr;
                        }
                    }
                });
            }
        });

        // Déclencher un événement personnalisé signalant la restauration
        form.dispatchEvent(new CustomEvent('inspection-draft-restored', { bubbles: true }));
    }

    function initAutosave() {
        const form = document.getElementById('inspectionForm');
        if (!form) return;

        const storageKey = getStorageKey();
        let rawDraft = null;

        try {
            rawDraft = localStorage.getItem(storageKey);
        } catch (e) {
            return;
        }

        if (rawDraft) {
            try {
                const draft = JSON.parse(rawDraft);
                const ageHours = (Date.now() - (draft.timestamp || 0)) / (1000 * 60 * 60);

                if (ageHours <= MAX_DRAFT_AGE_HOURS && draft.fields && Object.keys(draft.fields).length > 0) {
                    showAutosaveBanner(form, draft);
                } else {
                    clearDraft();
                }
            } catch (err) {
                clearDraft();
            }
        }

        // Écouter les modifications avec debounce de 400ms
        let debounceTimer = null;
        function onFieldInput() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                saveDraft(form);
            }, 400);
        }

        form.addEventListener('input', onFieldInput);
        form.addEventListener('change', onFieldInput);

        // Nettoyer le brouillon lors de la soumission validée
        form.addEventListener('submit', function () {
            clearDraft();
        });
    }

    function showAutosaveBanner(form, draft) {
        // Supprimer toute bannière préexistante
        const existing = form.querySelector('.inspection-autosave-banner');
        if (existing) existing.remove();

        const banner = document.createElement('div');
        banner.className = 'inspection-autosave-banner u-mb-4';
        banner.id = 'autosaveBanner';

        const formattedDate = formatTimeAgo(draft.timestamp);

        banner.innerHTML = `
            <div class="inspection-autosave-content">
                <span class="inspection-autosave-icon"><i data-lucide="history"></i></span>
                <div class="inspection-autosave-text">
                    <strong class="inspection-autosave-title">Brouillon local non validé détecté</strong>
                    <div class="inspection-autosave-desc">Une saisie précédente a été conservée (${formattedDate}). Souhaitez-vous la restaurer ?</div>
                </div>
            </div>
            <div class="inspection-autosave-actions">
                <button type="button" class="admin-btn admin-btn-sm admin-btn-primary" id="btnRestoreAutosave">
                    <i data-lucide="rotate-ccw"></i> Restaurer la saisie
                </button>
                <button type="button" class="admin-btn admin-btn-sm admin-btn-secondary" id="btnDiscardAutosave">
                    Ignorer
                </button>
            </div>
        `;

        form.insertBefore(banner, form.firstChild);

        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }

        const btnRestore = banner.querySelector('#btnRestoreAutosave');
        const btnDiscard = banner.querySelector('#btnDiscardAutosave');

        if (btnRestore) {
            btnRestore.addEventListener('click', function () {
                restoreDraft(form, draft.fields);
                banner.className = 'inspection-autosave-banner is-restored u-mb-4';
                banner.innerHTML = `
                    <div class="inspection-autosave-content">
                        <span class="inspection-autosave-icon"><i data-lucide="circle-check"></i></span>
                        <div class="inspection-autosave-text">
                            <strong class="inspection-autosave-title">Données du brouillon restaurées avec succès</strong>
                        </div>
                    </div>
                `;
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
                setTimeout(() => {
                    banner.remove();
                }, 3500);
            });
        }

        if (btnDiscard) {
            btnDiscard.addEventListener('click', function () {
                clearDraft();
                banner.remove();
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAutosave);
    } else {
        initAutosave();
    }
})();
