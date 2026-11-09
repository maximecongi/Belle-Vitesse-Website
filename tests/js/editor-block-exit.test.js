const fs = require('fs');
const { JSDOM } = require('jsdom');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '../../static/js/src/admin/notion-editor.js'), 'utf8');
let fails = 0;
function mk(html) {
  const dom = new JSDOM(`<!doctype html><body><form><div class="notion-wysiwyg-wrapper" id="w">
<textarea name="content"></textarea><div class="notion-slash-container"><div class="notion-slash-menu"></div>
<div class="notion-live-editor" contenteditable="true">${html}</div></div></div></form></body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  w.document.execCommand = () => true; w.HTMLElement.prototype.scrollIntoView = () => {};
  w.eval(src);
  const wrapper = w.document.getElementById('w');
  w.initNotionEditor(wrapper);
  const ed = wrapper.querySelector('.notion-live-editor');
  return { w, ed, ta: wrapper.querySelector('textarea') };
}
function caret(w, node, off) { const r = w.document.createRange(); r.setStart(node, off); r.collapse(true); const s = w.getSelection(); s.removeAllRanges(); s.addRange(r); }
function key(w, ed, k, opts = {}) { const ev = new w.KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...opts }); ed.dispatchEvent(ev); return ev.defaultPrevented; }
function type(w, t) { const r = w.getSelection().getRangeAt(0); const n = w.document.createTextNode(t); r.insertNode(n); caret(w, n, t.length); }
function check(name, cond, info) { console.log((cond ? 'OK  ' : 'FAIL') + ' ' + name + (cond ? '' : '  → ' + info)); if (!cond) fails++; }

// 1. Entrée en fin de citation → paragraphe normal, on tape du texte
{ const { w, ed, ta } = mk('<blockquote>Observation</blockquote>');
  const t = ed.querySelector('blockquote').firstChild; caret(w, t, t.length);
  key(w, ed, 'Enter'); type(w, 'Texte normal'); ed.dispatchEvent(new w.Event('blur'));
  check('Entrée sort de la citation', ta.value === '> Observation\n\nTexte normal', JSON.stringify(ta.value) + ' ' + ed.innerHTML); }

// 2. Citation rendue serveur (<blockquote><p>) 
{ const { w, ed, ta } = mk('<blockquote>\n<p>Obs serveur</p>\n</blockquote>');
  const t = ed.querySelector('blockquote p').firstChild; caret(w, t, t.length);
  key(w, ed, 'Enter'); type(w, 'Suite'); ed.dispatchEvent(new w.Event('blur'));
  check('Entrée sort d\'une citation rendue serveur', ta.value === '> Obs serveur\n\nSuite', JSON.stringify(ta.value) + ' ' + ed.innerHTML); }

// 3. Entrée au milieu → coupe
{ const { w, ed, ta } = mk('<blockquote>AvantApres</blockquote>');
  caret(w, ed.querySelector('blockquote').firstChild, 5); key(w, ed, 'Enter'); ed.dispatchEvent(new w.Event('blur'));
  check('Entrée au milieu coupe la citation', ta.value === '> Avant\n\nApres', JSON.stringify(ta.value)); }

// 4. Maj+Entrée reste dans la citation (natif → non intercepté)
{ const { w, ed } = mk('<blockquote>Ligne</blockquote>');
  caret(w, ed.querySelector('blockquote').firstChild, 5);
  check('Maj+Entrée non intercepté', key(w, ed, 'Enter', { shiftKey: true }) === false, ''); }

// 5. Citation vide (créée par "> ") + Entrée → paragraphe
{ const { w, ed, ta } = mk('<p>a</p><blockquote>​</blockquote>');
  caret(w, ed.querySelector('blockquote').firstChild, 1); key(w, ed, 'Enter');
  check('Entrée sur citation vide → paragraphe', !ed.querySelector('blockquote') && ed.lastElementChild.tagName === 'P', ed.innerHTML); }

// 6. Titre : Entrée en fin
{ const { w, ed, ta } = mk('<h2>Titre</h2>');
  const t = ed.querySelector('h2').firstChild; caret(w, t, t.length); key(w, ed, 'Enter'); type(w, 'Corps'); ed.dispatchEvent(new w.Event('blur'));
  check('Entrée sort du titre', ta.value === '## Titre\n\nCorps', JSON.stringify(ta.value)); }

// 7. Retour arrière en début de citation → texte normal
{ const { w, ed, ta } = mk('<blockquote>Garde moi</blockquote>');
  caret(w, ed.querySelector('blockquote').firstChild, 0); key(w, ed, 'Backspace'); ed.dispatchEvent(new w.Event('blur'));
  check('Retour arrière défait la citation', ta.value === 'Garde moi' && !ed.querySelector('blockquote'), JSON.stringify(ta.value)); }

// 8. Flèche bas en fin de dernier bloc formaté
{ const { w, ed } = mk('<blockquote>Fin</blockquote>');
  caret(w, ed.querySelector('blockquote').firstChild, 3); key(w, ed, 'ArrowDown');
  check('Flèche bas crée une ligne normale', ed.lastElementChild.tagName === 'P', ed.innerHTML); }

// 9. Code : Entrée = nouvelle ligne, Entrée sur ligne vide = sortie
{ const { w, ed, ta } = mk('<pre><code>x=1</code></pre>');
  caret(w, ed.querySelector('code').firstChild, 3); key(w, ed, 'Enter');
  const inPre = ed.querySelector('pre') && ed.childElementCount === 1;
  key(w, ed, 'Enter'); type(w, 'après'); ed.dispatchEvent(new w.Event('blur'));
  check('Code : 1re Entrée reste dans le bloc', inPre, ed.innerHTML);
  check('Code : 2e Entrée sort', ta.value === '```\nx=1\n```\n\naprès', JSON.stringify(ta.value) + ' ' + ed.innerHTML); }

// 10. Listes : non interceptées (comportement natif)
{ const { w, ed } = mk('<ul><li>a</li></ul>');
  caret(w, ed.querySelector('li').firstChild, 1);
  check('Liste : Entrée native', key(w, ed, 'Enter') === false, ''); }

process.exit(fails ? 1 : 0);
