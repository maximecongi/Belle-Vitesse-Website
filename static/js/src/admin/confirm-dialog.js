/**
 * confirm-dialog.js — Modales génériques et confirmations d'actions de l'ERP.
 *
 * 1. Modales génériques (macro `admin_modal`) :
 *    - `[data-modal-open="<id>"]`  ouvre la modale <id>
 *    - `[data-modal-close="<id>"]` ferme la modale <id>
 *    - clic sur le voile ou touche Échap : fermeture
 *    - événements `admin-modal:open` / `admin-modal:close` émis sur la modale
 *
 * 2. Confirmations (remplacent les `confirm()` natifs et les `onsubmit` inline) :
 *    - `<form data-confirm="Message">` : confirmation avant soumission
 *    - `<button data-confirm="Message">` / `<a data-confirm="Message">` : confirmation avant l'action
 *    - options : `data-confirm-title`, `data-confirm-label` (libellé du bouton),
 *      `data-confirm-variant` ("danger" par défaut, ou "primary" pour une action non destructive)
 */
(function () {
    'use strict';

    const CONFIRM_MODAL_ID = 'confirmModal';
    let pendingAction = null;
    let pendingCancel = null;
    let lastFocused = null;

    function openModal(id) {
        const modal = document.getElementById(id);
        if (!modal) return null;
        lastFocused = document.activeElement;
        modal.classList.add('is-active');
        modal.setAttribute('aria-hidden', 'false');
        modal.dispatchEvent(new CustomEvent('admin-modal:open', { bubbles: true }));
        return modal;
    }

    function closeModal(id) {
        const modal = typeof id === 'string' ? document.getElementById(id) : id;
        if (!modal || !modal.classList.contains('is-active')) return;
        modal.classList.remove('is-active');
        modal.setAttribute('aria-hidden', 'true');
        modal.dispatchEvent(new CustomEvent('admin-modal:close', { bubbles: true }));
        if (modal.id === CONFIRM_MODAL_ID) {
            const cancel = pendingCancel;
            pendingAction = null;
            pendingCancel = null;
            if (cancel) cancel();
        }
        if (lastFocused && typeof lastFocused.focus === 'function') lastFocused.focus();
    }

    function askConfirmation(trigger, onAccept, onCancel) {
        const modal = document.getElementById(CONFIRM_MODAL_ID);
        if (!modal) {
            // Repli : la modale n'est pas présente (page autonome)
            if (window.confirm(trigger.dataset.confirm)) onAccept();
            else if (onCancel) onCancel();
            return;
        }
        const title = modal.querySelector('.admin-modal-title');
        const message = modal.querySelector('[data-confirm-message]');
        const accept = modal.querySelector('[data-confirm-accept]');
        const variant = trigger.dataset.confirmVariant || 'danger';

        if (title) title.textContent = trigger.dataset.confirmTitle || 'Confirmer l’action';
        if (message) message.textContent = trigger.dataset.confirm;
        if (accept) {
            accept.textContent = trigger.dataset.confirmLabel || (variant === 'danger' ? 'Supprimer' : 'Confirmer');
            accept.classList.toggle('admin-btn-danger', variant === 'danger');
            accept.classList.toggle('admin-btn-primary', variant !== 'danger');
        }
        pendingAction = onAccept;
        pendingCancel = onCancel || null;
        openModal(CONFIRM_MODAL_ID);
        if (accept) accept.focus();
    }

    // ── Ouverture / fermeture génériques ──
    document.addEventListener('click', function (e) {
        const opener = e.target.closest('[data-modal-open]');
        if (opener) {
            e.preventDefault();
            openModal(opener.dataset.modalOpen);
            return;
        }
        const closer = e.target.closest('[data-modal-close]');
        if (closer) {
            e.preventDefault();
            closeModal(closer.dataset.modalClose);
            return;
        }
        // Clic sur le voile (en dehors du conteneur)
        if (e.target.classList && e.target.classList.contains('admin-modal-overlay') && e.target.hasAttribute('aria-modal')) {
            closeModal(e.target);
            return;
        }
        if (e.target.closest('[data-confirm-accept]')) {
            const action = pendingAction;
            pendingCancel = null;
            closeModal(CONFIRM_MODAL_ID);
            if (action) action();
            return;
        }

        // Boutons et liens soumis à confirmation
        const trigger = e.target.closest('button[data-confirm], a[data-confirm], input[type="submit"][data-confirm]');
        if (trigger && !trigger.disabled) {
            e.preventDefault();
            e.stopPropagation();
            askConfirmation(trigger, function () {
                if (trigger.tagName === 'A') {
                    window.location.href = trigger.href;
                } else if (trigger.form) {
                    trigger.form.dataset.confirmed = 'true';
                    if (trigger.form.requestSubmit) trigger.form.requestSubmit(trigger);
                    else trigger.form.submit();
                }
            });
        }
    }, true);

    // Formulaires soumis à confirmation
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!(form instanceof HTMLFormElement)) return;
        if (form.dataset.confirmed === 'true') {
            delete form.dataset.confirmed;
            return;
        }
        if (!form.dataset.confirm) return;
        e.preventDefault();
        const submitter = e.submitter || null;
        askConfirmation(form, function () {
            form.dataset.confirmed = 'true';
            if (form.requestSubmit) form.requestSubmit(submitter || undefined);
            else form.submit();
        });
    }, true);

    // Retour visuel pendant une soumission longue : <form data-submit-loading="Libellé…">
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!(form instanceof HTMLFormElement) || e.defaultPrevented || !form.dataset.submitLoading) return;
        const btn = e.submitter || form.querySelector('button[type="submit"]');
        if (!btn) return;
        btn.disabled = true;
        btn.classList.add('btn-disabled');
        btn.textContent = form.dataset.submitLoading;
    });

    // Image de repli (remplace onerror inline) : <img data-fallback-src="...">
    // L'événement « error » ne remonte pas : écoute en phase de capture.
    function applyImageFallback(img) {
        if (!(img instanceof HTMLImageElement) || !img.dataset.fallbackSrc || img.dataset.fallbackApplied) return;
        img.dataset.fallbackApplied = '1';
        img.src = img.dataset.fallbackSrc;
        img.classList.add('vehicle-avatar-fallback');
    }
    document.addEventListener('error', e => applyImageFallback(e.target), true);
    // Images déjà en échec avant le chargement de ce script
    document.querySelectorAll('img[data-fallback-src]').forEach(img => {
        if (img.complete && img.naturalWidth === 0 && img.getAttribute('src')) applyImageFallback(img);
    });

    // Petits comportements déclaratifs (remplacent les handlers inline)
    document.addEventListener('click', function (e) {
        const dismiss = e.target.closest('[data-dismiss="banner"]');
        if (dismiss) {
            const banner = dismiss.closest('.admin-banner');
            if (banner) banner.remove();
        }
    });
    document.addEventListener('input', function (e) {
        const el = e.target;
        if (el && el.dataset && el.dataset.sanitize === 'phone') {
            const cleaned = el.value.replace(/[\s.()[\]]/g, '');
            if (cleaned !== el.value) el.value = cleaned;
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        document.querySelectorAll('.admin-modal-overlay.is-active[aria-modal]').forEach(function (m) {
            closeModal(m);
        });
    });

    /**
     * Confirmation programmatique (remplace window.confirm dans les modules JS).
     * @param {string} message
     * @param {{title?: string, label?: string, variant?: 'danger'|'primary'}} [options]
     * @returns {Promise<boolean>}
     */
    function adminConfirm(message, options) {
        const opts = options || {};
        const pseudoTrigger = {
            dataset: {
                confirm: message,
                confirmTitle: opts.title || '',
                confirmLabel: opts.label || '',
                confirmVariant: opts.variant || 'danger'
            }
        };
        return new Promise(resolve => {
            askConfirmation(pseudoTrigger, () => resolve(true), () => resolve(false));
        });
    }

    window.adminModal = { open: openModal, close: closeModal, confirm: askConfirmation };
    window.adminConfirm = adminConfirm;
})();
