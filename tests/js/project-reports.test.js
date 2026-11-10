// Module des rapports d'équipe (project-reports.js) : filtres, export, brouillons, compte à rebours, photos, AJAX.
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const SRC = path.join(__dirname, '../../static/js/src/admin');
const editorSrc = fs.readFileSync(path.join(SRC, 'notion-editor.js'), 'utf8');
const reportsSrc = fs.readFileSync(path.join(SRC, 'project-reports.js'), 'utf8');
let fails = 0;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function check(name, cond, info) { console.log((cond ? 'OK  ' : 'FAIL') + ' ' + name + (cond ? '' : '  → ' + info)); if (!cond) fails++; }

const item = (id, { category = 'note', day = '', search = '', created = '2026-09-10T10:00:00', until = '' } = {}) => `
<div class="project-report-item" id="report-${id}" data-report-id="${id}" data-category="${category}" data-day="${day}"
  data-day-heading="${day ? 'J · ' + day : 'Général'}"
  data-updated-at="${created}" data-created-at="${created}" data-search="${search}">
  <div class="project-report-card">
    ${until ? `<span class="project-report-countdown" data-editable-until="${until}"></span>` : ''}
    <button data-action="edit-report" data-report-id="${id}">edit</button>
    <form class="project-report-delete-form" action="/admin/projects/1/reports/${id}/delete" method="POST">
      <input type="hidden" name="csrf_token" value="tok"><button type="submit">x</button>
    </form>
  </div>
</div>`;

const editorMarkup = (uid) => `<div class="notion-wysiwyg-wrapper"><textarea name="content"></textarea>
  <div class="notion-slash-container"><div class="notion-slash-menu"></div><div class="notion-context-menu"></div>
  <div class="notion-live-editor" id="reportContentEditor-${uid}" contenteditable="true"></div></div></div>`;

function page(items, { storage = {} } = {}) {
  const dom = new JSDOM(`<!doctype html><body>
<div data-reports-root data-project-id="1">
  <span data-reports-count-badge><span class="badge-pill">${items.length} contributions</span></span>
  <button type="button" data-action="open-report-form">+ Nouveau rapport</button>
  <form id="create" data-report-form="create" data-draft-key="1:new" action="/admin/projects/1/reports" method="POST" hidden>
    <button type="button" data-action="close-report-form">x</button>
    <button type="button" data-action="cancel-report-form">Annuler</button>
    <input type="hidden" name="csrf_token" value="tok">
    <div class="report-draft-banner is-hidden" data-draft-banner></div>
    <input name="title" type="text">
    <label><input type="radio" name="category" value="note" checked></label>
    <label><input type="radio" name="category" value="securite"></label>
    <select name="shoot_day"><option value="">—</option><option value="2026-09-10">J1</option></select>
    ${editorMarkup('new')}
    <input type="file" name="photos" class="report-photos-input" data-max-photos="2"><div data-photos-preview></div>
    <div class="report-form-error is-hidden" data-form-error></div>
    <button type="submit" data-submit-label="Publier">Publier</button>
  </form>
  <div data-reports-toolbar>
    <button type="button" class="is-active" data-reports-category="">Toutes <span data-category-count=""></span></button>
    <button type="button" data-reports-category="securite">Sécurité <span data-category-count="securite"></span></button>
    <button type="button" data-reports-category="note">Note <span data-category-count="note"></span></button>
    <input data-reports-filter="q">
    <select data-reports-filter="day"><option value=""></option><option value="2026-09-10"></option></select>
    <a data-reports-export href="/admin/projects/1/reports/export">PDF</a>
  </div>
  <p data-reports-filter-summary class="is-hidden"></p>
  <div data-reports-timeline>${items.join('')}</div>
  <div data-reports-empty hidden></div>
</div></body>`, { runScripts: 'outside-only', url: 'https://bv.test/admin/projects/1' });
  const w = dom.window;
  Object.entries(storage).forEach(([k, v]) => w.localStorage.setItem(k, v));
  w.document.execCommand = () => true;
  w.HTMLElement.prototype.scrollIntoView = () => {};
  w.URL.createObjectURL = () => 'blob:x';
  w.URL.revokeObjectURL = () => {};
  w.CSS = w.CSS || { escape: (s) => s };
  w.flashes = [];
  w.showFlash = (m, c) => w.flashes.push([m, c]);
  w.eval(editorSrc);
  w.eval(reportsSrc);
  w.initProjectReports();
  return { w, doc: w.document };
}

(async () => {
  // ── Filtres & lien d'export ──
  {
    const { w, doc } = page([
      item(1, { category: 'securite', day: '2026-09-10', search: 'pneu avant crevé' }),
      item(2, { category: 'note', search: 'rien à signaler' }),
    ]);
    const q = doc.querySelector('[data-reports-filter="q"]');
    q.value = 'pneu'; q.dispatchEvent(new w.Event('input'));
    check('Filtre texte', !doc.getElementById('report-1').hidden && doc.getElementById('report-2').hidden, '');
    q.value = ''; q.dispatchEvent(new w.Event('input'));
    doc.querySelector('[data-reports-category="securite"]').click();
    const day = doc.querySelector('[data-reports-filter="day"]');
    day.value = '2026-09-10'; day.dispatchEvent(new w.Event('change'));
    check('Filtres catégorie + jour', !doc.getElementById('report-1').hidden && doc.getElementById('report-2').hidden, '');
    const href = doc.querySelector('[data-reports-export]').getAttribute('href');
    check("Lien d'export synchronisé", href === '/admin/projects/1/reports/export?category=securite&day=2026-09-10', href);
    check('Résumé des filtres', doc.querySelector('[data-reports-filter-summary]').textContent.startsWith('1 rapport sur 2'), doc.querySelector('[data-reports-filter-summary]').textContent);
  }

  // ── Pastilles de catégorie : compteurs et état actif ──
  {
    const { w, doc } = page([item(1, { category: 'securite' }), item(2), item(3)]);
    const count = (k) => doc.querySelector(`[data-category-count="${k}"]`).textContent;
    w.initProjectReports();
    doc.querySelector('[data-reports-filter="q"]').dispatchEvent(new w.Event('input'));
    check('Compteurs des pastilles', count('') === '3' && count('securite') === '1' && count('note') === '2', `${count('')}/${count('securite')}/${count('note')}`);
    const pill = doc.querySelector('[data-reports-category="note"]');
    pill.click();
    check('Pastille active (aria-pressed)', pill.classList.contains('is-active') && pill.getAttribute('aria-pressed') === 'true'
      && !doc.querySelector('[data-reports-category=""]').classList.contains('is-active'), '');
    check('Filtre par pastille', doc.getElementById('report-1').hidden && !doc.getElementById('report-2').hidden, '');
  }

  // ── Regroupement par jour de tournage ──
  {
    const { w, doc } = page([
      item(1, { day: '2026-09-10', created: '2026-09-10T08:00:00' }),
      item(2, { day: '', created: '2026-09-12T08:00:00' }),
      item(3, { day: '2026-09-11', created: '2026-09-11T08:00:00', category: 'securite' }),
      item(4, { day: '2026-09-10', created: '2026-09-10T18:00:00' }),
    ]);
    w.fetch = async () => ({ ok: true, status: 200, json: async () => ({ status: 'success', html: item(5, { day: '2026-09-11', created: '2026-09-11T20:00:00' }) }) });
    const form = doc.getElementById('create');
    form.querySelector('input[name="title"]').value = 'x';
    form.querySelector('.notion-wysiwyg-wrapper')._notionEditor.setContent('<p>y</p>');
    form.dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
    await sleep(20);
    const groups = [...doc.querySelectorAll('.report-day-group')].map((g) => g.dataset.groupDay + ':' + [...g.querySelectorAll('.project-report-item')].map((i) => i.dataset.reportId).join(''));
    check('Groupes : jours récents d\'abord, « sans jour » en dernier, rapports récents d\'abord', groups.join(' | ') === '2026-09-11:53 | 2026-09-10:41 | :2', groups.join(' | '));
    check('Intitulé et compteur du groupe', doc.querySelector('.report-day-group .report-day-title').textContent === 'J · 2026-09-11'
      && doc.querySelector('.report-day-group [data-group-count]').textContent === '2 rapports', doc.querySelector('.report-day-group [data-group-count]').textContent);
    doc.querySelector('[data-reports-category="securite"]').click();
    const visibleGroups = [...doc.querySelectorAll('.report-day-group')].filter((g) => !g.hidden).map((g) => g.dataset.groupDay);
    check('Filtre : groupes vides masqués, compteur = visibles', visibleGroups.join(',') === '2026-09-11'
      && doc.querySelector('.report-day-group [data-group-count]').textContent === '1 rapport', visibleGroups.join(','));
  }

  // ── Formulaire « Nouveau rapport » replié ──
  {
    const { w, doc } = page([]);
    const form = doc.getElementById('create');
    const opener = doc.querySelector('[data-action="open-report-form"]');
    check('Replié par défaut', form.hidden && !opener.hidden, '');
    opener.click();
    check('Ouverture au clic (bouton masqué)', !form.hidden && opener.hidden && opener.getAttribute('aria-expanded') === 'true', '');
    form.querySelector('input[name="title"]').value = 'Brouillon';
    form.dispatchEvent(new w.Event('input', { bubbles: true }));
    await sleep(750);
    form.querySelector('[data-action="close-report-form"]').click();
    check('× : ferme et garde le brouillon', form.hidden && !opener.hidden && !!w.localStorage.getItem('bv_report_draft:1:new'), '');
    const reopened = page([], { storage: { 'bv_report_draft:1:new': w.localStorage.getItem('bv_report_draft:1:new') } });
    check('Brouillon existant : formulaire rouvert au chargement', !reopened.doc.getElementById('create').hidden, '');
    opener.click();
    form.querySelector('[data-action="cancel-report-form"]').click();
    check('Annuler : ferme, vide et efface le brouillon', form.hidden && form.querySelector('input[name="title"]').value === ''
      && !w.localStorage.getItem('bv_report_draft:1:new'), '');
  }

  // ── Compte à rebours ──
  {
    const soon = new Date(Date.now() + 72 * 60000).toISOString();
    const past = new Date(Date.now() - 60000).toISOString();
    const { doc } = page([item(1, { until: soon }), item(2, { until: past })]);
    const txt = doc.querySelector('#report-1 [data-editable-until]').textContent;
    check('Compte à rebours affiché', /^Modifiable encore 1 h 1[12]$/.test(txt), txt);
    check('Fenêtre écoulée : bouton modifier retiré', !doc.querySelector('#report-2 [data-action="edit-report"]') && !doc.querySelector('#report-2 [data-editable-until]'), '');
  }

  // ── Brouillon : sauvegarde puis restauration ──
  {
    const { w, doc } = page([]);
    const form = doc.getElementById('create');
    form.querySelector('input[name="title"]').value = 'Débrief J1';
    form.querySelector('input[value="securite"]').checked = true;
    const api = form.querySelector('.notion-wysiwyg-wrapper')._notionEditor;
    api.setContent('<p>Texte <strong>important</strong></p>');
    form.dispatchEvent(new w.Event('input', { bubbles: true }));
    await sleep(750);
    const saved = JSON.parse(w.localStorage.getItem('bv_report_draft:1:new') || 'null');
    check('Brouillon enregistré', saved && saved.title === 'Débrief J1' && saved.category === 'securite' && saved.html.includes('important'), JSON.stringify(saved));

    const second = page([], { storage: { 'bv_report_draft:1:new': JSON.stringify(saved) } });
    const f2 = second.doc.getElementById('create');
    check('Brouillon restauré au chargement', f2.querySelector('input[name="title"]').value === 'Débrief J1'
      && f2.querySelector('input[value="securite"]').checked
      && f2.querySelector('textarea[name="content"]').value === 'Texte **important**'
      && !f2.querySelector('[data-draft-banner]').classList.contains('is-hidden'), f2.querySelector('textarea[name="content"]').value);
    f2.querySelector('.report-draft-discard').click();
    check('« Effacer le brouillon » vide le formulaire et le stockage', !second.w.localStorage.getItem('bv_report_draft:1:new')
      && f2.querySelector('input[name="title"]').value === '', '');

    const old = { ...saved, savedAt: Date.now() - 8 * 24 * 3600 * 1000 };
    const third = page([], { storage: { 'bv_report_draft:1:new': JSON.stringify(old) } });
    check('Brouillon expiré ignoré', third.doc.querySelector('#create input[name="title"]').value === '', '');
  }

  // ── Publication AJAX : succès puis échec réseau ──
  {
    const { w, doc } = page([item(1, { created: '2026-09-10T10:00:00' })]);
    const form = doc.getElementById('create');
    form.querySelector('input[name="title"]').value = 'Nouveau';
    form.querySelector('.notion-wysiwyg-wrapper')._notionEditor.setContent('<p>Corps</p>');
    w.localStorage.setItem('bv_report_draft:1:new', JSON.stringify({ title: 'Nouveau', savedAt: Date.now() }));
    let sent = null;
    w.fetch = async (url, opts) => { sent = { url, opts }; return { ok: true, status: 201, json: async () => ({ status: 'success', count: 2, message: 'Rapport publié.', html: item(9, { created: '2026-09-11T08:00:00' }) }) }; };
    form.dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
    await sleep(20);
    const order = [...doc.querySelectorAll('[data-reports-timeline] .project-report-item')].map((e) => e.id);
    check('Publication sans rechargement : carte insérée en tête', order[0] === 'report-9' && order.length === 2, order.join(','));
    check('Requête XHR multipart', sent && sent.opts.headers['X-Requested-With'] === 'XMLHttpRequest' && sent.opts.body instanceof w.FormData, '');
    check('Formulaire vidé + brouillon effacé', form.querySelector('input[name="title"]').value === '' && !w.localStorage.getItem('bv_report_draft:1:new'), '');
    check('Compteur mis à jour', doc.querySelector('.badge-pill').textContent.includes('2 contributions'), doc.querySelector('.badge-pill').textContent);

    form.querySelector('input[name="title"]').value = 'Hors ligne';
    form.querySelector('.notion-wysiwyg-wrapper')._notionEditor.setContent('<p>Texte</p>');
    w.fetch = async () => { throw new TypeError('Failed to fetch'); };
    form.dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
    await sleep(20);
    const err = form.querySelector('[data-form-error]');
    check('Échec réseau : message + brouillon conservé', !err.classList.contains('is-hidden') && /brouillon est conservé/.test(err.textContent)
      && JSON.parse(w.localStorage.getItem('bv_report_draft:1:new')).title === 'Hors ligne', err.textContent);
    check('Bouton réactivé après échec', !form.querySelector('button[type="submit"]').disabled, '');
  }

  // ── Suppression AJAX + annulation ──
  {
    const { w, doc } = page([item(1), item(2)]);
    w.fetch = async (url) => {
      if (url.endsWith('/delete')) return { ok: true, status: 200, json: async () => ({ status: 'success', count: 1, restore_url: '/admin/projects/1/reports/1/restore' }) };
      return { ok: true, status: 200, json: async () => ({ status: 'success', count: 2, html: item(1) }) };
    };
    const del = doc.querySelector('#report-1 .project-report-delete-form');
    del.dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
    await sleep(20);
    const toast = doc.querySelector('.report-undo-toast');
    check('Suppression sans rechargement + toast « Annuler »', !doc.getElementById('report-1') && toast && toast.querySelector('button'), '');
    toast.querySelector('button').click();
    await sleep(20);
    check('Annuler restaure la carte', !!doc.getElementById('report-1') && !doc.querySelector('.report-undo-toast'), '');
  }

  // ── Photos : sélections successives cumulées, retrait, limite, envoi ──
  {
    const { w, doc } = page([]);
    const input = doc.querySelector('.report-photos-input');
    const mkFile = (n) => new w.File(['x' + n], `p${n}.jpg`, { type: 'image/jpeg', lastModified: n });
    const pick = (files) => {
      Object.defineProperty(input, 'files', { value: files, configurable: true });
      input.dispatchEvent(new w.Event('change', { bubbles: true }));
    };
    const tiles = () => doc.querySelectorAll('[data-photos-preview] .report-photo-preview').length;
    const err = doc.querySelector('#create [data-form-error]');

    pick([mkFile(1)]);
    pick([mkFile(2)]);
    check('2 sélections successives : les photos s\'ajoutent', tiles() === 2 && input._reportPhotos.length === 2, String(tiles()));
    pick([mkFile(2)]);
    check('Même photo choisie deux fois : pas de doublon', tiles() === 2, String(tiles()));
    pick([mkFile(3), mkFile(4)]);
    check('Limite (2) : surplus refusé avec message', tiles() === 2 && !err.classList.contains('is-hidden') && /maximum 2/.test(err.textContent), err.textContent);
    doc.querySelector('.report-photo-preview-remove').click();
    check('Croix : retire une photo', tiles() === 1 && input._reportPhotos[0].file.name === 'p2.jpg', String(tiles()));
    pick([mkFile(5)]);
    check('Ajout après retrait', tiles() === 2, String(tiles()));

    const form = doc.getElementById('create');
    form.querySelector('input[name="title"]').value = 'Photos';
    form.querySelector('.notion-wysiwyg-wrapper')._notionEditor.setContent('<p>Voir</p>');
    let body = null;
    w.fetch = async (url, opts) => { body = opts.body; return { ok: true, status: 201, json: async () => ({ status: 'success', count: 1, html: item(7) }) }; };
    form.dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
    await sleep(30);
    const sentNames = body ? body.getAll('photos').map((f) => f.name) : [];
    check('Envoi : toutes les photos cumulées sont transmises', sentNames.join(',') === 'p2.jpg,p5.jpg', sentNames.join(','));
    check('Après publication : sélection vidée', tiles() === 0 && input._reportPhotos.length === 0, String(tiles()));
  }

  process.exit(fails ? 1 : 0);
})();
