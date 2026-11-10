/**
 * project-reports.js — Rapports d'équipe de la fiche projet.
 *  - Brouillons automatiques (création et modification) conservés sur l'appareil
 *  - Publication / modification / suppression / restauration sans rechargement (AJAX)
 *  - Annulation d'une suppression, corbeille administrateur
 *  - Liste + lecture : liste regroupée par jour à gauche, rapport sélectionné à droite (hauteur fixe),
 *    navigation au clavier (↑ ↓), affichage « liste puis lecture » sur mobile
 *  - Filtres (texte, catégorie, jour) et lien d'export PDF synchronisé
 *  - Compte à rebours de la fenêtre de modification (3 h)
 *  - Aperçu et limite des photos jointes
 * Markup : templates/admin/project_detail.html, _report_item.html, _report_fields.html.
 */
(function () {
    'use strict';

    const DRAFT_PREFIX = 'bv_report_draft:';
    const DRAFT_MAX_AGE_MS = 7 * 24 * 3600 * 1000;
    const DRAFT_DEBOUNCE_MS = 600;
    const UNDO_DELAY_MS = 8000;

    // ── Utilitaires ─────────────────────────────────────────────

    function storageGet(key) {
        try {
            const raw = window.localStorage.getItem(key);
            return raw ? JSON.parse(raw) : null;
        } catch (e) {
            return null;
        }
    }

    function storageSet(key, value) {
        try {
            window.localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (e) {
            return false;
        }
    }

    function storageRemove(key) {
        try {
            window.localStorage.removeItem(key);
        } catch (e) {
            // stockage indisponible (navigation privée…) : rien à faire
        }
    }

    function refreshIcons() {
        if (window.lucide && typeof window.lucide.createIcons === 'function') window.lucide.createIcons();
    }

    function notify(message, category) {
        if (typeof window.showFlash === 'function') window.showFlash(message, category || 'success');
    }

    function htmlToElement(html) {
        const tpl = document.createElement('template');
        tpl.innerHTML = (html || '').trim();
        return tpl.content.firstElementChild;
    }

    function editorApi(form) {
        const wrapper = form && form.querySelector('.notion-wysiwyg-wrapper');
        if (!wrapper) return null;
        return wrapper._notionEditor || (typeof window.initNotionEditor === 'function' ? window.initNotionEditor(wrapper) : null);
    }

    function formatAgo(ts) {
        const minutes = Math.round((Date.now() - ts) / 60000);
        if (minutes < 1) return "à l'instant";
        if (minutes < 60) return `il y a ${minutes} min`;
        const hours = Math.round(minutes / 60);
        if (hours < 24) return `il y a ${hours} h`;
        return `il y a ${Math.round(hours / 24)} j`;
    }

    // ── Brouillons ──────────────────────────────────────────────

    function draftKey(form) {
        return DRAFT_PREFIX + form.dataset.draftKey;
    }

    // Version du rapport au moment où le brouillon a été pris (édition uniquement)
    function reportVersion(form) {
        const item = form.closest('.project-report-item');
        return item ? item.dataset.updatedAt || '' : '';
    }

    function readFormState(form) {
        const api = editorApi(form);
        const title = form.querySelector('input[name="title"]');
        const category = form.querySelector('input[name="category"]:checked');
        const day = form.querySelector('select[name="shoot_day"]');
        return {
            title: title ? title.value : '',
            html: api ? api.getHTML() : '',
            empty: api ? api.isEmpty() : true,
            category: category ? category.value : '',
            day: day ? day.value : '',
        };
    }

    function saveDraft(form) {
        if (!form.dataset.draftKey) return;
        const state = readFormState(form);
        if (!state.title.trim() && state.empty) {
            storageRemove(draftKey(form));
            return;
        }
        storageSet(draftKey(form), {
            title: state.title,
            html: state.html,
            category: state.category,
            day: state.day,
            version: reportVersion(form),
            savedAt: Date.now(),
        });
    }

    function clearDraft(form) {
        if (form.dataset.draftKey) storageRemove(draftKey(form));
        hideDraftBanner(form);
    }

    function hideDraftBanner(form) {
        const banner = form.querySelector('[data-draft-banner]');
        if (banner) {
            banner.classList.add('is-hidden');
            banner.innerHTML = '';
        }
    }

    function showDraftBanner(form, savedAt) {
        const banner = form.querySelector('[data-draft-banner]');
        if (!banner) return;
        banner.innerHTML = '';
        const text = document.createElement('span');
        text.textContent = `Brouillon restauré (enregistré ${formatAgo(savedAt)}). Les photos ne sont pas conservées dans les brouillons.`;
        const discard = document.createElement('button');
        discard.type = 'button';
        discard.className = 'report-draft-discard';
        discard.textContent = 'Effacer le brouillon';
        discard.addEventListener('click', () => {
            clearDraft(form);
            resetForm(form);
        });
        banner.append(text, discard);
        banner.classList.remove('is-hidden');
    }

    function restoreDraft(form) {
        if (!form.dataset.draftKey) return false;
        const draft = storageGet(draftKey(form));
        if (!draft) return false;
        const expired = Date.now() - (draft.savedAt || 0) > DRAFT_MAX_AGE_MS;
        // Brouillon d'édition périmé si le rapport a été modifié entre-temps
        const outdated = form.dataset.reportForm === 'edit' && draft.version !== reportVersion(form);
        if (expired || outdated) {
            storageRemove(draftKey(form));
            return false;
        }
        const title = form.querySelector('input[name="title"]');
        if (title) title.value = draft.title || '';
        const api = editorApi(form);
        if (api) api.setContent(draft.html || '');
        if (draft.category) {
            const radio = form.querySelector(`input[name="category"][value="${CSS.escape(draft.category)}"]`);
            if (radio) radio.checked = true;
        }
        const day = form.querySelector('select[name="shoot_day"]');
        if (day && [...day.options].some((o) => o.value === draft.day)) day.value = draft.day || '';
        showDraftBanner(form, draft.savedAt || Date.now());
        return true;
    }

    function bindDraftAutosave(form) {
        if (form._draftBound) return;
        form._draftBound = true;
        let timer = null;
        const schedule = () => {
            clearTimeout(timer);
            timer = setTimeout(() => saveDraft(form), DRAFT_DEBOUNCE_MS);
        };
        form.addEventListener('input', schedule);
        form.addEventListener('change', schedule);
        form.addEventListener('notion-change', schedule);
        // Dernière chance avant de quitter la page
        window.addEventListener('pagehide', () => {
            if (timer) saveDraft(form);
        });
    }

    // ── Formulaires ─────────────────────────────────────────────

    function resetForm(form) {
        form.reset();
        const api = editorApi(form);
        if (api) api.reset();
        clearPhotoPreview(form);
        setFormError(form, '');
    }

    function setFormError(form, message) {
        const box = form.querySelector('[data-form-error]');
        if (!box) {
            if (message) notify(message, 'error');
            return;
        }
        box.textContent = message || '';
        box.classList.toggle('is-hidden', !message);
    }

    function setBusy(form, busy) {
        const btn = form.querySelector('button[type="submit"]');
        if (!btn) return;
        btn.disabled = busy;
        btn.classList.toggle('is-loading', busy);
        btn.textContent = busy ? 'Envoi…' : (btn.dataset.submitLabel || btn.textContent);
    }

    // Attend la fin de l'optimisation des photos sélectionnées avant l'envoi
    function waitForCompression(form) {
        const pending = [...form.querySelectorAll('.report-photos-input')]
            .flatMap((input) => (input._reportPhotos || []).map((p) => p.ready));
        if (!pending.length) return Promise.resolve();
        return Promise.race([
            Promise.all(pending),
            new Promise((resolve) => setTimeout(resolve, 20000)),
        ]);
    }

    // Corps de la requête : les photos envoyées sont la liste cumulée (pas la dernière sélection du champ)
    function buildFormData(form) {
        const data = new FormData(form);
        form.querySelectorAll('.report-photos-input').forEach((input) => {
            if (!input._reportPhotos) return;
            data.delete(input.name);
            input._reportPhotos.forEach((p) => data.append(input.name, p.file, p.file.name));
        });
        return data;
    }

    async function postForm(form, url) {
        const response = await fetch(url || form.action, {
            method: 'POST',
            body: buildFormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' },
            credentials: 'same-origin',
        });
        let data = {};
        try {
            data = await response.json();
        } catch (e) {
            data = {};
        }
        if (!response.ok || data.status !== 'success') {
            const error = new Error(data.message || `Erreur ${response.status}`);
            error.isServer = true;
            throw error;
        }
        return data;
    }

    function networkMessage(err) {
        return err && err.isServer
            ? err.message
            : 'Connexion impossible. Votre brouillon est conservé sur cet appareil : réessayez dès que le réseau revient.';
    }

    // ── Liste + lecture ─────────────────────────────────────────

    function root() {
        return document.querySelector('[data-reports-root]');
    }

    function find(selector) {
        const r = root();
        return r && r.querySelector(selector);
    }

    function timeline() {
        return find('[data-reports-timeline]');
    }

    function createForm() {
        return find('[data-report-form="create"]');
    }

    function isComposeOpen() {
        const form = createForm();
        return Boolean(form && !form.hidden);
    }

    function allItems() {
        const tl = timeline();
        return tl ? [...tl.querySelectorAll('.project-report-item')] : [];
    }

    function rowFor(id) {
        return find(`[data-report-row="${id}"]`);
    }

    function visibleRows() {
        const box = find('[data-reports-groups]');
        return box ? [...box.querySelectorAll('[data-report-row]')].filter((row) => !row.hidden) : [];
    }

    function selectedId() {
        const r = root();
        return (r && r._selectedId) || '';
    }

    // Bloc liste + lecture visible s'il y a des rapports (ou un rapport en cours de rédaction)
    function updateVisibility() {
        const r = root();
        if (!r) return;
        const count = allItems().length;
        const compose = isComposeOpen();
        const browser = r.querySelector('[data-reports-browser]');
        const empty = r.querySelector('[data-reports-empty]');
        const toolbar = r.querySelector('[data-reports-toolbar]');
        if (browser) browser.hidden = count === 0 && !compose;
        if (empty) empty.hidden = count > 0 || compose;
        if (toolbar) toolbar.hidden = count === 0;
    }

    function updateCount(count) {
        const r = root();
        if (!r || typeof count !== 'number') return;
        const badge = r.querySelector('[data-reports-count-badge]');
        if (badge) {
            const label = badge.querySelector('.badge-pill') || badge;
            const text = `${count} contribution${count > 1 ? 's' : ''}`;
            // Remplace uniquement le texte du badge (l'icône éventuelle est conservée)
            const textNode = [...label.childNodes].reverse().find((n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
            if (textNode) textNode.textContent = ` ${text} `;
            else label.textContent = text;
        }
        updateVisibility();
    }

    function createdAt(item) {
        return item.dataset.createdAt || '';
    }

    // Ligne de liste construite à partir des data-* de la carte (même balisage que report_list_row())
    function buildRow(item) {
        const row = document.createElement('button');
        row.type = 'button';
        row.className = `report-list-row report-list-row--${item.dataset.category || 'note'}`;
        row.dataset.reportRow = item.dataset.reportId;
        row.setAttribute('aria-controls', item.id);
        row.setAttribute('aria-current', 'false');
        const title = document.createElement('span');
        title.className = 'report-list-row-title';
        title.textContent = item.dataset.title || '';
        const meta = document.createElement('span');
        meta.className = 'report-list-row-meta';
        const avatar = document.createElement('span');
        avatar.className = `project-report-avatar report-list-row-avatar${item.dataset.mine === '1' ? ' is-mine' : ''}`;
        avatar.setAttribute('aria-hidden', 'true');
        avatar.textContent = item.dataset.initials || '';
        const info = document.createElement('span');
        info.textContent = [item.dataset.time, item.dataset.categoryLabel].filter(Boolean).join(' · ');
        meta.append(avatar, info);
        row.append(title, meta);
        return row;
    }

    // Reconstruit la liste regroupée par jour de tournage (jours récents d'abord, « Général » (sans jour)
    // en dernier ; rapports récents d'abord dans chaque jour). Même ordre que group_reports_by_day() côté
    // serveur. Les cartes du volet de lecture sont rangées dans le même ordre.
    function regroup() {
        const tl = timeline();
        const box = find('[data-reports-groups]');
        if (!tl || !box) return;
        const groups = new Map();
        allItems().forEach((item) => {
            const day = item.dataset.day || '';
            if (!groups.has(day)) groups.set(day, { heading: item.dataset.dayHeading || 'Général', items: [] });
            groups.get(day).items.push(item);
        });
        const days = [...groups.keys()].filter(Boolean).sort().reverse();
        if (groups.has('')) days.push('');

        const fragment = document.createDocumentFragment();
        const ordered = [];
        days.forEach((day) => {
            const group = groups.get(day);
            group.items.sort((a, b) => (createdAt(a) < createdAt(b) ? 1 : createdAt(a) > createdAt(b) ? -1 : 0));
            const section = document.createElement('section');
            section.className = 'report-day-group';
            section.dataset.groupDay = day;
            const header = document.createElement('header');
            header.className = 'report-day-header';
            const title = document.createElement('span');
            title.className = 'report-day-title';
            title.textContent = group.heading;
            const count = document.createElement('span');
            count.className = 'report-day-count';
            count.dataset.groupCount = '';
            count.textContent = String(group.items.length);
            header.append(title, count);
            section.appendChild(header);
            group.items.forEach((item) => {
                section.appendChild(buildRow(item));
                ordered.push(item);
            });
            fragment.appendChild(section);
        });
        box.innerHTML = '';
        box.appendChild(fragment);
        ordered.forEach((item) => tl.appendChild(item));
        markSelection();
    }

    // Une seule carte visible dans le volet de lecture : celle du rapport sélectionné
    function markSelection() {
        const r = root();
        if (!r) return;
        const compose = isComposeOpen();
        const id = compose ? '' : selectedId();
        allItems().forEach((item) => {
            item.hidden = item.dataset.reportId !== id;
        });
        r.querySelectorAll('[data-report-row]').forEach((row) => {
            const on = row.dataset.reportRow === id;
            row.classList.toggle('is-selected', on);
            row.setAttribute('aria-current', on ? 'true' : 'false');
        });
        const draftRow = r.querySelector('[data-compose-row]');
        if (draftRow) draftRow.hidden = !compose;
        const anyVisible = visibleRows().length > 0;
        r.querySelectorAll('[data-reader-placeholder]').forEach((ph) => {
            const forNoMatch = ph.dataset.readerPlaceholder === 'nomatch';
            ph.hidden = compose || Boolean(id) || (forNoMatch ? anyVisible : !anyVisible);
        });
    }

    // Garde la ligne visible dans la liste (scroll interne uniquement, jamais celui de la page)
    function keepRowVisible(row) {
        const list = row.closest('[data-reports-list]');
        if (!list) return;
        const header = row.parentElement && row.parentElement.querySelector('.report-day-header');
        const top = row.offsetTop - (header ? header.offsetHeight : 0);
        const bottom = row.offsetTop + row.offsetHeight;
        if (top < list.scrollTop) list.scrollTop = top;
        else if (bottom > list.scrollTop + list.clientHeight) list.scrollTop = bottom - list.clientHeight;
    }

    // Mobile : « liste puis lecture » (le volet de lecture remplace la liste)
    function setReading(on) {
        const browser = find('[data-reports-browser]');
        if (browser) browser.classList.toggle('is-reading', Boolean(on));
    }

    function selectReport(id, { focus = false, reveal = false } = {}) {
        const r = root();
        if (!r) return;
        if (isComposeOpen()) setComposeOpen(false, { focus: false });
        r._selectedId = id ? String(id) : '';
        markSelection();
        const reader = r.querySelector('[data-reports-reader]');
        if (reader) reader.scrollTop = 0;
        const row = id && rowFor(id);
        if (row) {
            keepRowVisible(row);
            if (focus) row.focus();
        }
        setReading(Boolean(id) && reveal);
    }

    // Sélection conservée si le rapport est toujours visible, sinon premier rapport visible
    function ensureSelection() {
        const r = root();
        if (!r) return;
        const row = selectedId() && rowFor(selectedId());
        if (!row || row.hidden) {
            const first = visibleRows()[0];
            r._selectedId = first ? first.dataset.reportRow : '';
        }
        markSelection();
    }

    // Insère (ou remplace) une carte, reconstruit la liste et sélectionne le rapport
    function insertItem(element, { select = true } = {}) {
        const tl = timeline();
        if (!tl || !element) return;
        const existing = document.getElementById(element.id);
        if (existing) existing.replaceWith(element);
        else tl.appendChild(element);
        regroup();
        refreshIcons();
        updateCountdowns();
        applyFilters();
        const id = element.dataset.reportId;
        const row = rowFor(id);
        if (select && row && !row.hidden) selectReport(id, { reveal: true });
        if (row) {
            row.classList.add('is-new');
            setTimeout(() => row.classList.remove('is-new'), 2000);
        }
    }

    // ── Formulaire « Nouveau rapport » (ouvert dans le volet de lecture) ──

    function setComposeOpen(open, { focus = true } = {}) {
        const r = root();
        const form = createForm();
        if (!r || !form) return;
        form.hidden = !open;
        const opener = r.querySelector('[data-action="open-report-form"]');
        if (opener) {
            opener.hidden = open;
            opener.setAttribute('aria-expanded', open ? 'true' : 'false');
        }
        if (open) markSelection();
        else ensureSelection();
        updateVisibility();
        setReading(open);
        if (open) {
            const reader = r.querySelector('[data-reports-reader]');
            if (reader) reader.scrollTop = 0;
            const title = form.querySelector('input[name="title"]');
            if (focus && title) title.focus();
        } else if (focus && opener) {
            opener.focus();
        }
    }

    // ── Soumissions AJAX ────────────────────────────────────────

    async function submitReportForm(form) {
        const api = editorApi(form);
        if (api) api.sync();
        setFormError(form, '');
        setBusy(form, true);
        saveDraft(form);
        try {
            await waitForCompression(form);
            const data = await postForm(form);
            clearDraft(form);
            if (form.dataset.reportForm === 'create') {
                resetForm(form);
                setComposeOpen(false);
                insertItem(htmlToElement(data.html));
                updateCount(data.count);
                notify(data.message || 'Rapport publié.');
            } else {
                insertItem(htmlToElement(data.html));
                notify(data.message || 'Rapport modifié.');
            }
        } catch (err) {
            setFormError(form, networkMessage(err));
        } finally {
            if (document.body.contains(form)) setBusy(form, false);
        }
    }

    async function submitDelete(form) {
        const item = form.closest('.project-report-item');
        const csrf = form.querySelector('input[name="csrf_token"]');
        try {
            const data = await postForm(form);
            if (item) {
                const editForm = item.querySelector('[data-report-form="edit"]');
                if (editForm) clearDraft(editForm);
                const id = item.dataset.reportId;
                const rows = visibleRows();
                const index = rows.findIndex((row) => row.dataset.reportRow === id);
                const next = rows[index + 1] || rows[index - 1];
                item.remove();
                const r = root();
                if (r && selectedId() === id) r._selectedId = next ? next.dataset.reportRow : '';
                regroup();
            }
            updateCount(data.count);
            showUndoToast(data.restore_url, csrf ? csrf.value : '');
            applyFilters();
        } catch (err) {
            notify(networkMessage(err), 'error');
        }
    }

    async function restoreFrom(url, csrfToken) {
        const body = new FormData();
        body.append('csrf_token', csrfToken);
        const response = await fetch(url, {
            method: 'POST',
            body,
            headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' },
            credentials: 'same-origin',
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.status !== 'success') {
            const error = new Error(data.message || 'Restauration impossible.');
            error.isServer = true;
            throw error;
        }
        insertItem(htmlToElement(data.html));
        updateCount(data.count);
        return data;
    }

    function showUndoToast(restoreUrl, csrfToken) {
        const previous = document.querySelector('.report-undo-toast');
        if (previous) previous.remove();
        const toast = document.createElement('div');
        toast.className = 'report-undo-toast';
        toast.setAttribute('role', 'status');
        const text = document.createElement('span');
        text.textContent = 'Rapport supprimé.';
        toast.appendChild(text);
        if (restoreUrl) {
            const undo = document.createElement('button');
            undo.type = 'button';
            undo.textContent = 'Annuler';
            undo.addEventListener('click', async () => {
                undo.disabled = true;
                try {
                    await restoreFrom(restoreUrl, csrfToken);
                    toast.remove();
                    notify('Rapport restauré.');
                } catch (err) {
                    notify(networkMessage(err), 'error');
                    undo.disabled = false;
                }
            });
            toast.appendChild(undo);
        }
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), UNDO_DELAY_MS);
    }

    async function submitTrashRestore(form) {
        const csrf = form.querySelector('input[name="csrf_token"]');
        try {
            await restoreFrom(form.action, csrf ? csrf.value : '');
            const li = form.closest('[data-trash-item]');
            const trash = form.closest('[data-reports-trash]');
            if (li) li.remove();
            if (trash) {
                const remaining = trash.querySelectorAll('[data-trash-item]').length;
                const counter = trash.querySelector('[data-trash-count]');
                if (counter) counter.textContent = remaining;
                if (!remaining) trash.remove();
            }
            notify('Rapport restauré.');
        } catch (err) {
            notify(networkMessage(err), 'error');
        }
    }

    // ── Filtres & export ────────────────────────────────────────

    function filterValues() {
        const r = root();
        const get = (name) => {
            const el = r && r.querySelector(`[data-reports-filter="${name}"]`);
            return el ? el.value.trim() : '';
        };
        const pill = r && r.querySelector('[data-reports-category].is-active');
        return { q: get('q').toLowerCase(), category: pill ? pill.dataset.reportsCategory : '', day: get('day') };
    }

    // Compteurs des pastilles de catégorie (sur l'ensemble des rapports, filtres ignorés)
    function refreshCategoryCounts(items) {
        const r = root();
        if (!r) return;
        r.querySelectorAll('[data-category-count]').forEach((badge) => {
            const key = badge.dataset.categoryCount;
            const n = key ? items.filter((it) => it.dataset.category === key).length : items.length;
            badge.textContent = n;
            badge.hidden = Boolean(key) && n === 0;
        });
    }

    function applyFilters() {
        const r = root();
        const tl = timeline();
        if (!r || !tl) return;
        const { q, category, day } = filterValues();
        const words = q.split(/\s+/).filter(Boolean);
        const items = allItems();
        let visible = 0;
        items.forEach((item) => {
            const haystack = item.dataset.search || '';
            const ok = (!category || item.dataset.category === category)
                && (!day || item.dataset.day === day)
                && words.every((w) => haystack.includes(w));
            const row = rowFor(item.dataset.reportId);
            if (row) row.hidden = !ok;
            if (ok) visible += 1;
        });
        // Groupes de la liste : masqués s'ils n'ont plus de rapport visible, compteur = rapports visibles
        r.querySelectorAll('[data-reports-groups] .report-day-group').forEach((group) => {
            const shown = [...group.querySelectorAll('[data-report-row]')].filter((row) => !row.hidden).length;
            group.hidden = shown === 0;
            const counter = group.querySelector('[data-group-count]');
            if (counter) {
                counter.textContent = String(shown);
                counter.title = `${shown} rapport${shown > 1 ? 's' : ''}`;
            }
        });
        const noMatch = r.querySelector('[data-reports-nomatch]');
        if (noMatch) noMatch.hidden = !(items.length && !visible);
        refreshCategoryCounts(items);

        const summary = r.querySelector('[data-reports-filter-summary]');
        const active = Boolean(q || category || day);
        if (summary) {
            summary.classList.toggle('is-hidden', !active);
            summary.textContent = active
                ? `${visible} rapport${visible > 1 ? 's' : ''} sur ${items.length} correspondant aux filtres.`
                  + (q ? " L'export PDF applique la catégorie et le jour, pas la recherche texte." : '')
                : '';
        }

        const exportLink = r.querySelector('[data-reports-export]');
        if (exportLink) {
            const url = new URL(exportLink.href, window.location.origin);
            url.searchParams.delete('category');
            url.searchParams.delete('day');
            if (category) url.searchParams.set('category', category);
            if (day) url.searchParams.set('day', day);
            exportLink.href = url.pathname + url.search;
        }
        ensureSelection();
    }

    function resetFilters() {
        const r = root();
        if (!r) return;
        r.querySelectorAll('[data-reports-filter]').forEach((el) => { el.value = ''; });
        r.querySelectorAll('[data-reports-category]').forEach((p) => {
            const on = !p.dataset.reportsCategory;
            p.classList.toggle('is-active', on);
            p.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
        applyFilters();
    }

    // ── Compte à rebours de modification ────────────────────────

    function updateCountdowns() {
        document.querySelectorAll('[data-editable-until]').forEach((el) => {
            const until = Date.parse(el.dataset.editableUntil);
            if (Number.isNaN(until)) return;
            const remaining = until - Date.now();
            const item = el.closest('.project-report-item');
            if (remaining <= 0) {
                el.remove();
                // Fenêtre écoulée : on retire le bouton (le serveur refuserait la modification)
                const btn = item && item.querySelector('[data-action="edit-report"]');
                const form = item && item.querySelector('[data-report-form="edit"]');
                if (btn && (!form || form.classList.contains('is-hidden'))) btn.remove();
                return;
            }
            const minutes = Math.ceil(remaining / 60000);
            const h = Math.floor(minutes / 60);
            const m = minutes % 60;
            el.textContent = `Modifiable encore ${h ? `${h} h ${String(m).padStart(2, '0')}` : `${m} min`}`;
            el.classList.toggle('is-urgent', minutes <= 15);
        });
    }

    // ── Photos ──────────────────────────────────────────────────
    // Le sélecteur natif remplace sa sélection à chaque choix : on tient donc une liste cumulée
    // (input._reportPhotos), chaque photo étant optimisée dès son ajout. Le champ est vidé après
    // chaque choix pour pouvoir en ajouter d'autres (ou reprendre la même).

    const photoKey = (file) => `${file.name}|${file.size}|${file.lastModified}`;

    function clearPhotoPreview(form) {
        form.querySelectorAll('.report-photos-input').forEach((input) => {
            (input._reportPhotos || []).forEach((p) => URL.revokeObjectURL(p.url));
            input._reportPhotos = [];
            input.value = '';
            renderPhotoPreview(input);
        });
    }

    function addPhotos(input) {
        const form = input.form;
        const list = input._reportPhotos || (input._reportPhotos = []);
        const max = parseInt(input.dataset.maxPhotos || '10', 10);
        const picked = [...(input.files || [])].filter((f) => (f.type || '').startsWith('image/')
            || /\.(jpe?g|png|webp|heic|heif)$/i.test(f.name));
        input.value = '';

        let ignored = 0;
        picked.forEach((file) => {
            const key = photoKey(file);
            if (list.some((p) => p.key === key)) return; // déjà ajoutée
            if (list.length >= max) {
                ignored += 1;
                return;
            }
            const entry = { key, file, url: URL.createObjectURL(file) };
            // Optimisation (image-compressor.js) en arrière-plan ; l'envoi attend sa fin
            entry.ready = (typeof window.compressImageFile === 'function'
                ? window.compressImageFile(file).catch(() => file)
                : Promise.resolve(file)).then((compressed) => {
                entry.file = compressed || file;
                entry.done = true;
                renderPhotoPreview(input);
            });
            list.push(entry);
        });

        if (form) {
            setFormError(form, ignored
                ? `${ignored} photo${ignored > 1 ? 's' : ''} non ajoutée${ignored > 1 ? 's' : ''} : maximum ${max} photo${max > 1 ? 's' : ''} par envoi.`
                : '');
        }
        renderPhotoPreview(input);
        if (form) form.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function removePhoto(input, key) {
        const list = input._reportPhotos || [];
        const index = list.findIndex((p) => p.key === key);
        if (index === -1) return;
        URL.revokeObjectURL(list[index].url);
        list.splice(index, 1);
        if (input.form) setFormError(input.form, '');
        renderPhotoPreview(input);
    }

    function renderPhotoPreview(input) {
        const preview = input.parentElement.querySelector('[data-photos-preview]');
        if (!preview) return;
        preview.innerHTML = '';
        (input._reportPhotos || []).forEach((p) => {
            const tile = document.createElement('div');
            tile.className = 'report-photo-preview';
            const img = document.createElement('img');
            img.src = p.url;
            img.alt = p.file.name;
            img.className = 'report-photo-preview-img';
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'report-photo-preview-remove';
            remove.setAttribute('aria-label', `Retirer ${p.file.name}`);
            remove.title = 'Retirer cette photo';
            remove.textContent = '×';
            remove.addEventListener('click', () => removePhoto(input, p.key));
            tile.append(img, remove);
            preview.appendChild(tile);
        });
        const photos = input._reportPhotos || [];
        const count = photos.length;
        const label = input.parentElement.querySelector('[data-photos-add-label]');
        if (label) label.textContent = count ? "Ajouter d'autres photos" : 'Ajouter des photos';
        const status = input.parentElement.querySelector('[data-photos-status]');
        if (status) {
            const pending = photos.filter((p) => !p.done).length;
            status.classList.toggle('is-done', count > 0 && !pending);
            status.textContent = !count ? ''
                : pending ? `Optimisation de ${pending} photo${pending > 1 ? 's' : ''}…`
                    : `${count} photo${count > 1 ? 's' : ''} optimisée${count > 1 ? 's' : ''}`;
        }
    }

    // ── Initialisation ──────────────────────────────────────────

    function init() {
        const r = root();
        if (!r || r._reportsBound) return;
        r._reportsBound = true;

        // Formulaire de création : brouillon restauré au chargement
        const compose = r.querySelector('[data-report-form="create"]');
        if (compose) {
            editorApi(compose);
            // Un brouillon en attente rouvre directement le formulaire
            if (restoreDraft(compose)) setComposeOpen(true, { focus: false });
            bindDraftAutosave(compose);
        }

        r.addEventListener('click', (e) => {
            const pill = e.target.closest('[data-reports-category]');
            if (pill && r.contains(pill)) {
                r.querySelectorAll('[data-reports-category]').forEach((p) => {
                    const on = p === pill;
                    p.classList.toggle('is-active', on);
                    p.setAttribute('aria-pressed', on ? 'true' : 'false');
                });
                applyFilters();
                return;
            }
            const row = e.target.closest('[data-report-row]');
            if (row && r.contains(row)) {
                selectReport(row.dataset.reportRow, { reveal: true });
                return;
            }
            const action = e.target.closest('[data-action]');
            if (!action || !r.contains(action)) return;
            switch (action.dataset.action) {
                case 'reports-back': {
                    setReading(false);
                    const current = selectedId() && rowFor(selectedId());
                    if (current) current.focus();
                    break;
                }
                case 'reset-report-filters':
                    resetFilters();
                    break;
                case 'open-report-form':
                    setComposeOpen(true);
                    break;
                case 'close-report-form':
                    setComposeOpen(false); // le brouillon reste disponible
                    break;
                case 'cancel-report-form':
                    if (compose) {
                        clearDraft(compose);
                        resetForm(compose);
                    }
                    setComposeOpen(false);
                    break;
                default:
            }
        });

        // Édition : brouillon restauré à l'ouverture, effacé à l'annulation
        r.addEventListener('report-edit-open', (e) => {
            const form = e.target.closest('[data-report-form="edit"]');
            if (!form) return;
            restoreDraft(form);
            bindDraftAutosave(form);
        });
        r.addEventListener('report-edit-cancel', (e) => {
            const form = e.target.closest('[data-report-form="edit"]');
            if (form) {
                clearDraft(form);
                clearPhotoPreview(form);
                setFormError(form, '');
            }
        });

        // Soumissions (après validation de l'éditeur et confirmation éventuelle)
        document.addEventListener('submit', (e) => {
            const form = e.target;
            if (!(form instanceof HTMLFormElement) || e.defaultPrevented || !r.contains(form)) return;
            if (form.matches('[data-report-form]')) {
                e.preventDefault();
                submitReportForm(form);
            } else if (form.matches('.project-report-delete-form')) {
                e.preventDefault();
                submitDelete(form);
            } else if (form.matches('[data-report-restore]')) {
                e.preventDefault();
                submitTrashRestore(form);
            }
        });

        // Photos : chaque sélection s'ajoute aux précédentes. Le compresseur global est neutralisé
        // sur ces champs (data-compressed) : l'optimisation est faite photo par photo dans addPhotos().
        r.querySelectorAll('.report-photos-input').forEach((input) => { input.dataset.compressed = 'true'; });
        r.addEventListener('change', (e) => {
            if (e.target.matches && e.target.matches('.report-photos-input')) addPhotos(e.target);
        });

        // Liste : navigation au clavier (↑ ↓)
        const list = r.querySelector('[data-reports-list]');
        if (list) {
            list.addEventListener('keydown', (e) => {
                if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
                const rows = visibleRows();
                if (!rows.length) return;
                e.preventDefault();
                const index = rows.findIndex((row) => row.dataset.reportRow === selectedId());
                const step = e.key === 'ArrowDown' ? 1 : -1;
                const next = index === -1 ? 0 : Math.min(rows.length - 1, Math.max(0, index + step));
                selectReport(rows[next].dataset.reportRow, { focus: true });
            });
        }

        // Filtres
        r.querySelectorAll('[data-reports-filter]').forEach((el) => {
            el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', applyFilters);
        });
        regroup();
        applyFilters();
        updateVisibility();

        updateCountdowns();
        setInterval(updateCountdowns, 30000);

        // Lien direct vers un rapport (#report-12) : on le sélectionne et on le met en évidence
        let target = null;
        try {
            target = window.location.hash && document.querySelector(window.location.hash);
        } catch (e) {
            target = null; // ancre invalide
        }
        if (target && target.classList.contains('project-report-item')) {
            const id = target.dataset.reportId;
            if (rowFor(id) && rowFor(id).hidden) resetFilters();
            selectReport(id, { reveal: true });
            const row = rowFor(id);
            if (row) {
                row.classList.add('is-new');
                setTimeout(() => row.classList.remove('is-new'), 2500);
            }
            r.scrollIntoView({ block: 'start' });
        }
    }

    window.initProjectReports = init;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
