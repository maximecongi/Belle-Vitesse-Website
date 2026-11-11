/**
 * pins.js — Pages épinglées (favoris) de l'ERP.
 *
 * - ⌘ + ; (Ctrl + ; hors Mac) sur n'importe quelle page : modale « Épingler la page »,
 *   pré-remplie avec <meta name="pin-label"> (bloc Jinja `pin_label`) ou, à défaut, le titre de la page.
 *   Si la page est déjà épinglée, la modale passe en mode édition (renommer / retirer).
 * - Sidebar (section « Épinglé(s) ») : renommer (crayon), retirer (croix), réordonner (glisser-déposer).
 * - Persistance serveur par utilisateur : /admin/api/pins (voir routes/admin/api.py).
 */
(function () {
    'use strict';

    const MODAL_ID = 'pinModal';
    const TITLE_SUFFIX = / - Admin Belle Vitesse$/;
    let editingPin = null;   // { id, label, url } lorsqu'on modifie une épingle existante
    let pendingUrl = null;   // URL à épingler (mode création)

    // ── Utilitaires ──────────────────────────────────────────────

    function container() { return document.querySelector('[data-pins]'); }

    function apiBase() {
        const c = container();
        return (c && c.dataset.pinsUrl) || '/admin/api/pins';
    }

    function csrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function notify(message, category) {
        if (typeof window.showFlash === 'function') window.showFlash(message, category || 'success');
    }

    /** URL normalisée d'une page : chemin + query, sans fragment ni `return_to` (même règle que le serveur). */
    function normalizeUrl(href) {
        let url;
        try { url = new URL(href, window.location.origin); } catch (e) { return null; }
        url.searchParams.delete('return_to');
        const query = url.searchParams.toString();
        return url.pathname + (query ? '?' + query : '');
    }

    function currentUrl() { return normalizeUrl(window.location.href); }

    function defaultLabel() {
        const meta = document.querySelector('meta[name="pin-label"]');
        const fromMeta = meta && meta.getAttribute('content').trim();
        if (fromMeta) return fromMeta;
        const fromTitle = document.title.replace(TITLE_SUFFIX, '').trim();
        if (fromTitle) return fromTitle;
        const h1 = document.querySelector('.admin-header-title h1');
        return h1 ? h1.textContent.trim() : '';
    }

    function readPins() {
        return Array.from(document.querySelectorAll('[data-pins-list] .admin-nav-pin')).map(el => ({
            id: Number(el.dataset.pinId),
            label: el.dataset.pinLabel,
            url: el.dataset.pinUrl,
        }));
    }

    function findPinByUrl(url) {
        return readPins().find(p => p.url === url) || null;
    }

    async function request(method, path, body) {
        const resp = await fetch(apiBase() + (path || ''), {
            method,
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken(),
            },
            body: body ? JSON.stringify(body) : undefined,
        });
        let data = null;
        try { data = await resp.json(); } catch (e) { /* réponse non JSON (session expirée…) */ }
        if (!resp.ok || !data || !data.success) {
            throw new Error((data && data.error) || 'Action impossible sur les favoris.');
        }
        if (Array.isArray(data.pins)) renderPins(data.pins);
        return data;
    }

    // ── Rendu de la section sidebar ──────────────────────────────

    function el(tag, className, attrs) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        Object.entries(attrs || {}).forEach(([k, v]) => node.setAttribute(k, v));
        return node;
    }

    function actionButton(attr, icon, label) {
        const btn = el('button', 'admin-nav-pin-action', { type: 'button', 'aria-label': label, [attr]: '' });
        btn.appendChild(el('i', '', { 'data-lucide': icon }));
        return btn;
    }

    function renderPins(pins) {
        const c = container();
        if (!c) return;
        const list = c.querySelector('[data-pins-list]');
        const title = c.querySelector('[data-pins-title]');
        list.replaceChildren();

        pins.forEach(pin => {
            const item = el('div', 'admin-nav-pin', {
                draggable: 'true',
                'data-pin-id': pin.id,
                'data-pin-label': pin.label,
                'data-pin-url': pin.url,
            });
            const link = el('a', 'admin-nav-item admin-nav-pin-link', { href: pin.url, title: pin.label });
            const labelWrap = el('span', 'admin-nav-label');
            labelWrap.appendChild(el('i', 'admin-nav-icon', { 'data-lucide': 'pin' }));
            const text = el('span', 'admin-nav-pin-text');
            text.textContent = pin.label;
            labelWrap.appendChild(text);
            link.appendChild(labelWrap);

            const actions = el('span', 'admin-nav-pin-actions');
            actions.appendChild(actionButton('data-pin-edit', 'pencil', 'Renommer le favori'));
            actions.appendChild(actionButton('data-pin-remove', 'x', 'Retirer le favori'));

            item.appendChild(link);
            item.appendChild(actions);
            list.appendChild(item);
        });

        title.textContent = pins.length > 1 ? 'Épinglés' : 'Épinglé';
        c.classList.toggle('u-d-none', pins.length === 0);
        if (typeof lucide !== 'undefined' && lucide.createIcons) lucide.createIcons({ root: c });
        markActivePin();
    }

    /** Surligne l'épingle correspondant exactement à la page courante. */
    function markActivePin() {
        const here = currentUrl();
        document.querySelectorAll('.admin-nav-pin').forEach(item => {
            const link = item.querySelector('.admin-nav-pin-link');
            if (link) link.classList.toggle('active', item.dataset.pinUrl === here);
        });
    }

    // ── Modale ───────────────────────────────────────────────────

    function modalParts() {
        const modal = document.getElementById(MODAL_ID);
        if (!modal) return null;
        return {
            modal,
            title: modal.querySelector('.admin-modal-title'),
            input: modal.querySelector('[data-pin-input]'),
            url: modal.querySelector('[data-pin-url]'),
            submit: modal.querySelector('[data-pin-submit]'),
            remove: modal.querySelector('[data-pin-modal-remove]'),
        };
    }

    function openPinModal(pin) {
        const parts = modalParts();
        if (!parts || !window.adminModal) return;
        editingPin = pin || null;
        pendingUrl = pin ? pin.url : currentUrl();

        parts.title.textContent = pin ? 'Modifier le favori' : 'Épingler la page';
        parts.submit.textContent = pin ? 'Enregistrer' : 'Épingler';
        parts.remove.classList.toggle('u-d-none', !pin);
        parts.input.value = pin ? pin.label : defaultLabel();
        parts.url.textContent = pendingUrl;

        window.adminModal.open(MODAL_ID);
        setTimeout(() => { parts.input.focus(); parts.input.select(); }, 30);
    }

    async function submitModal() {
        const parts = modalParts();
        const label = parts.input.value.trim();
        if (!label) { parts.input.focus(); return; }
        parts.submit.disabled = true;
        try {
            if (editingPin) {
                await request('PATCH', '/' + editingPin.id, { label });
                notify('Favori renommé');
            } else {
                await request('POST', '', { url: pendingUrl, label });
                notify('Page épinglée');
            }
            window.adminModal.close(MODAL_ID);
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            parts.submit.disabled = false;
        }
    }

    async function removePin(pinId) {
        try {
            await request('DELETE', '/' + pinId);
            notify('Favori retiré');
        } catch (err) {
            notify(err.message, 'error');
        }
    }

    // ── Glisser-déposer (réordonnancement) ───────────────────────

    let dragged = null;

    function dropTarget(list, y) {
        // Premier élément dont le milieu est sous le curseur : on insère avant lui
        return Array.from(list.querySelectorAll('.admin-nav-pin:not(.is-dragging)'))
            .find(item => {
                const box = item.getBoundingClientRect();
                return y < box.top + box.height / 2;
            }) || null;
    }

    function initDragAndDrop() {
        document.addEventListener('dragstart', e => {
            const item = e.target.closest && e.target.closest('.admin-nav-pin');
            if (!item) return;
            dragged = item;
            item.classList.add('is-dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', item.dataset.pinId);
        });

        document.addEventListener('dragover', e => {
            if (!dragged) return;
            const list = e.target.closest && e.target.closest('[data-pins-list]');
            if (!list) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            const before = dropTarget(list, e.clientY);
            if (before) list.insertBefore(dragged, before);
            else list.appendChild(dragged);
        });

        document.addEventListener('drop', e => {
            if (dragged && e.target.closest && e.target.closest('[data-pins-list]')) e.preventDefault();
        });

        document.addEventListener('dragend', () => {
            if (!dragged) return;
            dragged.classList.remove('is-dragging');
            dragged = null;
            const ids = readPins().map(p => p.id);
            request('POST', '/reorder', { ids }).catch(err => notify(err.message, 'error'));
        });
    }

    // ── Écouteurs ────────────────────────────────────────────────

    function isPinShortcut(e) {
        // e.key (caractère produit) plutôt que e.code : « ; » n'est pas sur la même touche en AZERTY et QWERTY
        return (e.metaKey || e.ctrlKey) && !e.altKey && e.key === ';';
    }

    if (!window._adminPinsAttached) {
        window._adminPinsAttached = true;

        document.addEventListener('keydown', e => {
            if (!isPinShortcut(e) || !document.getElementById(MODAL_ID)) return;
            e.preventDefault();
            const modal = document.getElementById(MODAL_ID);
            if (modal.classList.contains('is-active')) return;
            const here = currentUrl();
            if (!here || !here.startsWith('/admin')) return;
            openPinModal(findPinByUrl(here));
        });

        document.addEventListener('submit', e => {
            if (!e.target.matches('[data-pin-form]')) return;
            e.preventDefault();
            submitModal();
        });

        document.addEventListener('click', e => {
            const modalRemove = e.target.closest('[data-pin-modal-remove]');
            if (modalRemove && editingPin) {
                const id = editingPin.id;
                window.adminModal.close(MODAL_ID);
                removePin(id);
                return;
            }

            const action = e.target.closest('.admin-nav-pin-action');
            if (!action) return;
            e.preventDefault();
            e.stopPropagation();
            const item = action.closest('.admin-nav-pin');
            const pin = { id: Number(item.dataset.pinId), label: item.dataset.pinLabel, url: item.dataset.pinUrl };
            if (action.hasAttribute('data-pin-edit')) openPinModal(pin);
            else if (action.hasAttribute('data-pin-remove')) removePin(pin.id);
        });

        initDragAndDrop();

        document.addEventListener('swup:contentReplaced', markActivePin);
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', markActivePin);
        } else {
            markActivePin();
        }
    }

    window.adminPins = { open: openPinModal, render: renderPins };
})();
