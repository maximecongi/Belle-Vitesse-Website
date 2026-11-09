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
  return { w, ed: wrapper.querySelector('.notion-live-editor'), ta: wrapper.querySelector('textarea'), menu: wrapper.querySelector('.notion-slash-menu') };
}
function caret(w, node, off) { const r = w.document.createRange(); r.setStart(node, off); r.collapse(true); const s = w.getSelection(); s.removeAllRanges(); s.addRange(r); }
// Simule la frappe façon navigateur : insertion dans le nœud texte courant ou création d'un nœud
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
function key(w, ed, k, o = {}) { const ev = new w.KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...o }); ed.dispatchEvent(ev); }
function blur(w, ed) { ed.dispatchEvent(new w.Event('blur')); }
function check(name, cond, info) { console.log((cond ? 'OK  ' : 'FAIL') + ' ' + name + (cond ? '' : '  → ' + info)); if (!cond) fails++; }

// A. Éditeur vide : "/" ouvre le menu, la commande s'applique
{ const { w, ed, ta, menu } = mk('');
  caret(w, ed, 0); type(w, ed, '/');
  check('Éditeur vide : « / » ouvre le menu', menu.classList.contains('is-open'), ed.innerHTML);
  type(w, ed, 'citation'); key(w, ed, 'Enter'); type(w, ed, 'Note');  blur(w, ed);
  check('Éditeur vide : /citation crée une citation', ta.value === '> Note', JSON.stringify(ta.value) + ' ' + ed.innerHTML); }

// B. Ligne vide sous une citation : le format s'applique à la bonne ligne
{ const { w, ed, ta } = mk('<blockquote>Citation</blockquote><p><br></p>');
  caret(w, ed.querySelector('p'), 0); type(w, ed, '/puce'); key(w, ed, 'Enter'); type(w, ed, 'item'); blur(w, ed);
  check('Ligne du dessous : la citation reste intacte', ta.value === '> Citation\n\n- item', JSON.stringify(ta.value) + ' ' + ed.innerHTML); }

// B2. Ligne vide sous un paragraphe, /titre
{ const { w, ed, ta } = mk('<p>Intro</p><p><br></p>');
  caret(w, ed.querySelectorAll('p')[1], 0); type(w, ed, '/titre'); key(w, ed, 'Enter'); type(w, ed, 'Section'); blur(w, ed);
  check('Ligne du dessous : /titre ne touche pas « Intro »', ta.value === 'Intro\n\n## Section', JSON.stringify(ta.value) + ' ' + ed.innerHTML); }

// C. Éditeur vide : raccourci "## "
{ const { w, ed, ta } = mk('');
  caret(w, ed, 0); type(w, ed, '## '); type(w, ed, 'Titre'); blur(w, ed);
  check('Éditeur vide : « ## » crée un titre', ta.value === '## Titre', JSON.stringify(ta.value) + ' ' + ed.innerHTML); }

// D. Commande en fin de ligne non vide
{ const { w, ed, ta } = mk('<p>Texte</p>');
  const t = ed.querySelector('p').firstChild; caret(w, t, 5); type(w, ed, ' /citation'); key(w, ed, 'Enter'); blur(w, ed);
  check('Ligne non vide : /citation transforme la ligne', ta.value === '> Texte', JSON.stringify(ta.value) + ' ' + ed.innerHTML); }

// E. Re-cliquer sur citation = retour texte normal ; puces ↔ numéros
{ const { w, ed, ta } = mk('<blockquote>Q</blockquote>');
  caret(w, ed.querySelector('blockquote').firstChild, 1); type(w, ed, ' /citation'); key(w, ed, 'Enter'); blur(w, ed);
  check('Citation + /citation → texte normal', ta.value === 'Q', JSON.stringify(ta.value)); }
{ const { w, ed, ta } = mk('<ul><li>a</li><li>b</li></ul>');
  caret(w, ed.querySelectorAll('li')[1].firstChild, 1); type(w, ed, ' /num'); key(w, ed, 'Enter'); blur(w, ed);
  check('Puces → liste numérotée', ta.value === '1. a\n1. b', JSON.stringify(ta.value) + ' ' + ed.innerHTML); }
{ const { w, ed, ta } = mk('<ul><li>a</li><li>b</li><li>c</li></ul>');
  caret(w, ed.querySelectorAll('li')[1].firstChild, 1); type(w, ed, ' /titre'); key(w, ed, 'Enter'); blur(w, ed);
  check('Élément de liste → titre (liste coupée)', ta.value === '- a\n\n## b\n\n- c', JSON.stringify(ta.value) + ' ' + ed.innerHTML); }

// F. Séparateur et code sur ligne vide
{ const { w, ed, ta } = mk('<p>Haut</p><p><br></p>');
  caret(w, ed.querySelectorAll('p')[1], 0); type(w, ed, '/sépar'); key(w, ed, 'Enter'); type(w, ed, 'Bas'); blur(w, ed);
  check('Séparateur sur ligne vide', ta.value === 'Haut\n\n---\n\nBas', JSON.stringify(ta.value) + ' ' + ed.innerHTML); }
{ const { w, ed, ta } = mk('<p>Haut</p><p><br></p>');
  caret(w, ed.querySelectorAll('p')[1], 0); type(w, ed, '/code'); key(w, ed, 'Enter'); type(w, ed, 'x=1'); blur(w, ed);
  check('Bloc de code sur ligne vide', ta.value === 'Haut\n\n```\nx=1\n```', JSON.stringify(ta.value) + ' ' + ed.innerHTML); }

process.exit(fails ? 1 : 0);
