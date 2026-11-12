// Onglets de la page Indicateurs (indicators-tabs.js) : bascule sans rechargement, onglet reporté dans l'URL.
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const src = fs.readFileSync(path.join(__dirname, '../../static/js/src/admin/indicators-tabs.js'), 'utf8');
let fails = 0;
function check(name, cond, info) { console.log((cond ? 'OK  ' : 'FAIL') + ' ' + name + (cond ? '' : '  → ' + info)); if (!cond) fails++; }

const dom = new JSDOM(`<!doctype html><body>
<div role="tablist">
  <button id="tc" data-ind-tab="commercial" aria-selected="true">Commercial</button>
  <button id="te" data-ind-tab="equipment" aria-selected="false">Matériel</button>
</div>
<a id="l30" data-ind-period-link href="/admin/indicators?period=30d&tab=commercial">30 j</a>
<section id="pc" data-ind-panel="commercial">a</section>
<section id="pe" data-ind-panel="equipment" hidden>b</section>
</body>`, { runScripts: 'outside-only', url: 'https://bv.test/admin/indicators?period=12m' });
const w = dom.window;
w.eval(src);
const $ = (s) => w.document.querySelector(s);

$('#te').click();
check('panneau Matériel affiché', !$('#pe').hidden && $('#pc').hidden, '');
check('onglet Matériel sélectionné', $('#te').getAttribute('aria-selected') === 'true' && $('#tc').getAttribute('aria-selected') === 'false', '');
check('URL mise à jour (période conservée)', w.location.search === '?period=12m&tab=equipment', w.location.href);
check('lien de période reporte l’onglet', $('#l30').getAttribute('href') === '/admin/indicators?period=30d&tab=equipment', $('#l30').getAttribute('href'));

$('#te').dispatchEvent(new w.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
check('flèche droite : retour au premier onglet', !$('#pc').hidden && $('#pe').hidden, '');

console.log(fails ? `\n${fails} échec(s)` : '\nTous les tests passent');
process.exit(fails ? 1 : 0);
