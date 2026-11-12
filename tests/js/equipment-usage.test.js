// Pointage du matériel dans le calendrier du hub projet (project-detail-calendar.js) :
// bascule du mode, cycle des états, glisser, pinceau « tout le matériel », annulation en cas d'erreur.
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const src = fs.readFileSync(path.join(__dirname, '../../static/js/src/admin/project-detail-calendar.js'), 'utf8');
let fails = 0;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function check(name, cond, info) { console.log((cond ? 'OK  ' : 'FAIL') + ' ' + name + (cond ? '' : '  → ' + info)); if (!cond) fails++; }

const USAGE = {
  days: [
    { iso: '2026-09-10', label: 'J1 · jeu. 10 sept. 2026', is_past: true },
    { iso: '2026-09-11', label: 'J2 · ven. 11 sept. 2026', is_past: true },
    { iso: '2026-09-12', label: 'J3 · sam. 12 sept. 2026', is_past: false },
  ],
  equipment: [
    { key: 'vehicle:rec_erider', type: 'vehicle', id: 'rec_erider', name: 'eRider <b>', code: 'BV-01', color: 'teal', type_label: 'Véhicule', used_days: 0, unused_days: 0, pending_days: 3 },
    { key: 'vehicle:rec_ecar', type: 'vehicle', id: 'rec_ecar', name: 'eCar', code: '', color: 'indigo', type_label: 'Véhicule', used_days: 0, unused_days: 0, pending_days: 3 },
  ],
  marks: { 'vehicle:rec_erider': {}, 'vehicle:rec_ecar': {} },
  pending_count: 2,
  orphans_count: 0,
};

function page({ fail = false } = {}) {
  const data = {
    date_mode: 'continuous', is_punctual: false, shoot_dates: [],
    shoot_start: '2026-09-10', shoot_end: '2026-09-12', departure_date: '2026-09-09', return_date: '2026-09-13',
    inter_shoot_intervals: [], usage: JSON.parse(JSON.stringify(USAGE)),
    usage_url: '/admin/projects/1/equipment-usage', usage_export_url: '/admin/projects/1/equipment-usage/export',
  };
  const dom = new JSDOM(`<!doctype html><body>
<meta name="csrf-token" content="tok">
<div id="projectShootCalendarWrapper">
  <span data-usage-pending-badge><span data-usage-pending-label>2 jours à pointer</span></span>
  <div id="projectShootCalendar"></div>
  <script id="projectShootCalendarData" type="application/json">${JSON.stringify(data)}</script>
</div></body>`, { runScripts: 'outside-only', url: 'https://bv.test/admin/projects/1' });
  const w = dom.window;
  w.__posts = [];
  w.__flash = [];
  w.showFlash = (m, c) => w.__flash.push([m, c]);
  w.document.elementFromPoint = () => null;
  w.fetch = async (u, opts) => {
    const body = JSON.parse(opts.body);
    w.__posts.push({ url: String(u), body, headers: opts.headers });
    if (fail) return { ok: false, status: 400, json: async () => ({ status: 'error', message: 'Refusé' }) };
    const usage = JSON.parse(JSON.stringify(USAGE));
    usage.pending_count = 1;
    usage.equipment[0].used_days = 1;
    return { ok: true, status: 200, json: async () => ({ status: 'success', usage }) };
  };
  w.eval(src);
  return w;
}

function pointer(w, el, type) {
  const ev = new w.MouseEvent(type, { bubbles: true, button: 0, cancelable: true });
  el.dispatchEvent(ev);
}

const cell = (w, iso) => w.document.querySelector(`.pdp-day-cell[data-date="${iso}"]`);

(async () => {
  // 1. Bascule du mode
  let w = page();
  await sleep(10);
  const cal = w.document.getElementById('projectShootCalendar');
  check('mode inactif par défaut', !cal.classList.contains('is-usage-mode'), cal.className);
  // Barre permanente : présente avant le calendrier dès le mode planning, puces en lecture seule
  const barBeforeCalendar = () => {
    const host = cal.querySelector('[data-usage-toolbar-host]');
    const vp = cal.querySelector('#pdp-calendar-viewport');
    return host && vp && host.querySelector('.pdu-toolbar') &&
      (host.compareDocumentPosition(vp) & w.Node.DOCUMENT_POSITION_FOLLOWING);
  };
  const chipNames = () => Array.from(cal.querySelectorAll('.pdu-chip .pdu-chip-name')).map((n) => n.textContent).join('|');
  const monthTitles = () => Array.from(cal.querySelectorAll('.pdp-month-title')).map((n) => n.textContent).join('|');
  check('barre visible en planning, avant le calendrier', barBeforeCalendar(), cal.innerHTML.slice(0, 200));
  check('puces non cliquables en planning', !cal.querySelector('[data-usage-brush]') && cal.querySelectorAll('.pdu-chip.is-static').length === 2, '');
  check('place réservée « Tout le matériel »', !!cal.querySelector('.pdu-chip--all.is-placeholder'), '');
  const namesPlanning = chipNames();
  const monthsPlanning = monthTitles();
  cal.querySelector('[data-action="toggle-usage-mode"]').click();
  check('mode pointage activé', cal.classList.contains('is-usage-mode'), cal.className);
  check('libellé du bouton', cal.querySelector('[data-action="toggle-usage-mode"]').textContent.trim() === 'Terminer le pointage', '');
  check('barre toujours avant le calendrier', barBeforeCalendar(), '');
  check('mêmes puces dans les deux modes', chipNames() === namesPlanning, chipNames() + ' vs ' + namesPlanning);
  check('mois inchangés à la bascule', monthTitles() === monthsPlanning, monthTitles() + ' vs ' + monthsPlanning);
  check('jours de tournage cliquables', w.document.querySelectorAll('.pdp-day-cell.is-usage-day').length === 3, '');
  check('départ hors pointage', cell(w, '2026-09-09').classList.contains('is-usage-off'), cell(w, '2026-09-09').className);
  check('nom échappé dans la barre', !w.document.querySelector('.pdu-toolbar b') && w.document.querySelector('.pdu-chip-name').textContent === 'eRider <b>', '');

  // 2. Cycle non pointé → utilisé → non utilisé → non pointé (pinceau eRider)
  const d1 = cell(w, '2026-09-10');
  pointer(w, d1, 'pointerdown'); pointer(w, w.document, 'pointerup');
  await sleep(5);
  check('clic → utilisé', cell(w, '2026-09-10').classList.contains('usage-state-used'), cell(w, '2026-09-10').className);
  check('requête envoyée', w.__posts.length === 1 && w.__posts[0].body.changes[0].state === 'used'
    && w.__posts[0].body.changes[0].equipment_id === 'rec_erider' && w.__posts[0].headers['X-CSRFToken'] === 'tok', JSON.stringify(w.__posts));
  check('rappel mis à jour', w.document.querySelector('[data-usage-pending-label]').textContent === '1 jour à pointer', '');
  check('compteur de la puce', w.document.querySelector('.pdu-chip-count').textContent === '1/3 j', w.document.querySelector('.pdu-chip-count').textContent);
  pointer(w, cell(w, '2026-09-10'), 'pointerdown'); pointer(w, w.document, 'pointerup');
  await sleep(5);
  check('2e clic → non utilisé', cell(w, '2026-09-10').classList.contains('usage-state-unused'), cell(w, '2026-09-10').className);
  pointer(w, cell(w, '2026-09-10'), 'pointerdown'); pointer(w, w.document, 'pointerup');
  await sleep(5);
  check('3e clic → non pointé', cell(w, '2026-09-10').classList.contains('usage-state-none') && w.__posts[2].body.changes[0].state === 'none', '');

  // 3. Glisser sur plusieurs jours : un seul lot
  w.__posts.length = 0;
  let hovered = null;
  w.document.elementFromPoint = () => hovered;
  pointer(w, cell(w, '2026-09-11'), 'pointerdown');
  hovered = cell(w, '2026-09-12');
  w.document.getElementById('projectShootCalendar').dispatchEvent(new w.MouseEvent('pointermove', { bubbles: true }));
  pointer(w, w.document, 'pointerup');
  await sleep(5);
  check('glisser → 2 jours en un lot', w.__posts.length === 1 && w.__posts[0].body.changes.length === 2, JSON.stringify(w.__posts));

  // 4. Pinceau « tout le matériel »
  w.__posts.length = 0;
  w.document.querySelector('[data-usage-brush="*"]').click();
  pointer(w, cell(w, '2026-09-10'), 'pointerdown'); pointer(w, w.document, 'pointerup');
  await sleep(5);
  const ch = w.__posts[0].body.changes;
  check('tout le matériel ce jour', ch.length === 2 && ch.every((c) => c.state === 'used' && c.date === '2026-09-10'), JSON.stringify(ch));

  // 5. Erreur serveur : annulation locale + message
  w = page({ fail: true });
  await sleep(10);
  w.document.querySelector('[data-action="toggle-usage-mode"]').click();
  pointer(w, cell(w, '2026-09-10'), 'pointerdown'); pointer(w, w.document, 'pointerup');
  await sleep(5);
  check('annulation après refus', cell(w, '2026-09-10').classList.contains('usage-state-none'), cell(w, '2026-09-10').className);
  check('message d\'erreur', w.__flash.length === 1 && w.__flash[0][0] === 'Refusé', JSON.stringify(w.__flash));

  console.log(fails ? `\n${fails} échec(s)` : '\nTous les tests passent');
  process.exit(fails ? 1 : 0);
})();
