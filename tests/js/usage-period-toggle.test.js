// Bascule de période du classement « Jours utilisés par matériel » (usage-period-toggle.js), sans rechargement.
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const src = fs.readFileSync(path.join(__dirname, '../../static/js/src/admin/usage-period-toggle.js'), 'utf8');
let fails = 0;
function check(name, cond, info) { console.log((cond ? 'OK  ' : 'FAIL') + ' ' + name + (cond ? '' : '  → ' + info)); if (!cond) fails++; }

const dom = new JSDOM(`<!doctype html><body>
<div data-usage-period-root>
  <button id="b30" data-usage-period="30d" aria-pressed="true" class="admin-btn admin-btn-primary">30 j</button>
  <button id="by" data-usage-period="year" aria-pressed="false" class="admin-btn admin-btn-quaternary">Année</button>
  <div id="p30" data-usage-period-panel="30d">a</div>
  <div id="py" data-usage-period-panel="year" hidden>b</div>
</div></body>`, { runScripts: 'outside-only', url: 'https://bv.test/admin/fleet' });
const w = dom.window;
w.eval(src);
const $ = (s) => w.document.querySelector(s);

$('#by').click();
check('panneau année affiché', !$('#py').hidden && $('#p30').hidden, '');
check('bouton année actif', $('#by').classList.contains('admin-btn-primary') && $('#by').getAttribute('aria-pressed') === 'true', $('#by').className);
check('bouton 30 j inactif', $('#b30').classList.contains('admin-btn-quaternary') && !$('#b30').classList.contains('admin-btn-primary'), $('#b30').className);
check('URL mise à jour sans rechargement', w.location.search === '?usage_period=year', w.location.href);
$('#b30').click();
check('retour aux 30 jours', !$('#p30').hidden && $('#py').hidden, '');

console.log(fails ? `\n${fails} échec(s)` : '\nTous les tests passent');
process.exit(fails ? 1 : 0);
