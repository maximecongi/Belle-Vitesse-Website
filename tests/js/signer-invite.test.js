// Modales d'invitation unifiées (signer-invite.js) : ouverture/fermeture, autocomplétion, lien contact, ?invite=.
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const src = fs.readFileSync(path.join(__dirname, '../../static/js/src/admin/signer-invite.js'), 'utf8');
let fails = 0;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function check(name, cond, info) { console.log((cond ? 'OK  ' : 'FAIL') + ' ' + name + (cond ? '' : '  → ' + info)); if (!cond) fails++; }

const RESULTS = [
  { kind: 'contact', id: 7, first_name: 'Claire', last_name: 'Juriste', full_name: 'Claire Juriste', mail: 'claire@alpha.fr', phone: '0601', job_title: 'Gérante', company: 'Prod Alpha', project_role: '', group: 'production', group_label: 'Contacts de la production' },
  { kind: 'user', id: 3, first_name: 'Camille', last_name: 'Tech', full_name: 'Camille Tech', mail: 'camille@bv.fr', phone: '', job_title: '', company: 'Belle Vitesse', project_role: '', group: 'team', group_label: 'Équipe BV' },
];

function page(url = 'https://bv.test/admin/projects/1') {
  const dom = new JSDOM(`<!doctype html><body>
<button id="open" data-signer-modal-open="m1">Inviter</button>
<div id="m1" class="admin-modal-overlay u-d-none" data-signer-modal>
  <button id="x" data-signer-modal-close>×</button>
  <form data-signer-form>
    <input type="hidden" name="return_to" value="/admin/projects/1?invite=m1">
    <input type="hidden" name="signer_contact_id" value="" data-signer-field="contact_id">
    <input type="hidden" name="signer_user_id" value="" data-signer-field="user_id">
    <div data-signer-picker data-fill="full" data-search-url="/admin/api/signers/search" data-project-id="1">
      <input id="q" data-signer-search aria-expanded="false">
      <div id="m1-results" class="u-d-none" data-signer-results></div>
      <div class="u-d-none" data-signer-linked><span data-signer-linked-label></span><button type="button" id="unlink" data-signer-unlink>Délier</button></div>
    </div>
    <select name="signer_role" data-signer-role><option value="pilot">Pilote</option><option value="other">Autre</option></select>
    <div class="u-d-none" data-signer-role-custom><input name="signer_role_custom"></div>
    <input id="fn" name="signer_first_name" data-signer-field="first_name">
    <input id="ln" name="signer_last_name" data-signer-field="last_name">
    <input id="mail" name="signer_email" data-signer-field="mail">
    <input id="phone" name="signer_phone" data-signer-field="phone">
    <input id="company" name="signer_company" value="Prod Alpha" data-signer-field="company">
  </form>
</div>
<form id="inc">
  <div data-signer-picker data-fill="email" data-search-url="/admin/api/signers/search" data-project-id="">
    <input id="q2" data-signer-search><div id="inc-results" class="u-d-none" data-signer-results></div>
  </div>
  <input id="incmail" name="recipient_email" data-signer-field="mail">
</form>
</body>`, { runScripts: 'outside-only', url });
  const w = dom.window;
  w.__calls = [];
  w.fetch = async (u) => { w.__calls.push(String(u)); return { ok: true, status: 200, json: async () => ({ results: RESULTS }) }; };
  w.eval(src);
  return w;
}

const typeIn = (w, el, value) => { el.value = value; el.dispatchEvent(new w.Event('input', { bubbles: true })); };
const key = (w, el, k) => el.dispatchEvent(new w.KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }));

(async () => {
  {
    const w = page();
    const doc = w.document;
    const modal = doc.getElementById('m1');
    let opened = 0;
    doc.addEventListener('signer-modal:open', () => { opened++; });

    doc.getElementById('open').click();
    check('Ouverture via data-signer-modal-open', modal.classList.contains('is-active') && !modal.classList.contains('u-d-none'), modal.className);
    check('Événement signer-modal:open émis', opened === 1, String(opened));
    doc.getElementById('x').click();
    check('Fermeture via data-signer-modal-close', modal.classList.contains('u-d-none'), modal.className);
    doc.getElementById('open').click();
    key(w, doc.body, 'Escape');
    check('Fermeture à Échap', modal.classList.contains('u-d-none'), modal.className);

    // Rôle « Autre »
    const sel = doc.querySelector('[data-signer-role]');
    sel.value = 'other'; sel.dispatchEvent(new w.Event('change', { bubbles: true }));
    const custom = doc.querySelector('[data-signer-role-custom]');
    check('Rôle « Autre » : champ libre affiché et requis', !custom.classList.contains('u-d-none') && custom.querySelector('input').required, custom.className);

    // Autocomplétion
    const q = doc.getElementById('q');
    typeIn(w, q, 'cla');
    await sleep(260);
    check('Recherche : URL avec q et project_id', w.__calls.some((u) => u.includes('q=cla') && u.includes('project_id=1')), w.__calls.join(' | '));
    const list = doc.getElementById('m1-results');
    check('Résultats groupés affichés', !list.classList.contains('u-d-none') && list.querySelectorAll('.signer-picker-group').length === 2, list.innerHTML.slice(0, 120));
    check('Membre BV étiqueté', list.textContent.includes('Équipe BV'), list.textContent);

    const form = doc.querySelector('[data-signer-form]');
    let submitted = 0;
    form.addEventListener('submit', (e) => { submitted++; e.preventDefault(); });
    key(w, q, 'ArrowDown');
    key(w, q, 'Enter');
    check('Entrée choisit le résultat surligné', doc.getElementById('fn').value === 'Claire' && doc.getElementById('mail').value === 'claire@alpha.fr', doc.getElementById('fn').value);
    check('Entrée ne soumet pas le formulaire', submitted === 0, String(submitted));
    check('Fiche contact liée', doc.querySelector('[data-signer-field="contact_id"]').value === '7' && doc.querySelector('[data-signer-field="user_id"]').value === '', doc.querySelector('[data-signer-field="contact_id"]').value);
    check('Bandeau « fiche liée » visible', !doc.querySelector('[data-signer-linked]').classList.contains('u-d-none') && doc.querySelector('[data-signer-linked-label]').textContent.includes('Claire Juriste'), doc.querySelector('[data-signer-linked-label]').textContent);
    check('Résultats refermés et recherche vidée', list.classList.contains('u-d-none') && q.value === '', q.value);

    typeIn(w, doc.getElementById('mail'), 'claire.perso@x.fr');
    check('Modifier l\'e-mail garde le lien', doc.querySelector('[data-signer-field="contact_id"]').value === '7', '');
    typeIn(w, doc.getElementById('ln'), 'Autre');
    check('Modifier le nom détache la fiche', doc.querySelector('[data-signer-field="contact_id"]').value === '' && doc.querySelector('[data-signer-linked]').classList.contains('u-d-none'), doc.querySelector('[data-signer-field="contact_id"]').value);

    // Choix d'un membre de l'équipe (clic)
    typeIn(w, q, 'cam');
    await sleep(260);
    list.querySelectorAll('[data-signer-option]')[1].dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    check('Membre BV : user_id renseigné, pas de contact', doc.querySelector('[data-signer-field="user_id"]').value === '3' && doc.querySelector('[data-signer-field="contact_id"]').value === '', doc.querySelector('[data-signer-field="user_id"]').value);
    check('Société vide non écrasée / non vide reprise', doc.getElementById('company').value === 'Belle Vitesse', doc.getElementById('company').value);

    doc.getElementById('unlink').click();
    check('Délier vide les identifiants', doc.querySelector('[data-signer-field="user_id"]').value === '', '');

    // Mode e-mail seul (invitation incident)
    const q2 = doc.getElementById('q2');
    typeIn(w, q2, 'claire');
    await sleep(260);
    doc.querySelector('#inc-results [data-signer-option]').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    check('Mode e-mail : seul le destinataire est rempli', doc.getElementById('incmail').value === 'claire@alpha.fr', doc.getElementById('incmail').value);
    check('Mode e-mail : sans project_id vide dans l\'URL', !w.__calls[w.__calls.length - 1].includes('project_id'), w.__calls[w.__calls.length - 1]);
  }

  {
    // Ouverture automatique depuis ?invite= et nettoyage des return_to
    const w = page('https://bv.test/admin/projects/1?invite=m1&tab=docs');
    await sleep(10);
    const modal = w.document.getElementById('m1');
    check('?invite=<id> ouvre la modale', modal.classList.contains('is-active'), modal.className);
    check('?invite retiré de l\'URL', !w.location.search.includes('invite') && w.location.search.includes('tab=docs'), w.location.search);
    const rt = w.document.querySelector('input[name="return_to"]').value;
    check('return_to nettoyé (pas de réouverture après envoi)', rt === '/admin/projects/1', rt);
  }

  process.exit(fails ? 1 : 0);
})();
