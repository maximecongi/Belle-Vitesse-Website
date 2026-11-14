/**
 * project-autosave.js — Sauvegarde automatique locale du formulaire projet
 * (création, modification, duplication).
 *
 * Le formulaire projet ne contient pas de fichiers : le brouillon est stocké en JSON dans
 * localStorage (lecture synchrone). Cela permet, lors d'une restauration, de réinjecter les
 * valeurs AVANT l'initialisation des widgets (sélecteur de dates, lieux, select2) qui lisent
 * les champs au chargement — d'où la restauration par rechargement de page.
 *
 * Ce module doit être chargé AVANT project_datepicker.js / project-form.js / project-locations.js.
 */
(function () {
    'use strict';

    const FORM_ID = 'projectMainForm';
    const KEY_PREFIX = 'bv-draft:project:';
    const RESTORE_FLAG = 'bv-project-draft-restore';
    const RESTORED_FLAG = 'bv-project-draft-restored';
    const PENDING_FLAG = 'bv-project-draft-pending';
    const MAX_AGE_MS = 14 * 24 * 3600 * 1000; // brouillons conservés 14 jours

    function safeGet(storage, key) {
        try { return storage.getItem(key); } catch (e) { return null; }
    }
    function safeSet(storage, key, value) {
        try { storage.setItem(key, value); } catch (e) { /* stockage indisponible */ }
    }
    function safeRemove(storage, key) {
        try { storage.removeItem(key); } catch (e) { /* stockage indisponible */ }
    }

    // Fiche projet atteinte après l'envoi = enregistrement réussi
    function isSavedProjectPage(path) {
        return /\/projects\/\d+\/?$/.test(path || '');
    }

    function getStorageKey() {
        const path = window.location.pathname;
        let m = path.match(/\/projects\/(\d+)\/edit/);
        if (m) return KEY_PREFIX + 'edit:' + m[1];
        m = path.match(/\/projects\/(\d+)\/duplicate/);
        if (m) return KEY_PREFIX + 'duplicate:' + m[1];
        return KEY_PREFIX + 'new';
    }

    function serialize(form) {
        const fields = {};
        Array.from(form.elements).forEach(el => {
            const name = el.name;
            if (!name || name === 'csrf_token' || el.type === 'file' || el.type === 'submit' || el.type === 'button') return;
            if (el.type === 'checkbox') {
                if (!Array.isArray(fields[name])) fields[name] = [];
                if (el.checked) fields[name].push(el.value);
            } else if (el.type === 'radio') {
                if (el.checked) fields[name] = el.value;
            } else if (el.tagName === 'SELECT' && el.multiple) {
                fields[name] = Array.from(el.selectedOptions).map(o => o.value);
            } else {
                fields[name] = el.value;
            }
        });
        return fields;
    }

    function apply(form, fields) {
        Object.keys(fields).forEach(name => {
            const value = fields[name];
            form.querySelectorAll(`[name="${CSS.escape(name)}"]`).forEach(el => {
                if (el.type === 'checkbox') {
                    el.checked = Array.isArray(value) && value.includes(el.value);
                } else if (el.type === 'radio') {
                    el.checked = el.value === value;
                } else if (el.tagName === 'SELECT' && el.multiple && Array.isArray(value)) {
                    Array.from(el.options).forEach(o => { o.selected = value.includes(o.value); });
                } else if (typeof value === 'string') {
                    el.value = value;
                }
            });
        });
    }

    function readDraft(key) {
        const raw = safeGet(localStorage, key);
        if (!raw) return null;
        try {
            const draft = JSON.parse(raw);
            if (!draft || !draft.fields || (Date.now() - (draft.timestamp || 0)) > MAX_AGE_MS) {
                safeRemove(localStorage, key);
                return null;
            }
            return draft;
        } catch (e) {
            safeRemove(localStorage, key);
            return null;
        }
    }

    function formatTimeAgo(ts) {
        if (window.BvDraftStore && typeof window.BvDraftStore.formatTimeAgo === 'function') {
            return window.BvDraftStore.formatTimeAgo(ts);
        }
        return new Date(ts).toLocaleString('fr-FR');
    }

    function showBanner(form, options) {
        if (typeof window.createAdminBanner !== 'function') return null;
        const banner = window.createAdminBanner(options);
        form.parentNode.insertBefore(banner, form);
        if (window.lucide && typeof window.lucide.createIcons === 'function') window.lucide.createIcons();
        return banner;
    }

    // ── 1. Nettoyage après une soumission RÉUSSIE uniquement ──
    // Un enregistrement réussi redirige toujours vers la fiche du projet (/admin/projects/<id>).
    // Toute autre page (formulaire réaffiché après une erreur, connexion expirée, page d'erreur…)
    // conserve le brouillon : il sera proposé à la restauration au retour sur le formulaire.
    const pendingKey = safeGet(sessionStorage, PENDING_FLAG);
    const form = document.getElementById(FORM_ID);
    if (pendingKey) {
        safeRemove(sessionStorage, PENDING_FLAG);
        if (!form && isSavedProjectPage(window.location.pathname)) safeRemove(localStorage, pendingKey);
    }
    if (!form) return;

    const storageKey = getStorageKey();

    // ── 2. Restauration demandée : réinjection synchrone avant l'initialisation des widgets ──
    if (safeGet(sessionStorage, RESTORE_FLAG) === storageKey) {
        safeRemove(sessionStorage, RESTORE_FLAG);
        const draft = readDraft(storageKey);
        if (draft) {
            apply(form, draft.fields);
            safeSet(sessionStorage, RESTORED_FLAG, '1');
        }
    }

    function init() {
        let baseline = null;
        let lastSaved = null;
        let timer = null;

        if (safeGet(sessionStorage, RESTORED_FLAG)) {
            safeRemove(sessionStorage, RESTORED_FLAG);
            const ok = showBanner(form, {
                variant: 'success',
                icon: 'circle-check',
                id: 'projectAutosaveBanner',
                title: 'Saisie du projet restaurée'
            });
            if (ok) setTimeout(() => ok.remove(), 3500);
        } else {
            const draft = readDraft(storageKey);
            if (draft) {
                const actionsHtml = `
                    <button type="button" class="admin-btn admin-btn-sm admin-btn-primary" data-project-draft="restore">
                        <i data-lucide="rotate-ccw"></i> Restaurer la saisie
                    </button>
                    <button type="button" class="admin-btn admin-btn-sm admin-btn-secondary" data-project-draft="discard">
                        Ignorer
                    </button>`;
                const banner = showBanner(form, {
                    variant: 'warning',
                    icon: 'history',
                    id: 'projectAutosaveBanner',
                    title: 'Brouillon de projet non enregistré',
                    desc: `Une saisie non enregistrée a été conservée (${formatTimeAgo(draft.timestamp)}). Souhaitez-vous la restaurer ?`,
                    actionsHtml: actionsHtml
                });
                if (banner) {
                    banner.addEventListener('click', e => {
                        const action = e.target.closest('[data-project-draft]');
                        if (!action) return;
                        if (action.dataset.projectDraft === 'restore') {
                            safeSet(sessionStorage, RESTORE_FLAG, storageKey);
                            window.location.reload();
                        } else {
                            safeRemove(localStorage, storageKey);
                            banner.remove();
                        }
                    });
                }
            }
        }

        function saveIfChanged() {
            const current = JSON.stringify(serialize(form));
            if (baseline === null || current === lastSaved) return;
            if (current === baseline) {
                // Retour à l'état initial : aucun brouillon à conserver
                safeRemove(localStorage, storageKey);
            } else {
                safeSet(localStorage, storageKey, JSON.stringify({
                    timestamp: Date.now(),
                    fields: JSON.parse(current)
                }));
            }
            lastSaved = current;
        }

        function scheduleSave() {
            clearTimeout(timer);
            timer = setTimeout(saveIfChanged, 600);
        }

        // Référence prise après l'initialisation des widgets (qui peuvent normaliser les champs)
        setTimeout(() => {
            baseline = JSON.stringify(serialize(form));
            lastSaved = baseline;
        }, 800);

        ['input', 'change', 'click'].forEach(evt => form.addEventListener(evt, scheduleSave));
        // Les widgets (dates, lieux, select2) modifient des champs cachés sans événement natif
        setInterval(saveIfChanged, 3000);

        form.addEventListener('submit', () => {
            saveIfChanged();
            safeSet(sessionStorage, PENDING_FLAG, storageKey);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
