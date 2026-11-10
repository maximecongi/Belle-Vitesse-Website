/**
 * signer-invite.js — Modales d'invitation des signataires (CGL, BVSR, Annexe 3, BVRA) et
 * autocomplétion dans l'annuaire (contacts ERP + équipe Belle Vitesse).
 *
 * Gabarit : templates/admin/_signer_invite.html
 *   [data-signer-modal]                 overlay de la modale
 *   [data-signer-modal-open="<id>"]     bouton d'ouverture (ou ?invite=<id> dans l'URL)
 *   [data-signer-modal-close]           boutons de fermeture
 *   [data-signer-picker]                champ de recherche (data-search-url, data-project-id, data-fill)
 *   [data-signer-field="<clé>"]         champs remplis lors du choix d'un résultat
 *   [data-signer-role]                  sélecteur de rôle (« other » → [data-signer-role-custom])
 *
 * Événement émis sur la modale à l'ouverture : « signer-modal:open ».
 */
(function () {
    'use strict';

    if (document._signerInviteBound) return;
    document._signerInviteBound = true;

    const DEBOUNCE_MS = 180;
    // Champs d'identité : les modifier à la main après un choix détache la fiche contact liée.
    const IDENTITY_FIELDS = ['first_name', 'last_name'];

    function refreshIcons() {
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
    }

    function escapeHtml(str) {
        return String(str == null ? '' : str)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    /* ── Ouverture / fermeture ─────────────────────────────────────────── */

    function openModal(modal) {
        if (!modal) return;
        modal.classList.remove('u-d-none');
        modal.classList.add('is-active');
        refreshIcons();
        modal.dispatchEvent(new CustomEvent('signer-modal:open', { bubbles: true }));
        const search = modal.querySelector('[data-signer-search]');
        if (search) {
            try { search.focus({ preventScroll: true }); } catch (e) { search.focus(); }
        }
    }

    function closeModal(modal) {
        if (!modal) return;
        modal.classList.add('u-d-none');
        modal.classList.remove('is-active');
        modal.querySelectorAll('[data-signer-picker]').forEach(hideResults);
    }

    document.addEventListener('click', (e) => {
        const opener = e.target.closest('[data-signer-modal-open]');
        if (opener) {
            e.preventDefault();
            openModal(document.getElementById(opener.getAttribute('data-signer-modal-open')));
            return;
        }

        const closer = e.target.closest('[data-signer-modal-close]');
        if (closer) {
            e.preventDefault();
            closeModal(closer.closest('[data-signer-modal]'));
            return;
        }

        if (e.target.matches && e.target.matches('[data-signer-modal].is-active')) {
            closeModal(e.target);
            return;
        }

        const option = e.target.closest('[data-signer-option]');
        if (option) {
            e.preventDefault();
            const picker = option.closest('[data-signer-picker]');
            selectResult(picker, Number(option.getAttribute('data-index')));
            return;
        }

        const unlink = e.target.closest('[data-signer-unlink]');
        if (unlink) {
            e.preventDefault();
            const picker = unlink.closest('[data-signer-picker]');
            setLink(picker, null);
            return;
        }

        // Clic hors d'un sélecteur : on referme ses résultats
        document.querySelectorAll('[data-signer-picker]').forEach((picker) => {
            if (!picker.contains(e.target)) hideResults(picker);
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape' && e.key !== 'Esc') return;
        const picker = e.target.closest && e.target.closest('[data-signer-picker]');
        if (picker && picker._results && picker._results.length && !picker.querySelector('[data-signer-results]').classList.contains('u-d-none')) {
            hideResults(picker);
            return;
        }
        document.querySelectorAll('[data-signer-modal].is-active').forEach(closeModal);
    });

    /* ── Rôle « Autre fonction... » ────────────────────────────────────── */

    document.addEventListener('change', (e) => {
        const select = e.target.closest && e.target.closest('[data-signer-role]');
        if (!select) return;
        const form = select.closest('form');
        const group = form && form.querySelector('[data-signer-role-custom]');
        if (!group) return;
        const input = group.querySelector('input');
        const isOther = select.value === 'other';
        group.classList.toggle('u-d-none', !isOther);
        if (input) {
            input.required = isOther;
            if (isOther) input.focus();
        }
    });

    /* ── Autocomplétion ────────────────────────────────────────────────── */

    function scopeOf(picker) {
        return picker.closest('form') || picker.parentElement;
    }

    function field(scope, key) {
        return scope ? scope.querySelector(`[data-signer-field="${key}"]`) : null;
    }

    function hideResults(picker) {
        if (!picker) return;
        const list = picker.querySelector('[data-signer-results]');
        const input = picker.querySelector('[data-signer-search]');
        if (list) list.classList.add('u-d-none');
        if (input) {
            input.setAttribute('aria-expanded', 'false');
            input.removeAttribute('aria-activedescendant');
        }
        picker._active = -1;
    }

    function renderResults(picker, results, query) {
        const list = picker.querySelector('[data-signer-results]');
        const input = picker.querySelector('[data-signer-search]');
        if (!list) return;
        picker._results = results;
        picker._active = -1;

        if (!results.length) {
            list.innerHTML = query
                ? '<div class="signer-picker-empty">Aucun résultat — saisissez les coordonnées ci-dessous, le contact sera créé.</div>'
                : '';
            list.classList.toggle('u-d-none', !query);
            input.setAttribute('aria-expanded', query ? 'true' : 'false');
            return;
        }

        let html = '';
        let lastGroup = null;
        results.forEach((r, i) => {
            if (r.group !== lastGroup) {
                html += `<div class="signer-picker-group" role="presentation">${escapeHtml(r.group_label)}</div>`;
                lastGroup = r.group;
            }
            const meta = [r.project_role || r.job_title, r.company, r.mail].filter(Boolean).map(escapeHtml).join(' · ');
            html += `<div class="signer-picker-option" role="option" id="${list.id}-opt-${i}" data-signer-option data-index="${i}" aria-selected="false">`
                + `<span class="signer-picker-option-name">${escapeHtml(r.full_name)}`
                + (r.kind === 'user' ? ' <span class="signer-picker-tag">Équipe BV</span>' : '')
                + `</span>`
                + (meta ? `<span class="signer-picker-option-meta">${meta}</span>` : '')
                + `</div>`;
        });
        list.innerHTML = html;
        list.classList.remove('u-d-none');
        input.setAttribute('aria-expanded', 'true');
    }

    function highlight(picker, index) {
        const list = picker.querySelector('[data-signer-results]');
        const input = picker.querySelector('[data-signer-search]');
        const options = list.querySelectorAll('[data-signer-option]');
        if (!options.length) return;
        const next = (index + options.length) % options.length;
        options.forEach((o, i) => {
            const on = i === next;
            o.classList.toggle('is-active', on);
            o.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        picker._active = next;
        input.setAttribute('aria-activedescendant', options[next].id);
        if (typeof options[next].scrollIntoView === 'function') options[next].scrollIntoView({ block: 'nearest' });
    }

    function setLink(picker, result) {
        const scope = scopeOf(picker);
        const contactId = field(scope, 'contact_id');
        const userId = field(scope, 'user_id');
        if (contactId) contactId.value = result && result.kind === 'contact' ? result.id : '';
        if (userId) userId.value = result && result.kind === 'user' ? result.id : '';

        const linked = picker.querySelector('[data-signer-linked]');
        const label = picker.querySelector('[data-signer-linked-label]');
        if (!linked || !label) return;
        if (result) {
            label.textContent = (result.kind === 'user' ? 'Membre de l\'équipe BV : ' : 'Fiche contact liée : ') + result.full_name;
            linked.classList.remove('u-d-none');
            refreshIcons();
        } else {
            label.textContent = '';
            linked.classList.add('u-d-none');
        }
    }

    function selectResult(picker, index) {
        const result = picker && picker._results ? picker._results[index] : null;
        if (result) applyResult(picker, result);
    }

    function applyResult(picker, result) {
        if (!picker || !result) return;
        const scope = scopeOf(picker);
        const fill = picker.getAttribute('data-fill') || 'full';

        const assign = (key, value, { onlyIfValue = false } = {}) => {
            const el = field(scope, key);
            if (!el) return;
            if (onlyIfValue && !value) return;
            el.value = value || '';
            el.dispatchEvent(new Event('input', { bubbles: true }));
        };

        picker._filling = true;
        if (fill === 'email') {
            assign('mail', result.mail);
        } else {
            assign('first_name', result.first_name);
            assign('last_name', result.last_name);
            assign('mail', result.mail);
            assign('phone', result.phone);
            assign('job_title', result.job_title, { onlyIfValue: true });
            assign('company', result.company, { onlyIfValue: true });
            setLink(picker, result);
        }
        picker._filling = false;

        const input = picker.querySelector('[data-signer-search]');
        if (input) input.value = '';
        hideResults(picker);
        picker.dispatchEvent(new CustomEvent('signer:selected', { bubbles: true, detail: result }));
    }

    async function search(picker, query) {
        const url = picker.getAttribute('data-search-url');
        if (!url) return;
        if (picker._abort) picker._abort.abort();
        const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
        picker._abort = controller;

        const params = new URLSearchParams({ q: query });
        const projectId = picker.getAttribute('data-project-id');
        if (projectId) params.set('project_id', projectId);

        try {
            const resp = await fetch(`${url}?${params.toString()}`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' },
                credentials: 'same-origin',
                signal: controller ? controller.signal : undefined,
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            renderResults(picker, Array.isArray(data.results) ? data.results : [], query);
        } catch (err) {
            if (err && err.name === 'AbortError') return;
            console.error('Recherche de signataires indisponible', err);
            hideResults(picker);
        }
    }

    document.addEventListener('input', (e) => {
        const input = e.target.closest && e.target.closest('[data-signer-search]');
        if (input) {
            const picker = input.closest('[data-signer-picker]');
            clearTimeout(picker._timer);
            picker._timer = setTimeout(() => search(picker, input.value.trim()), DEBOUNCE_MS);
            return;
        }

        // Saisie manuelle du prénom / nom après un choix : ce n'est plus la même personne.
        const key = e.target.getAttribute && e.target.getAttribute('data-signer-field');
        if (key && IDENTITY_FIELDS.includes(key)) {
            const form = e.target.closest('form');
            const picker = form && form.querySelector('[data-signer-picker]');
            if (picker && !picker._filling) setLink(picker, null);
        }
    });

    document.addEventListener('focusin', (e) => {
        const input = e.target.closest && e.target.closest('[data-signer-search]');
        if (!input || input.value.trim()) return;
        // Champ vide : suggestions du projet (contacts du projet puis de sa production)
        search(input.closest('[data-signer-picker]'), '');
    });

    document.addEventListener('keydown', (e) => {
        const input = e.target.closest && e.target.closest('[data-signer-search]');
        if (!input) return;
        const picker = input.closest('[data-signer-picker]');
        const list = picker.querySelector('[data-signer-results]');
        const open = list && !list.classList.contains('u-d-none') && picker._results && picker._results.length;

        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            if (!open) return;
            e.preventDefault();
            highlight(picker, (picker._active == null ? -1 : picker._active) + (e.key === 'ArrowDown' ? 1 : -1));
        } else if (e.key === 'Enter') {
            // Entrée dans la recherche ne doit jamais soumettre l'invitation
            e.preventDefault();
            if (open) selectResult(picker, picker._active >= 0 ? picker._active : 0);
        }
    });

    /* ── Page « Nouvelles CGL » : signataire du projet choisi (waiver-search.js) ── */

    document.addEventListener('waiver:project-selected', (e) => {
        const form = e.target.closest && e.target.closest('form');
        const section = form && form.querySelector('[data-signer-section]');
        if (!section) return;
        const proj = e.detail;
        const picker = section.querySelector('[data-signer-picker]');

        section.classList.toggle('u-d-none', !proj);
        if (picker) picker.setAttribute('data-project-id', proj ? proj.id : '');
        ['first_name', 'last_name', 'mail', 'phone', 'job_title'].forEach((key) => {
            const el = field(form, key);
            if (el) el.value = '';
        });
        if (picker) setLink(picker, null);
        if (proj && proj.signer && picker) applyResult(picker, proj.signer);
        refreshIcons();
    });

    /* ── Ouverture automatique : ?invite=<id de modale> ─────────────────── */

    function stripInviteParam(value) {
        const url = new URL(value, window.location.origin);
        url.searchParams.delete('invite');
        return url.pathname + (url.search || '') + (url.hash || '');
    }

    function autoOpenFromUrl() {
        let target = null;
        try {
            target = new URLSearchParams(window.location.search).get('invite');
        } catch (e) { /* URL indisponible */ }
        if (!target) return;

        // Le paramètre ne sert qu'une fois : on l'ôte de l'URL et des retours post-envoi
        try {
            window.history.replaceState(window.history.state, '', stripInviteParam(window.location.href));
            document.querySelectorAll('input[name="return_to"]').forEach((input) => {
                if (input.value && input.value.indexOf('invite=') !== -1) input.value = stripInviteParam(input.value);
            });
        } catch (e) { /* history indisponible */ }

        const modal = document.getElementById(target);
        if (modal && modal.matches('[data-signer-modal]')) openModal(modal);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoOpenFromUrl);
    } else {
        autoOpenFromUrl();
    }

    window.SignerInvite = { open: openModal, close: closeModal };
})();
