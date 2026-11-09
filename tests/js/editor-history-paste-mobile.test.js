const fs = require('fs');
const { JSDOM } = require('jsdom');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '../../static/js/src/admin/notion-editor.js'), 'utf8');
let fails = 0;
function mk(html) {
  const dom = new JSDOM(`<!doctype html><body><form><div class="notion-wysiwyg-wrapper" id="w">
<textarea name="content"></textarea><div class="notion-slash-container"><div class="notion-slash-menu"></div><div class="notion-context-menu"></div>
<div class="notion-live-editor" contenteditable="true">${html}</div></div></div></form></body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  w.document.execCommand = () => true; w.HTMLElement.prototype.scrollIntoView = () => {};
  w.eval(src);
  const wrapper = w.document.getElementById('w');
  const api = w.initNotionEditor(wrapper);
  return { w, api, ed: wrapper.querySelector('.notion-live-editor'), ta: wrapper.querySelector('textarea'), menu: wrapper.querySelector('.notion-slash-menu'), cm: wrapper.querySelector('.notion-context-menu') };
}
function caret(w, node, off) { const r = w.document.createRange(); r.setStart(node, off); r.collapse(true); const s = w.getSelection(); s.removeAllRanges(); s.addRange(r); }
function select(w, node, a, b) { const r = w.document.createRange(); r.setStart(node, a); r.setEnd(node, b); const s = w.getSelection(); s.removeAllRanges(); s.addRange(r); }
function type(w, ed, t) {
  for (const ch of t) {
    const r = w.getSelection().getRangeAt(0); let n = r.startContainer, off = r.startOffset;
    if (n.nodeType === 3) { n.insertData(off, ch); caret(w, n, off + 1); }
    else { const tn = w.document.createTextNode(ch); const ref = n.childNodes[off] || null;
      if (ref && ref.nodeName === 'BR' && n.childNodes.length === 1) ref.remove();
      n.insertBefore(tn, n.childNodes[off] || null); caret(w, tn, 1); }
    ed.dispatchEvent(new w.InputEvent('input', { bubbles: true }));
  }
}
function key(w, ed, k, o = {}) { const ev = new w.KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...o }); ed.dispatchEvent(ev); return ev; }
function before(w, ed, inputType, data) { const ev = new w.InputEvent('beforeinput', { inputType, data, bubbles: true, cancelable: true }); ed.dispatchEvent(ev); return ev; }
function paste(w, ed, map) { const ev = new w.Event('paste', { bubbles: true, cancelable: true }); ev.clipboardData = { getData: (t) => map[t] || '' }; ed.dispatchEvent(ev); return ev; }
const md = (w, ed, ta) => { ed.dispatchEvent(new w.Event('blur')); return ta.value; };
function check(name, cond, info) { console.log((cond ? 'OK  ' : 'FAIL') + ' ' + name + (cond ? '' : '  → ' + info)); if (!cond) fails++; }
const undoKey = (w, ed) => key(w, ed, 'z', { metaKey: true });
const redoKey = (w, ed) => key(w, ed, 'z', { metaKey: true, shiftKey: true });

// ── Historique ──
{ const { w, ed, ta } = mk('');
  caret(w, ed, 0); type(w, ed, '## '); type(w, ed, 'Titre');
  check('⌘Z : « ## Titre » tapé', md(w, ed, ta) === '## Titre', md(w, ed, ta));
  undoKey(w, ed); check('⌘Z #1 : titre vide', !!ed.querySelector('h2') && md(w, ed, ta) === '##', ed.innerHTML);
  undoKey(w, ed); check('⌘Z #2 : « ## » redevient du texte', !ed.querySelector('h2') && ed.textContent.includes('##'), ed.innerHTML);
  redoKey(w, ed); redoKey(w, ed); check('⌘⇧Z ×2 : on retrouve « ## Titre »', md(w, ed, ta) === '## Titre', md(w, ed, ta)); }
{ const { w, ed, ta } = mk('<blockquote>Obs</blockquote>');
  caret(w, ed.querySelector('blockquote').firstChild, 3); key(w, ed, 'Enter');
  check('Sortie de citation effectuée', ed.children.length === 2, ed.innerHTML);
  undoKey(w, ed); check('⌘Z annule la sortie de citation', ed.children.length === 1 && ed.firstElementChild.tagName === 'BLOCKQUOTE', ed.innerHTML); }
{ const { w, ed, ta } = mk('<p>Texte</p>');
  caret(w, ed.querySelector('p').firstChild, 5); type(w, ed, ' /citation'); key(w, ed, 'Enter');
  check('/citation appliquée', md(w, ed, ta) === '> Texte', md(w, ed, ta));
  undoKey(w, ed); check('⌘Z annule /citation (texte conservé, sans « / »)', md(w, ed, ta) === 'Texte', JSON.stringify(md(w, ed, ta)));
  redoKey(w, ed); check('⌘⇧Z la rétablit', md(w, ed, ta) === '> Texte', md(w, ed, ta)); }
{ const { w, ed, ta } = mk('<p>a</p>');
  caret(w, ed.querySelector('p').firstChild, 1);
  const ev = before(w, ed, 'historyUndo'); check('beforeinput historyUndo intercepté (mobile / menu Édition)', ev.defaultPrevented, ''); }

// ── Listes : Tab ──
{ const { w, ed, ta } = mk('<ul><li>a</li><li>b</li><li>c</li></ul>');
  caret(w, ed.querySelectorAll('li')[1].firstChild, 1); key(w, ed, 'Tab');
  check('Tab indente', md(w, ed, ta) === '- a\n    - b\n- c', JSON.stringify(md(w, ed, ta)));
  key(w, ed, 'Tab', { shiftKey: true });
  check('Maj+Tab désindente', md(w, ed, ta) === '- a\n- b\n- c', JSON.stringify(md(w, ed, ta)));
  caret(w, ed.querySelectorAll('li')[0].firstChild, 1); const ev = key(w, ed, 'Tab');
  check('Tab sur le 1er élément : pas de sortie du champ', ev.defaultPrevented && md(w, ed, ta) === '- a\n- b\n- c', md(w, ed, ta)); }
{ const { w, ed, ta } = mk('<ul><li>a<ul><li>b</li><li>c</li></ul></li></ul>');
  caret(w, ed.querySelectorAll('li')[1].firstChild, 1); key(w, ed, 'Tab', { shiftKey: true });
  check('Maj+Tab garde l\'ordre (c devient enfant de b)', md(w, ed, ta) === '- a\n- b\n    - c', JSON.stringify(md(w, ed, ta))); }
{ const { w, ed } = mk('<p>x</p>');
  caret(w, ed.querySelector('p').firstChild, 1);
  check('Tab hors liste : comportement natif (navigation)', !key(w, ed, 'Tab').defaultPrevented, ''); }

// ── Collage ──
{ const { w, ed, ta } = mk('<p><br></p>');
  caret(w, ed.querySelector('p'), 0);
  paste(w, ed, { 'text/html': '<meta charset="utf-8"><b style="font-weight:normal;" id="docs-internal-guid-1"><p dir="ltr"><span style="font-weight:700">Gras</span><span> normal</span></p><h1><span>Grand titre</span></h1><ul><li><p><span>un</span></p></li></ul><table><tr><td>A</td><td>B</td></tr></table><img src="x"><script>alert(1)</script></b>', 'text/plain': 'ignored' });
  check('Collage Google Docs nettoyé', md(w, ed, ta) === '**Gras** normal\n\n## Grand titre\n\n- un\n\nA | B', JSON.stringify(md(w, ed, ta)) + ' ' + ed.innerHTML);
  check('Pas de style ni script conservé', !/style=|<script|<img|<span/.test(ed.innerHTML), ed.innerHTML);
  undoKey(w, ed); check('⌘Z annule le collage', md(w, ed, ta) === '', JSON.stringify(md(w, ed, ta))); }
{ const { w, ed, ta } = mk('<p>AvantApres</p>');
  caret(w, ed.querySelector('p').firstChild, 5); paste(w, ed, { 'text/plain': 'x\n\ny' });
  check('Texte brut multi-paragraphes coupé au curseur', md(w, ed, ta) === 'Avant\n\nx\n\ny\n\nApres', JSON.stringify(md(w, ed, ta))); }
{ const { w, ed, ta } = mk('<p>ab</p>');
  caret(w, ed.querySelector('p').firstChild, 1); paste(w, ed, { 'text/plain': 'ZZ' });
  check('Texte brut sur une ligne inséré en ligne', md(w, ed, ta) === 'aZZb', md(w, ed, ta)); }
{ const { w, ed, ta } = mk('<p>voir site</p>');
  select(w, ed.querySelector('p').firstChild, 5, 9); paste(w, ed, { 'text/plain': 'https://x.fr' });
  check('URL collée sur une sélection → lien', md(w, ed, ta) === 'voir [site](https://x.fr)', md(w, ed, ta)); }
{ const { w, ed, ta } = mk('<p>Avant</p><p>Fin</p>');
  caret(w, ed.querySelector('p').firstChild, 5); paste(w, ed, { 'text/html': '<p>Lien <a href="javascript:alert(1)">piège</a> et <a href="https://ok.fr">ok</a></p><blockquote><p>Cité</p></blockquote>' });
  check('Liens javascript: retirés, citation conservée', md(w, ed, ta) === 'Avant\n\nLien piège et [ok](https://ok.fr)\n\n> Cité\n\nFin', JSON.stringify(md(w, ed, ta))); }
{ const { w, ed, ta } = mk('<pre><code>x</code></pre>');
  caret(w, ed.querySelector('code').firstChild, 1); paste(w, ed, { 'text/html': '<b>y</b>', 'text/plain': 'y\nz' });
  check('Collage dans un bloc de code : texte brut', md(w, ed, ta) === '```\nxy\nz\n```', JSON.stringify(md(w, ed, ta))); }

// ── Liens ⌘K ──
{ const { w, ed, ta } = mk('<p>voir site</p>');
  w.prompt = () => 'exemple.fr';
  select(w, ed.querySelector('p').firstChild, 5, 9); key(w, ed, 'k', { metaKey: true });
  check('⌘K crée un lien (https ajouté)', md(w, ed, ta) === 'voir [site](https://exemple.fr)', md(w, ed, ta));
  caret(w, ed.querySelector('a').firstChild, 2); w.prompt = () => '';
  key(w, ed, 'k', { metaKey: true });
  check('⌘K + adresse vide retire le lien', md(w, ed, ta) === 'voir site', md(w, ed, ta)); }
{ const { w, ed, ta } = mk('<p>a</p>');
  w.prompt = () => 'pas une url'; let alerted = false; w.alert = () => { alerted = true; };
  caret(w, ed.querySelector('p').firstChild, 1); key(w, ed, 'k', { metaKey: true });
  check('Adresse invalide refusée', alerted && md(w, ed, ta) === 'a', md(w, ed, ta)); }
{ const { w, ed, ta } = mk('<p>Texte</p>');
  w.prompt = () => 'contact@bv.fr';
  caret(w, ed.querySelector('p').firstChild, 5); type(w, ed, ' /lien'); key(w, ed, 'Enter');
  check('/lien sans sélection insère l\'adresse en lien mailto', md(w, ed, ta) === 'Texte [contact@bv.fr](mailto:contact@bv.fr)', JSON.stringify(md(w, ed, ta))); }

// ── Mobile ──
{ const { w, ed, ta } = mk('<blockquote>Obs</blockquote>');
  caret(w, ed.querySelector('blockquote').firstChild, 3);
  const ev = before(w, ed, 'insertParagraph');
  check('Android (beforeinput) : Entrée sort de la citation', ev.defaultPrevented && ed.children.length === 2 && ed.lastElementChild.tagName === 'P', ed.innerHTML); }
{ const { w, ed, ta } = mk('<blockquote>Obs</blockquote>');
  caret(w, ed.querySelector('blockquote').firstChild, 0);
  before(w, ed, 'deleteContentBackward');
  check('Android (beforeinput) : ⌫ en début retire la citation', !ed.querySelector('blockquote'), ed.innerHTML); }
{ const { w, ed, ta, menu } = mk('<p>x</p>');
  caret(w, ed.querySelector('p').firstChild, 1); type(w, ed, ' /citation');
  before(w, ed, 'insertParagraph');
  check('Android : Entrée du clavier valide la commande « / »', md(w, ed, ta) === '> x' && !menu.classList.contains('is-open'), md(w, ed, ta)); }
{ const { w, ed, ta, menu } = mk('<p>mot</p>');
  select(w, ed.querySelector('p').firstChild, 0, 3);
  const ev = before(w, ed, 'insertText', '/');
  check('Mobile : « / » sur une sélection ouvre le menu sans effacer', ev.defaultPrevented && menu.classList.contains('is-open') && ed.textContent === 'mot', ed.innerHTML); }
{ const { w, ed, ta, menu } = mk('<p>x</p>');
  caret(w, ed.querySelector('p').firstChild, 1); type(w, ed, ' /cita');
  const item = menu.querySelector('.notion-slash-item');
  const pd = new w.Event('pointerdown', { bubbles: true, cancelable: true }); item.dispatchEvent(pd);
  item.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true }));
  check('Tap sur une commande du menu (pointerdown sans perte de focus + click)', pd.defaultPrevented && md(w, ed, ta) === '> x', md(w, ed, ta)); }
{ const { w, ed, cm } = mk('<p>x</p>');
  const pd = new w.Event('pointerdown', { bubbles: true }); pd.pointerType = 'touch'; ed.dispatchEvent(pd);
  const ev = new w.MouseEvent('contextmenu', { bubbles: true, cancelable: true }); ed.dispatchEvent(ev);
  check('Appui long tactile : menu natif conservé', !ev.defaultPrevented && !cm.classList.contains('is-open'), '');
  const pd2 = new w.Event('pointerdown', { bubbles: true }); pd2.pointerType = 'mouse'; ed.dispatchEvent(pd2);
  const ev2 = new w.MouseEvent('contextmenu', { bubbles: true, cancelable: true }); ed.dispatchEvent(ev2);
  check('Clic droit souris : menu personnalisé', ev2.defaultPrevented && cm.classList.contains('is-open'), ''); }

process.exit(fails ? 1 : 0);
