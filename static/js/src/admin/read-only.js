/**
 * read-only.js — Mode lecture seule de l'ERP (rôle Associé).
 *
 * Actif uniquement lorsque <body> porte la classe `is-read-only`. Le serveur refuse déjà toute
 * écriture (garde globale + require_roles) : ce module se contente d'épurer l'interface en
 * masquant les points d'entrée d'écriture et en verrouillant les formulaires POST.
 */

// Formulaires POST qui restent utilisables (auth, calculs sans écriture, préférences perso).
const READ_ONLY_ALLOWED_FORM_ACTIONS = [
    '/admin/logout',
    '/admin/dev/switch-role',
    '/admin/tools/meeting-report',
    '/admin/mcp-connector',
    '/admin/api/projects/check-conflicts',
];

// Liens menant à des pages de création / édition (refusées côté serveur).
const READ_ONLY_BLOCKED_LINK = /\/(new|edit|duplicate|send|compose|quick-create)(\/|\?|#|$)|\/catalog\/update(\?|#|$)|\/edit\/(general|vehicle)/;

const READ_ONLY_MESSAGE = 'Accès en lecture seule : votre rôle Associé ne permet pas de modifier les données.';

function isReadOnlyMode() {
    return document.body && document.body.classList.contains('is-read-only');
}

function isAllowedForm(form) {
    if (form.hasAttribute('data-read-only-allowed')) return true;
    const action = form.getAttribute('action') || window.location.pathname;
    let path = action;
    try {
        path = new URL(action, window.location.href).pathname;
    } catch (e) { /* action relative non résoluble : on garde la valeur brute */ }
    return READ_ONLY_ALLOWED_FORM_ACTIONS.some((prefix) => path.startsWith(prefix));
}

function lockForm(form) {
    if (form.dataset.readOnlyLocked === '1') return;
    form.dataset.readOnlyLocked = '1';
    form.classList.add('is-read-only-locked');

    form.querySelectorAll('input, select, textarea, button').forEach((field) => {
        const type = (field.getAttribute('type') || '').toLowerCase();
        if (type === 'hidden') return;
        const isSubmit = field.tagName === 'BUTTON'
            ? (type === '' || type === 'submit')
            : type === 'submit';
        if (isSubmit) {
            field.classList.add('u-read-only-hidden');
        }
        field.disabled = true;
    });

    form.querySelectorAll('[contenteditable="true"]').forEach((el) => {
        el.setAttribute('contenteditable', 'false');
    });
}

function blockSubmit(event) {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if ((form.getAttribute('method') || 'get').toLowerCase() !== 'post') return;
    if (isAllowedForm(form)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (typeof window.showFlash === 'function') window.showFlash(READ_ONLY_MESSAGE, 'warning');
}

function initReadOnlyMode() {
    if (!isReadOnlyMode()) return;

    document.querySelectorAll('form').forEach((form) => {
        if ((form.getAttribute('method') || 'get').toLowerCase() !== 'post') return;
        if (isAllowedForm(form)) return;
        lockForm(form);
    });

    document.querySelectorAll('.admin-content a[href], .admin-header-actions a[href]').forEach((link) => {
        const href = link.getAttribute('href') || '';
        if (READ_ONLY_BLOCKED_LINK.test(href)) {
            link.classList.add('u-read-only-hidden');
            link.setAttribute('aria-hidden', 'true');
            link.setAttribute('tabindex', '-1');
        }
    });

    document.querySelectorAll('.admin-content [contenteditable="true"]').forEach((el) => {
        el.setAttribute('contenteditable', 'false');
    });

    if (!document.body.dataset.readOnlyBound) {
        document.body.dataset.readOnlyBound = '1';
        document.addEventListener('submit', blockSubmit, true);
    }
}

window.initReadOnlyMode = initReadOnlyMode;
