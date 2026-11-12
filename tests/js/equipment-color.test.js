// Sélecteur de couleur fixe du matériel (equipment-color.js) : ouverture, choix, enregistrement, erreur.
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const src = fs.readFileSync(path.join(__dirname, '../../static/js/src/admin/equipment-color.js'), 'utf8');
let fails = 0;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function check(name, cond, info) { console.log((cond ? 'OK  ' : 'FAIL') + ' ' + name + (cond ? '' : '  → ' + info)); if (!cond) fails++; }

function page(fail) {
  const dom = new JSDOM(`<!doctype html><body><meta name="csrf-token" content="tok">
<div data-eq-color-picker data-equipment-type="vehicle" data-equipment-id="rec_erider" data-equipment-name="eRider" data-url="/admin/fleet/equipment-color">
  <button id="t" class="eq-color-trigger eq-color-teal" data-eq-color-toggle aria-expanded="false"><span data-eq-color-label>Sarcelle</span></button>
  <div id="pop" data-eq-color-popover hidden>
    <button id="none" class="eq-color-swatch eq-color-none" data-eq-color-choice="none" data-eq-color-name="Sans couleur"></button>
    <button class="eq-color-swatch eq-color-teal is-selected" data-eq-color-choice="teal" data-eq-color-name="Sarcelle"></button>
    <button id="amber" class="eq-color-swatch eq-color-amber" data-eq-color-choice="amber" data-eq-color-name="Ambre"></button>
  </div>
</div>
<div data-eq-color-picker data-equipment-type="head" data-equipment-id="rec_head" data-equipment-name="Titan" data-url="/admin/fleet/equipment-color">
  <button id="t2" class="eq-color-trigger eq-color-cyan" data-eq-color-toggle aria-expanded="false"><span data-eq-color-label>Cyan</span></button>
  <div id="pop2" data-eq-color-popover hidden>
    <button id="h-teal" class="eq-color-swatch eq-color-teal is-taken" data-eq-color-choice="teal" data-eq-color-name="Sarcelle" disabled></button>
    <button id="h-amber" class="eq-color-swatch eq-color-amber" data-eq-color-choice="amber" data-eq-color-name="Ambre"></button>
    <button class="eq-color-swatch eq-color-cyan is-selected" data-eq-color-choice="cyan" data-eq-color-name="Cyan"></button>
  </div>
</div><div id="out">ailleurs</div></body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  w.__posts = []; w.__flash = [];
  w.showFlash = (m) => w.__flash.push(m);
  w.fetch = async (u, o) => {
    w.__posts.push(JSON.parse(o.body));
    if (fail) return { ok: false, status: 403, json: async () => ({ status: 'error', message: 'Action non autorisée.' }) };
    return { ok: true, status: 200, json: async () => ({ status: 'success', color: 'amber', label: 'Ambre' }) };
  };
  w.eval(src);
  return w;
}

(async () => {
  let w = page(false);
  const $ = (s) => w.document.querySelector(s);
  $('#t').click();
  check('ouverture', !$('#pop').hidden && $('#t').getAttribute('aria-expanded') === 'true', '');
  $('#out').click();
  check('fermeture au clic extérieur', $('#pop').hidden, '');
  $('#t').click();
  w.document.dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Escape' }));
  check('fermeture avec Échap', $('#pop').hidden, '');
  $('#t').click();
  $('#amber').click();
  await sleep(5);
  check('requête envoyée', w.__posts.length === 1 && w.__posts[0].color === 'amber' && w.__posts[0].equipment_id === 'rec_erider', JSON.stringify(w.__posts));
  check('pastille mise à jour', $('#t').classList.contains('eq-color-amber') && !$('#t').classList.contains('eq-color-teal'), $('#t').className);
  check('style du bouton conservé', $('#t').classList.contains('eq-color-trigger'), $('#t').className);
  check('libellé mis à jour', $('[data-eq-color-label]').textContent === 'Ambre', '');
  check('sélection mise à jour', $('#amber').classList.contains('is-selected') && !$('[data-eq-color-choice="teal"]').classList.contains('is-selected'), '');

  check('autre sélecteur : ancienne couleur libérée', !$('#h-teal').classList.contains('is-taken') && !$('#h-teal').disabled, $('#h-teal').className);
  check('autre sélecteur : nouvelle couleur réservée', $('#h-amber').classList.contains('is-taken') && $('#h-amber').disabled && $('#h-amber').title.indexOf('eRider') > -1, $('#h-amber').title);
  const before = w.__posts.length;
  $('#t2').click();
  $('#h-amber').click();
  await sleep(5);
  check('couleur prise : aucun enregistrement', w.__posts.length === before, JSON.stringify(w.__posts));

  // Sans couleur : libère la couleur dans les autres sélecteurs, sans rien réserver
  w.fetch = async (u, o) => { w.__posts.push(JSON.parse(o.body)); return { ok: true, status: 200, json: async () => ({ status: 'success', color: 'none', label: 'Sans couleur' }) }; };
  $('#t').click();
  $('#none').click();
  await sleep(5);
  check('sans couleur : requête', w.__posts[w.__posts.length - 1].color === 'none', JSON.stringify(w.__posts));
  check('sans couleur : couleur libérée ailleurs', !$('#h-amber').classList.contains('is-taken') && !$('#h-amber').disabled, $('#h-amber').className);
  check('sans couleur : pastille neutre', $('#t').classList.contains('eq-color-none') && !$('#t').classList.contains('eq-color-amber'), $('#t').className);

  w = page(true);
  w.document.querySelector('#t').click();
  w.document.querySelector('#amber').click();
  await sleep(5);
  check('refus : couleur inchangée', w.document.querySelector('#t').classList.contains('eq-color-teal'), '');
  check('refus : message', w.__flash[0] === 'Action non autorisée.', JSON.stringify(w.__flash));

  console.log(fails ? `\n${fails} échec(s)` : '\nTous les tests passent');
  process.exit(fails ? 1 : 0);
})();
