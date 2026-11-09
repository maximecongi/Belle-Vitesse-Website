/**
 * notion-editor.js — Éditeur WYSIWYG Notion-style (rapports d'équipe).
 * Markup : templates/admin/_notion_editor.html — initialisation : initNotionEditor(wrapper).
 * Le contenu est sérialisé en Markdown dans le <textarea name="content"> du conteneur.
 */

// ── Fonctions utilitaires pour l'éditeur WYSIWYG Notion ──────────────

function escapeEditorHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// ── Éditeur WYSIWYG Notion-Style directement éditable ──────────────

const NOTION_SLASH_COMMANDS = [
    { id: 'clear', title: 'Texte normal (sans format)', desc: 'Supprimer la mise en forme du texte ou bloc', icon: '🧹', hint: 'p' },
    { id: 'bullet', title: 'Liste à puces', desc: 'Créer une liste à puces simple', icon: '•', hint: '-' },
    { id: 'numbered', title: 'Liste numérotée', desc: 'Créer une liste ordonnée', icon: '1.', hint: '1.' },
    { id: 'h2', title: 'Titre de section', desc: 'Grand titre de section', icon: '🏷️', hint: '##' },
    { id: 'h3', title: 'Sous-titre', desc: 'Sous-titre ou étape', icon: '📌', hint: '###' },
    { id: 'quote', title: 'Citation / Observation', desc: 'Observation ou débriefing plateau', icon: '💬', hint: '>' },
    { id: 'callout', title: 'Point d’attention', desc: 'Remarque importante avec icône', icon: '💡', hint: '> 💡' },
    { id: 'bold', title: 'Gras', desc: 'Mettre le texte en gras', icon: '𝐁', hint: '**' },
    { id: 'italic', title: 'Italique', desc: 'Mettre le texte en italique', icon: '𝐼', hint: '*' },
    { id: 'link', title: 'Lien', desc: 'Ajouter ou modifier un lien web', icon: '🔗', hint: '⌘K' },
    { id: 'code', title: 'Bloc de données / Paramètres', desc: 'Données techniques ou code', icon: '💻', hint: '```' },
    { id: 'divider', title: 'Séparateur horizontal', desc: 'Ligne de séparation visuelle', icon: '➖', hint: '---' },
];

function nodeToMarkdown(node) {
    if (!node) return '';

    if (node.nodeType === Node.TEXT_NODE) {
        const text = node.textContent.replace(/\u200B/g, '');
        const parent = node.parentElement;
        // Dans un bloc de code, les retours à la ligne sont significatifs
        if (parent && parent.closest('pre')) return text;
        // Les blancs de mise en forme du HTML rendu côté serveur (entre blocs) ne portent pas de contenu
        if (!text.trim() && parent && (
            ['UL', 'OL', 'BLOCKQUOTE'].includes(parent.tagName) ||
            parent.classList.contains('notion-live-editor')
        )) {
            return '';
        }
        // Les sauts de ligne bruts du HTML sont des espaces ; les vrais retours viennent des <br>
        return text.replace(/\s+/g, (ws) => (ws.includes('\n') ? ' ' : ws));
    }

    if (node.nodeType !== Node.ELEMENT_NODE) {
        return '';
    }

    if (node.classList && (node.classList.contains('notion-slash-menu') || node.classList.contains('notion-context-menu'))) {
        return '';
    }

    const tag = node.tagName.toLowerCase();

    let inner = '';
    for (const child of node.childNodes) {
        inner += nodeToMarkdown(child);
    }

    switch (tag) {
        case 'h1':
        case 'h2':
            return `\n## ${inner.trim()}\n`;
        case 'h3':
            return `\n### ${inner.trim()}\n`;
        case 'h4':
            return `\n#### ${inner.trim()}\n`;
        case 'blockquote': {
            const lines = inner.trim().split('\n').filter((l) => l.trim());
            return '\n' + lines.map((l) => `> ${l.trim()}`).join('\n') + '\n';
        }
        case 'strong':
        case 'b':
            return `**${inner}**`;
        case 'em':
        case 'i':
            return `*${inner}*`;
        case 'code':
            if (node.parentElement && node.parentElement.tagName.toLowerCase() === 'pre') {
                return inner;
            }
            return `\`${inner}\``;
        case 'pre':
            return `\n\`\`\`\n${inner.trim()}\n\`\`\`\n`;
        case 'a': {
            const href = node.getAttribute('href');
            if (!href || !inner.trim()) return inner;
            return inner.trim() === href ? `<${href}>` : `[${inner}](${href})`;
        }
        case 'hr':
            return '\n---\n';
        case 'br':
            return '\n';
        case 'li': {
            const isOl = node.parentElement && node.parentElement.tagName.toLowerCase() === 'ol';
            // Sous-listes : indentées de 4 espaces (exigence de Python-Markdown)
            let own = '';
            let nested = '';
            for (const child of node.childNodes) {
                const isList = child.nodeType === Node.ELEMENT_NODE && ['UL', 'OL'].includes(child.tagName);
                if (isList) nested += nodeToMarkdown(child);
                else own += nodeToMarkdown(child);
            }
            let out = `${isOl ? '1. ' : '- '}${own.trim().replace(/\n/g, '\n    ')}\n`;
            if (nested.trim()) {
                out += nested.trim().split('\n').filter((l) => l.trim()).map((l) => `    ${l}`).join('\n') + '\n';
            }
            return out;
        }
        case 'ul':
        case 'ol':
            return `\n${inner}\n`;
        case 'p':
        case 'div': {
            if (!inner.trim()) return '';
            return `\n${inner.trim()}\n`;
        }
        default:
            return inner;
    }
}

function editorToMarkdown(editor) {
    if (!editor) return '';
    let md = '';
    for (const child of editor.childNodes) {
        md += nodeToMarkdown(child);
    }
    return md.replace(/\n{3,}/g, '\n\n').trim();
}

/**
 * Initialise un éditeur Notion-style à partir de son conteneur `.notion-wysiwyg-wrapper`
 * (markup généré par la macro `notion_report_editor`). Idempotent.
 * Retourne une API { sync, reset, focusEnd }.
 */
function initNotionEditor(wrapper) {
    if (!wrapper) return null;
    if (wrapper._notionEditor) return wrapper._notionEditor;

    const editor = wrapper.querySelector('.notion-live-editor');
    const hiddenInput = wrapper.querySelector('textarea[name="content"]');
    const menu = wrapper.querySelector('.notion-slash-menu');
    const contextMenu = wrapper.querySelector('.notion-context-menu');
    if (!editor || !hiddenInput || !menu) return null;

    const initialHTML = editor.innerHTML;

    let isSlashOpen = false;
    let slashRangeInfo = null;
    let savedSelectionRange = null;
    let filteredCommands = [...NOTION_SLASH_COMMANDS];
    let activeIndex = 0;

    // Mémoriser la sélection courante dans l'éditeur
    function saveCurrentSelection() {
        const sel = window.getSelection();
        if (sel && sel.rangeCount > 0) {
            const r = sel.getRangeAt(0);
            if (editor.contains(r.commonAncestorContainer)) {
                savedSelectionRange = r.cloneRange();
                return savedSelectionRange;
            }
        }
        return null;
    }

    editor.addEventListener('mouseup', saveCurrentSelection);
    editor.addEventListener('keyup', saveCurrentSelection);

    // Gestion du focus pour effacer immédiatement le placeholder dès la sélection
    editor.addEventListener('focus', () => {
        editor.classList.add('is-focused');
    });

    editor.addEventListener('blur', () => {
        editor.classList.remove('is-focused');
        syncToHidden();
    });

    // Synchronisation vers le champ formulaire
    function syncToHidden() {
        const md = editorToMarkdown(editor);
        hiddenInput.value = md;
        const textOnly = editor.textContent.replace(/\u200B/g, '').trim();
        const isEmpty = !textOnly;
        editor.setAttribute('data-empty', isEmpty ? 'true' : 'false');
    }

    function setCursorAt(node, offset = 0) {
        const range = document.createRange();
        const sel = window.getSelection();
        if (node.nodeType === Node.TEXT_NODE) {
            range.setStart(node, Math.min(offset, node.textContent.length));
        } else {
            range.selectNodeContents(node);
            range.collapse(false);
        }
        range.collapse(true);
        sel.removeAllRanges();
        sel.addRange(range);
        editor.focus();
    }

    // ── Historique interne (⌘Z / ⌘⇧Z) ───────────────────────────
    // Les transformations faites en DOM direct échappent à l'historique natif du navigateur :
    // l'éditeur gère donc lui-même un historique d'instantanés (HTML + position du curseur).
    const HISTORY_LIMIT = 100;
    const TYPING_PAUSE_MS = 700;
    const TYPING_MAX_MS = 3000;
    let historyStack = [];
    let historyIndex = -1;
    let typingTimer = null;
    let typingBurstStart = 0;

    function nodePath(node) {
        const path = [];
        let n = node;
        while (n && n !== editor) {
            const parent = n.parentNode;
            if (!parent) return null;
            path.unshift(Array.prototype.indexOf.call(parent.childNodes, n));
            n = parent;
        }
        return n === editor ? path : null;
    }

    function nodeFromPath(path) {
        if (!path) return null;
        let n = editor;
        for (const i of path) {
            n = n.childNodes[i];
            if (!n) return null;
        }
        return n;
    }

    function takeSnapshot() {
        const sel = window.getSelection();
        let caret = null;
        if (sel && sel.rangeCount && editor.contains(sel.getRangeAt(0).startContainer)) {
            const r = sel.getRangeAt(0);
            caret = { path: nodePath(r.startContainer), offset: r.startOffset };
        }
        return { html: editor.innerHTML, caret };
    }

    function pushSnapshot(snap) {
        clearTimeout(typingTimer);
        typingTimer = null;
        typingBurstStart = 0;
        const current = historyStack[historyIndex];
        if (current && current.html === snap.html) {
            if (snap.caret) current.caret = snap.caret;
            return;
        }
        historyStack = historyStack.slice(0, historyIndex + 1);
        historyStack.push(snap);
        if (historyStack.length > HISTORY_LIMIT) historyStack.shift();
        historyIndex = historyStack.length - 1;
    }

    function recordHistory() {
        pushSnapshot(takeSnapshot());
    }

    // Frappe continue : un pas d'annulation par pause (ou toutes les 3 s au maximum)
    function scheduleHistory() {
        const now = Date.now();
        if (!typingBurstStart) typingBurstStart = now;
        clearTimeout(typingTimer);
        if (now - typingBurstStart >= TYPING_MAX_MS) {
            recordHistory();
            return;
        }
        typingTimer = setTimeout(recordHistory, TYPING_PAUSE_MS);
    }

    // Exécute une transformation en l'encadrant de deux instantanés
    function withHistory(fn) {
        recordHistory();
        const result = fn();
        recordHistory();
        return result;
    }

    function applySnapshot(snap) {
        closeMenu();
        if (contextMenu) contextMenu.classList.remove('is-open');
        editor.innerHTML = snap.html;
        const node = snap.caret ? nodeFromPath(snap.caret.path) : null;
        if (!(node && restoreCaret({ node, offset: snap.caret.offset }))) {
            placeCaretAtEnd(editor.lastElementChild || editor);
        }
        editor.focus();
        syncToHidden();
    }

    function undo() {
        recordHistory();
        if (historyIndex <= 0) return;
        historyIndex -= 1;
        applySnapshot(historyStack[historyIndex]);
    }

    function redo() {
        recordHistory();
        if (historyIndex >= historyStack.length - 1) return;
        historyIndex += 1;
        applySnapshot(historyStack[historyIndex]);
    }

    function resetHistory() {
        historyStack = [];
        historyIndex = -1;
        recordHistory();
    }

    // ── Liens (⌘K ou /lien) ──────────────────────────────────────
    function normalizeUrl(raw) {
        const url = (raw || '').trim();
        if (!url) return '';
        if (/^(https?:\/\/|mailto:|tel:)/i.test(url)) return url;
        if (/^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i.test(url)) return `mailto:${url}`;
        if (/^(www\.)?[\w-]+(\.[\w-]+)+([/?#]\S*)?$/i.test(url)) return `https://${url}`;
        return null;
    }

    function editLink() {
        const sel = window.getSelection();
        if (!sel || !sel.rangeCount || !editor.contains(sel.getRangeAt(0).startContainer)) return;
        const range = sel.getRangeAt(0).cloneRange();
        const startEl = range.startContainer.nodeType === Node.ELEMENT_NODE
            ? range.startContainer : range.startContainer.parentElement;
        const existing = startEl && startEl.closest('a');
        const linkEl = existing && editor.contains(existing) ? existing : null;

        const answer = window.prompt(
            linkEl ? 'Adresse du lien (laisser vide pour retirer le lien)' : 'Adresse du lien',
            linkEl ? linkEl.getAttribute('href') : 'https://'
        );
        // La boîte de dialogue fait perdre la sélection : on la restaure
        sel.removeAllRanges();
        sel.addRange(range);
        editor.focus();
        if (answer === null) return;

        const href = normalizeUrl(answer === 'https://' ? '' : answer);
        if (href === null) {
            window.alert('Adresse invalide. Exemple : https://www.exemple.fr');
            return;
        }

        withHistory(() => {
            if (linkEl) {
                if (!href) linkEl.replaceWith(...linkEl.childNodes);
                else linkEl.setAttribute('href', href);
                return;
            }
            if (!href) return;
            const a = document.createElement('a');
            a.setAttribute('href', href);
            if (!range.collapsed && getTopBlock(range.startContainer) === getTopBlock(range.endContainer)) {
                a.appendChild(range.extractContents());
            } else {
                if (!range.collapsed) range.collapse(false);
                a.textContent = answer.trim();
            }
            range.insertNode(a);
            // Curseur juste après le lien : la frappe suivante n'est pas incluse dans le lien
            const after = document.createRange();
            after.setStartAfter(a);
            after.collapse(true);
            sel.removeAllRanges();
            sel.addRange(after);
        });
        syncToHidden();
    }

    // ── Collage : on ne garde que ce que l'éditeur sait représenter ──
    const PASTE_BLOCK_MAP = {
        P: 'p', DIV: 'p', SECTION: 'p', ARTICLE: 'p', H1: 'h2', H2: 'h2', H3: 'h3', H4: 'h3', H5: 'h3', H6: 'h3',
        BLOCKQUOTE: 'blockquote', UL: 'ul', OL: 'ol', LI: 'li', PRE: 'pre', HR: 'hr',
    };
    const PASTE_INLINE_MAP = { STRONG: 'strong', B: 'strong', EM: 'em', I: 'em', CODE: 'code', BR: 'br' };
    const PASTE_DROP = ['SCRIPT', 'STYLE', 'META', 'LINK', 'TITLE', 'IMG', 'SVG', 'VIDEO', 'AUDIO', 'IFRAME', 'OBJECT', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'NOSCRIPT', 'TEMPLATE'];

    function cleanPastedNode(node, out) {
        if (node.nodeType === Node.TEXT_NODE) {
            out.appendChild(document.createTextNode(node.textContent));
            return;
        }
        if (node.nodeType !== Node.ELEMENT_NODE) return;
        const tag = node.tagName.toUpperCase();
        if (PASTE_DROP.includes(tag)) return;

        const appendChildren = (target) => node.childNodes.forEach((c) => cleanPastedNode(c, target));
        const style = (node.getAttribute('style') || '').toLowerCase();

        // Tableaux : une ligne de texte par rangée (cellules séparées par « | »)
        if (tag === 'TABLE') {
            node.querySelectorAll('tr').forEach((tr) => {
                const p = document.createElement('p');
                p.textContent = [...tr.children].map((td) => td.textContent.trim()).filter(Boolean).join(' | ');
                if (p.textContent) out.appendChild(p);
            });
            return;
        }
        if (tag === 'A') {
            const href = normalizeUrl(node.getAttribute('href') || '');
            if (href) {
                const a = document.createElement('a');
                a.setAttribute('href', href);
                appendChildren(a);
                out.appendChild(a);
            } else {
                appendChildren(out);
            }
            return;
        }
        // Google Docs enveloppe tout dans <b style="font-weight:normal">
        if (tag === 'B' && /font-weight\s*:\s*(normal|[1-5]00)\b/.test(style)) {
            appendChildren(out);
            return;
        }
        const mapped = PASTE_BLOCK_MAP[tag] || PASTE_INLINE_MAP[tag];
        if (mapped) {
            const el = document.createElement(mapped);
            if (mapped === 'pre') el.appendChild(document.createTextNode(node.textContent));
            else if (mapped !== 'br' && mapped !== 'hr') appendChildren(el);
            out.appendChild(el);
            return;
        }
        // SPAN & co : gras / italique exprimés en CSS (Google Docs, Word)
        const isBold = /font-weight\s*:\s*(bold|[6-9]00)\b/.test(style);
        const isItalic = /font-style\s*:\s*italic/.test(style);
        if (isBold || isItalic) {
            let wrapperEl = document.createElement(isBold ? 'strong' : 'em');
            let inner = wrapperEl;
            if (isBold && isItalic) {
                inner = document.createElement('em');
                wrapperEl.appendChild(inner);
            }
            appendChildren(inner);
            out.appendChild(wrapperEl);
            return;
        }
        appendChildren(out);
    }

    const BLOCK_LEVEL = ['P', 'H2', 'H3', 'BLOCKQUOTE', 'UL', 'OL', 'PRE', 'HR'];

    // Regroupe le contenu nettoyé en blocs de premier niveau valides
    function toBlocks(container) {
        const blocks = [];
        let current = null;
        const flush = () => {
            if (current && (cleanText(current.textContent).trim() || current.querySelector('a'))) blocks.push(current);
            current = null;
        };
        [...container.childNodes].forEach((n) => {
            if (n.nodeType === Node.ELEMENT_NODE && BLOCK_LEVEL.includes(n.tagName)) {
                flush();
                // Un paragraphe ne peut pas contenir de bloc (Word / Google Docs imbriquent p et div)
                if (['P', 'H2', 'H3'].includes(n.tagName)
                    && [...n.children].some((c) => BLOCK_LEVEL.includes(c.tagName) || c.tagName === 'LI')) {
                    blocks.push(...toBlocks(n));
                    return;
                }
                if (n.tagName === 'HR' || cleanText(n.textContent).trim()) blocks.push(n);
                return;
            }
            if (n.nodeType === Node.ELEMENT_NODE && n.tagName === 'LI') {
                flush();
                const ul = document.createElement('ul');
                ul.appendChild(n);
                blocks.push(ul);
                return;
            }
            if (n.nodeType === Node.TEXT_NODE && !n.textContent.trim() && !current) return;
            if (!current) current = document.createElement('p');
            current.appendChild(n);
        });
        flush();
        return blocks;
    }

    function blocksFromPlainText(text) {
        return text.replace(/\r\n?/g, '\n').split(/\n{2,}/)
            .map((para) => para.replace(/^\n+|\n+$/g, ''))
            .filter((para) => para.trim())
            .map((para) => makeParagraphFromText(para));
    }

    function insertInlineAtCaret(range, nodes) {
        range.deleteContents();
        const frag = document.createDocumentFragment();
        nodes.forEach((n) => frag.appendChild(n));
        const last = frag.lastChild;
        range.insertNode(frag);
        if (last) {
            const after = document.createRange();
            after.setStartAfter(last);
            after.collapse(true);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(after);
        }
    }

    // Insère des blocs au curseur : le bloc courant est coupé en deux autour du collage
    function insertBlocksAtCaret(range, blocks) {
        range.deleteContents();
        let block = getTopBlock(range.startContainer);
        if (!block) {
            normalizeRoot();
            block = getTopBlock(range.startContainer) || resolveTargetBlock(null);
        }

        // Un seul paragraphe collé : insertion en ligne (on reste dans le bloc courant)
        if (blocks.length === 1 && blocks[0].tagName === 'P') {
            insertInlineAtCaret(range, [...blocks[0].childNodes]);
            return;
        }

        let anchor = block;
        if (isEmptyNode(block)) {
            anchor = blocks[0];
            block.replaceWith(anchor);
            blocks = blocks.slice(1);
        } else {
            const tail = document.createRange();
            tail.setStart(range.endContainer, range.endOffset);
            tail.setEnd(block, block.childNodes.length);
            const tailContent = tail.extractContents();
            trimTrailingEmpty(block);
            const tailBlock = document.createElement(['UL', 'OL'].includes(block.tagName) ? 'p' : block.tagName);
            tailBlock.appendChild(tailContent);
            if (!isEmptyNode(tailBlock)) {
                block.after(tailBlock);
            }
        }
        blocks.forEach((b) => {
            anchor.after(b);
            anchor = b;
        });
        placeCaretAtEnd(anchor);
    }

    function handlePaste(e) {
        const data = e.clipboardData;
        if (!data) return;
        const sel = window.getSelection();
        if (!sel || !sel.rangeCount) return;
        const range = sel.getRangeAt(0);
        if (!editor.contains(range.startContainer)) return;
        e.preventDefault();

        const html = data.getData('text/html');
        const text = data.getData('text/plain') || '';
        const startBlock = getTopBlock(range.startContainer);
        const inPre = startBlock && startBlock.tagName === 'PRE';
        const inList = startBlock && ['UL', 'OL'].includes(startBlock.tagName);

        withHistory(() => {
            // URL collée sur du texte sélectionné → lien
            const pastedUrl = !html || text.trim() === text.trim().split(/\s/)[0] ? normalizeUrl(text) : null;
            if (pastedUrl && !range.collapsed && /^(https?:|mailto:)/.test(pastedUrl)
                && getTopBlock(range.startContainer) === getTopBlock(range.endContainer)) {
                const a = document.createElement('a');
                a.setAttribute('href', pastedUrl);
                a.appendChild(range.extractContents());
                insertInlineAtCaret(range, [a]);
                return;
            }
            // Bloc de code ou liste : texte brut uniquement
            if (inPre) {
                insertInlineAtCaret(range, [document.createTextNode(text)]);
                return;
            }
            if (inList) {
                const lines = text.replace(/\r\n?/g, '\n').replace(/\n+$/, '').split('\n');
                const nodes = [];
                lines.forEach((line, i) => {
                    if (i > 0) nodes.push(document.createElement('br'));
                    nodes.push(document.createTextNode(line));
                });
                insertInlineAtCaret(range, nodes);
                return;
            }

            let blocks;
            if (html) {
                const doc = new DOMParser().parseFromString(html, 'text/html');
                const cleaned = document.createElement('div');
                doc.body.childNodes.forEach((n) => cleanPastedNode(n, cleaned));
                blocks = toBlocks(cleaned);
            } else {
                blocks = blocksFromPlainText(text);
            }
            if (!blocks.length) return;
            insertBlocksAtCaret(range, blocks);
        });
        normalizeRoot();
        syncToHidden();
    }

    // ── Listes : Tab / Maj+Tab pour indenter ─────────────────────
    function closestListItem(node) {
        const el = node && (node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement);
        const li = el && el.closest('li');
        return li && editor.contains(li) ? li : null;
    }

    function indentListItem(li) {
        const prev = li.previousElementSibling;
        if (!prev || prev.tagName !== 'LI') return false;
        const listTag = li.parentElement.tagName;
        let sub = prev.lastElementChild;
        if (!sub || !['UL', 'OL'].includes(sub.tagName)) {
            sub = document.createElement(listTag);
            prev.appendChild(sub);
        }
        sub.appendChild(li);
        return true;
    }

    function outdentListItem(li) {
        const list = li.parentElement;
        const parentLi = list.parentElement;
        if (!parentLi || parentLi.tagName !== 'LI') return false;
        // Les éléments suivants deviennent les enfants de l'élément remonté (ordre conservé)
        const following = [];
        let n = li.nextElementSibling;
        while (n) {
            following.push(n);
            n = n.nextElementSibling;
        }
        if (following.length) {
            const sub = document.createElement(list.tagName);
            following.forEach((item) => sub.appendChild(item));
            li.appendChild(sub);
        }
        parentLi.after(li);
        if (!list.children.length) list.remove();
        return true;
    }

    // ── Sortie de bloc (comportement Notion) ─────────────────────
    // Entrée dans une citation / un titre → nouveau paragraphe normal ;
    // Maj+Entrée → retour à la ligne dans la citation ;
    // Retour arrière en début de bloc → le bloc redevient du texte normal.
    const EXIT_ON_ENTER_TAGS = ['BLOCKQUOTE', 'H1', 'H2', 'H3', 'H4'];
    const PLAIN_BLOCK_TAGS = ['P', 'DIV'];

    const cleanText = (s) => s.replace(/​/g, '');

    function getTopBlock(node) {
        if (!node || node === editor || !editor.contains(node)) return null;
        let n = node;
        while (n.parentNode && n.parentNode !== editor) n = n.parentNode;
        return n.parentNode === editor && n.nodeType === Node.ELEMENT_NODE ? n : null;
    }

    function textAround(block, caretRange, side) {
        const r = document.createRange();
        r.selectNodeContents(block);
        if (side === 'before') r.setEnd(caretRange.startContainer, caretRange.startOffset);
        else r.setStart(caretRange.endContainer, caretRange.endOffset);
        return cleanText(r.toString());
    }

    function isEmptyNode(n) {
        if (n.nodeName === 'BR') return true;
        if (n.nodeType === Node.TEXT_NODE) return !cleanText(n.textContent).trim();
        if (n.nodeType === Node.ELEMENT_NODE) {
            return !cleanText(n.textContent).trim() && !n.querySelector('img, hr');
        }
        return true;
    }

    function trimTrailingEmpty(el) {
        while (el.lastChild && isEmptyNode(el.lastChild)) el.lastChild.remove();
        const last = el.lastChild;
        if (last && last.nodeType === Node.ELEMENT_NODE && !['CODE', 'STRONG', 'EM', 'B', 'I', 'A'].includes(last.tagName)) {
            trimTrailingEmpty(last);
        }
    }

    function placeCaretAtStart(el) {
        const range = document.createRange();
        range.setStart(el, 0);
        range.collapse(true);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        editor.focus();
    }

    // Construit un paragraphe normal à partir d'un fragment (sous-blocs aplatis)
    function makeParagraph(fragment) {
        const p = document.createElement('p');
        if (fragment) p.appendChild(fragment);
        p.querySelectorAll('p, div, h1, h2, h3, h4, blockquote').forEach((inner) => {
            if (inner.previousSibling) inner.before(document.createElement('br'));
            inner.replaceWith(...inner.childNodes);
        });
        trimTrailingEmpty(p);
        if (!cleanText(p.textContent).trim() && !p.querySelector('img')) p.innerHTML = '<br>';
        return p;
    }

    function makeParagraphFromText(text) {
        const p = document.createElement('p');
        text.replace(/\n+$/, '').split('\n').forEach((line, i) => {
            if (i > 0) p.appendChild(document.createElement('br'));
            p.appendChild(document.createTextNode(line));
        });
        if (!cleanText(p.textContent).trim()) p.innerHTML = '<br>';
        return p;
    }

    // Coupe le bloc au curseur : la suite part dans un nouveau paragraphe normal
    function exitBlockAtCaret(block, range) {
        if (!range.collapsed) range.deleteContents();

        // Curseur au tout début d'un bloc non vide : paragraphe vide inséré au-dessus
        if (!textAround(block, range, 'before').trim() && cleanText(block.textContent).trim()) {
            block.before(makeParagraph());
            syncToHidden();
            return;
        }

        const tail = document.createRange();
        tail.setStart(range.endContainer, range.endOffset);
        tail.setEnd(block, block.childNodes.length);
        const p = makeParagraph(tail.extractContents());
        trimTrailingEmpty(block);

        if (isEmptyNode(block)) {
            // Bloc vide (ex : Entrée sur une citation vide) → il redevient un paragraphe
            block.replaceWith(p);
        } else {
            block.after(p);
        }
        placeCaretAtStart(p);
        syncToHidden();
    }

    // Bloc de code : Entrée = nouvelle ligne ; Entrée sur une ligne vide en fin de bloc = sortie
    function handleEnterInPre(block, range) {
        const before = textAround(block, range, 'before');
        const after = textAround(block, range, 'after');
        if (!after.replace(/\n/g, '') && (before.endsWith('\n') || !before.trim())) {
            const code = block.querySelector('code') || block;
            code.textContent = cleanText(code.textContent).replace(/\n+$/, '');
            const p = makeParagraph();
            if (!code.textContent.trim()) block.replaceWith(p);
            else block.after(p);
            placeCaretAtStart(p);
            syncToHidden();
            return;
        }
        if (!range.collapsed) range.deleteContents();
        // En fin de bloc, un « \n » final seul n'est pas affiché : on en ajoute un second
        const nl = document.createTextNode(after ? '\n' : '\n\n');
        range.insertNode(nl);
        const caret = document.createRange();
        caret.setStart(nl, 1);
        caret.collapse(true);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(caret);
        syncToHidden();
    }

    // Retour arrière en début de bloc formaté → texte normal (le contenu est conservé)
    function unformatBlock(block) {
        let p;
        if (block.tagName === 'PRE') {
            p = makeParagraphFromText(cleanText(block.textContent));
        } else {
            const all = document.createRange();
            all.selectNodeContents(block);
            p = makeParagraph(all.extractContents());
        }
        block.replaceWith(p);
        placeCaretAtStart(p);
        syncToHidden();
    }

    // Garantit une ligne de texte normal après le dernier bloc formaté
    function ensureTrailingParagraph() {
        const last = editor.lastElementChild;
        if (!last || PLAIN_BLOCK_TAGS.includes(last.tagName)) return null;
        const p = makeParagraph();
        editor.appendChild(p);
        return p;
    }

    function handleBlockKeys(e) {
        if (e.isComposing) return false;
        const sel = window.getSelection();
        if (!sel || !sel.rangeCount) return false;
        const range = sel.getRangeAt(0);
        const block = getTopBlock(range.startContainer);
        if (!block) return false;
        const tag = block.tagName;
        const isEnter = e.key === 'Enter';

        // Tab / Maj+Tab : indentation des listes ; dans un bloc de code, insère 4 espaces
        if (e.key === 'Tab' && !e.metaKey && !e.ctrlKey && !e.altKey) {
            const li = closestListItem(range.startContainer);
            if (li) {
                e.preventDefault();
                const caret = getCaret();
                if (e.shiftKey ? outdentListItem(li) : indentListItem(li)) {
                    restoreCaret(caret);
                    syncToHidden();
                }
                return true;
            }
            if (tag === 'PRE' && !e.shiftKey) {
                e.preventDefault();
                insertInlineAtCaret(range, [document.createTextNode('    ')]);
                syncToHidden();
                return true;
            }
            return false;
        }

        if (isEnter && tag === 'PRE') {
            e.preventDefault();
            if (e.metaKey || e.ctrlKey) {
                // ⌘/Ctrl+Entrée : sortie immédiate du bloc de code
                const p = makeParagraph();
                block.after(p);
                placeCaretAtStart(p);
                syncToHidden();
            } else {
                handleEnterInPre(block, range);
            }
            return true;
        }

        if (isEnter && EXIT_ON_ENTER_TAGS.includes(tag)) {
            // Maj+Entrée dans une citation : retour à la ligne sans sortir (comportement natif)
            if (e.shiftKey && tag === 'BLOCKQUOTE') return false;
            e.preventDefault();
            exitBlockAtCaret(block, range);
            return true;
        }

        if (e.key === 'Backspace' && range.collapsed
            && [...EXIT_ON_ENTER_TAGS, 'PRE'].includes(tag)
            && !textAround(block, range, 'before')) {
            e.preventDefault();
            unformatBlock(block);
            return true;
        }

        if ((e.key === 'ArrowDown' || e.key === 'ArrowRight') && range.collapsed
            && block === editor.lastElementChild
            && !PLAIN_BLOCK_TAGS.includes(tag)
            && !textAround(block, range, 'after').trim()) {
            const p = ensureTrailingParagraph();
            if (p) {
                e.preventDefault();
                placeCaretAtStart(p);
                syncToHidden();
                return true;
            }
        }
        return false;
    }

    // Clic sous le dernier bloc formaté : ouvre une ligne de texte normal
    editor.addEventListener('click', (e) => {
        if (e.target !== editor) return;
        const last = editor.lastElementChild;
        if (!last || PLAIN_BLOCK_TAGS.includes(last.tagName)) return;
        if (e.clientY > last.getBoundingClientRect().bottom) {
            const p = ensureTrailingParagraph();
            if (p) {
                placeCaretAtStart(p);
                syncToHidden();
            }
        }
    });

    // Rendu du menu Slash
    function renderMenu() {
        if (!filteredCommands.length) {
            menu.innerHTML = '<div class="u-text-xs u-text-muted u-p-2 u-text-center">Aucune commande trouvée</div>';
            return;
        }

        let html = '<div class="notion-slash-header">COMMANDES DE BASE</div>';
        filteredCommands.forEach((cmd, idx) => {
            const isActive = idx === activeIndex ? ' is-active' : '';
            html += `
                <div class="notion-slash-item${isActive}" data-index="${idx}" role="option" aria-selected="${idx === activeIndex}">
                    <div class="notion-slash-icon">${cmd.icon}</div>
                    <div class="notion-slash-info">
                        <span class="notion-slash-title">${cmd.title}</span>
                        <span class="notion-slash-desc">${cmd.desc}</span>
                    </div>
                    <span class="notion-slash-hint">${cmd.hint}</span>
                </div>
            `;
        });
        menu.innerHTML = html;

        const activeElem = menu.querySelector('.notion-slash-item.is-active');
        if (activeElem) {
            activeElem.scrollIntoView({ block: 'nearest' });
        }
    }

    // Positionne le menu « / » près du curseur, en restant dans la zone visible
    // (au-dessus du curseur si le clavier virtuel ou le bas de l'écran manque de place)
    function positionMenu() {
        const sel = window.getSelection();
        if (!sel || !sel.rangeCount) return;
        const range = sel.getRangeAt(0);
        let rect = typeof range.getBoundingClientRect === 'function' ? range.getBoundingClientRect() : null;
        if (!rect || (!rect.width && !rect.height && !rect.top)) {
            const host = getTopBlock(range.startContainer)
                || (range.startContainer.nodeType === Node.ELEMENT_NODE ? range.startContainer : range.startContainer.parentElement);
            if (host && host.getBoundingClientRect) rect = host.getBoundingClientRect();
        }
        const container = menu.parentElement;
        const containerRect = container.getBoundingClientRect();
        const compact = containerRect.width < 480;
        menu.classList.toggle('is-compact', compact);

        const vv = window.visualViewport;
        const viewTop = vv ? vv.offsetTop : 0;
        const viewBottom = vv ? vv.offsetTop + vv.height : window.innerHeight;
        const menuHeight = menu.offsetHeight || 220;
        const spaceBelow = viewBottom - rect.bottom;
        const spaceAbove = rect.top - viewTop;
        const above = spaceBelow < menuHeight + 12 && spaceAbove > spaceBelow;

        menu.style.bottom = 'auto';
        menu.style.top = `${above ? rect.top - containerRect.top - menuHeight - 6 : rect.bottom - containerRect.top + 6}px`;
        if (compact) {
            menu.style.left = '0px';
        } else {
            const width = menu.offsetWidth || 290;
            const left = Math.max(0, Math.min(rect.left - containerRect.left, containerRect.width - width));
            menu.style.left = `${left}px`;
        }
    }

    if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', () => {
            if (isSlashOpen) positionMenu();
        });
    }

    // Sélection d'une commande : pointerdown empêche la perte de focus (souris et tactile),
    // l'application se fait au clic pour ne pas déclencher pendant un défilement tactile.
    menu.addEventListener('pointerdown', (e) => {
        if (e.target.closest('.notion-slash-item')) e.preventDefault();
    });
    menu.addEventListener('mousedown', (e) => {
        if (e.target.closest('.notion-slash-item')) e.preventDefault();
    });
    menu.addEventListener('click', (e) => {
        const item = e.target.closest('.notion-slash-item');
        if (!item) return;
        e.preventDefault();
        const index = parseInt(item.getAttribute('data-index'), 10);
        if (!isNaN(index) && filteredCommands[index]) applyCommand(filteredCommands[index]);
    });

    function openMenu(query = '') {
        isSlashOpen = true;
        const q = query.toLowerCase().trim();
        filteredCommands = NOTION_SLASH_COMMANDS.filter((cmd) => {
            return (
                cmd.id.includes(q) ||
                cmd.title.toLowerCase().includes(q) ||
                cmd.desc.toLowerCase().includes(q) ||
                cmd.hint.toLowerCase().includes(q)
            );
        });
        activeIndex = 0;
        renderMenu();
        menu.classList.add('is-open');

        positionMenu();
    }

    function closeMenu() {
        isSlashOpen = false;
        slashRangeInfo = null;
        menu.classList.remove('is-open');
    }

    // ── Transformations de bloc (DOM direct) ─────────────────────
    // On n'utilise pas execCommand('formatBlock') : sur une ligne vide, le navigateur
    // recale le curseur sur la ligne précédente et formate le mauvais bloc.
    const STRUCTURAL_TAGS = ['P', 'DIV', 'H1', 'H2', 'H3', 'H4', 'BLOCKQUOTE', 'PRE', 'UL', 'OL', 'HR'];

    function getCaret() {
        const sel = window.getSelection();
        if (!sel || !sel.rangeCount) return null;
        const r = sel.getRangeAt(0);
        if (!editor.contains(r.startContainer)) return null;
        return { node: r.startContainer, offset: r.startOffset };
    }

    function restoreCaret(caret) {
        if (!caret || !caret.node || caret.node === editor || !editor.contains(caret.node)) return false;
        const max = caret.node.nodeType === Node.TEXT_NODE ? caret.node.length : caret.node.childNodes.length;
        const r = document.createRange();
        r.setStart(caret.node, Math.min(caret.offset, max));
        r.collapse(true);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(r);
        return true;
    }

    function placeCaretAtEnd(el) {
        if (!cleanText(el.textContent)) {
            placeCaretAtStart(el);
            return;
        }
        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        let last = null;
        while (walker.nextNode()) last = walker.currentNode;
        const r = document.createRange();
        r.setStart(last, last.length);
        r.collapse(true);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(r);
        editor.focus();
    }

    // Range le texte « nu » posé directement dans l'éditeur dans des <p> (curseur préservé)
    function normalizeRoot() {
        const caret = getCaret();
        let current = null;
        let changed = false;
        for (const n of [...editor.childNodes]) {
            if (n.nodeType === Node.ELEMENT_NODE && STRUCTURAL_TAGS.includes(n.tagName)) {
                current = null;
                continue;
            }
            // Blancs de mise en forme du HTML serveur entre deux blocs
            if (n.nodeType === Node.TEXT_NODE && !n.textContent.trim() && n.textContent.includes('\n')) {
                if (!caret || caret.node !== n) {
                    n.remove();
                    changed = true;
                    continue;
                }
            }
            if (n.nodeType !== Node.TEXT_NODE && n.nodeType !== Node.ELEMENT_NODE) continue;
            if (!current) {
                current = document.createElement('p');
                n.before(current);
            }
            current.appendChild(n);
            changed = true;
        }
        if (changed) restoreCaret(caret);
        return changed;
    }

    // Bloc de premier niveau visé par une commande (créé si l'éditeur est vide)
    function resolveTargetBlock(range) {
        if (range) {
            let block = getTopBlock(range.startContainer);
            if (!block && range.startContainer === editor) {
                const n = editor.childNodes[range.startOffset] || editor.childNodes[range.startOffset - 1];
                block = n && n.nodeType === Node.ELEMENT_NODE ? n : null;
            }
            if (block && block.tagName !== 'HR') return block;
        }
        if (normalizeRoot()) {
            const caret = getCaret();
            const block = caret ? getTopBlock(caret.node) : null;
            if (block) return block;
        }
        const p = makeParagraph();
        editor.appendChild(p);
        placeCaretAtStart(p);
        return p;
    }

    // Sort un <li> de sa liste : la liste est coupée en deux autour d'un emplacement réservé
    function extractListItem(li) {
        const list = li.parentElement;
        const items = [...list.children];
        const rest = items.slice(items.indexOf(li) + 1);
        const slot = document.createElement('p');
        list.after(slot);
        if (rest.length) {
            const tailList = document.createElement(list.tagName);
            rest.forEach((item) => tailList.appendChild(item));
            slot.after(tailList);
        }
        const all = document.createRange();
        all.selectNodeContents(li);
        const content = all.extractContents();
        li.remove();
        if (!list.children.length) list.remove();
        return { slot, content };
    }

    // Change le type du bloc courant : p, h2, h3, blockquote, ul, ol (re-cliquer = retour au texte normal)
    function setBlockType(type, block) {
        const caret = getCaret();
        const TYPE = type.toUpperCase();
        let slot;
        let content;

        if (block.tagName === 'UL' || block.tagName === 'OL') {
            const caretLi = caret && caret.node.nodeType === Node.ELEMENT_NODE
                ? caret.node.closest('li')
                : caret && caret.node.parentElement && caret.node.parentElement.closest('li');
            const li = (caretLi && block.contains(caretLi)) ? caretLi : block.querySelector('li');
            if (!li) return null;
            if (TYPE === 'UL' || TYPE === 'OL') {
                if (TYPE === block.tagName) {
                    type = 'p';
                } else {
                    // Puces ↔ numérotation : on change toute la liste
                    const swapped = document.createElement(type);
                    while (block.firstChild) swapped.appendChild(block.firstChild);
                    block.replaceWith(swapped);
                    if (!restoreCaret(caret)) placeCaretAtEnd(li);
                    return li;
                }
            }
            ({ slot, content } = extractListItem(li));
        } else {
            if (TYPE === block.tagName) type = 'p';
            slot = block;
            if (block.tagName === 'PRE') {
                content = document.createDocumentFragment();
                const tmp = makeParagraphFromText(cleanText(block.textContent));
                while (tmp.firstChild) content.appendChild(tmp.firstChild);
            } else {
                const all = document.createRange();
                all.selectNodeContents(block);
                content = all.extractContents();
            }
        }

        const inner = makeParagraph(content);
        let target;
        if (type === 'ul' || type === 'ol') {
            target = document.createElement('li');
            while (inner.firstChild) target.appendChild(inner.firstChild);
            const prev = slot.previousElementSibling;
            if (prev && prev.tagName === type.toUpperCase()) {
                prev.appendChild(target);
                slot.remove();
            } else {
                const list = document.createElement(type);
                list.appendChild(target);
                slot.replaceWith(list);
            }
        } else if (type === 'p') {
            target = inner;
            slot.replaceWith(target);
        } else {
            target = document.createElement(type);
            while (inner.firstChild) target.appendChild(inner.firstChild);
            slot.replaceWith(target);
        }

        if (!(caret && target.contains(caret.node) && restoreCaret(caret))) placeCaretAtEnd(target);
        return target;
    }

    function insertAfterBlock(block, el) {
        // Ligne vide : le nouveau bloc la remplace ; sinon il s'insère juste dessous
        if (block.tagName !== 'UL' && block.tagName !== 'OL' && isEmptyNode(block)) block.replaceWith(el);
        else block.after(el);
    }

    // Application unifiée d'une mise en forme (dropdown ou clic droit)
    function applyFormat(actionId, targetHint = null) {
        if (actionId === 'link') {
            editLink();
            return;
        }
        recordHistory();
        // Restaurer la sélection active si existante
        const sel = window.getSelection();
        if (savedSelectionRange && (!sel || sel.rangeCount === 0 || !editor.contains(sel.anchorNode))) {
            sel.removeAllRanges();
            sel.addRange(savedSelectionRange);
        }

        const hasSelection = sel && !sel.isCollapsed && editor.contains(sel.anchorNode);
        const getBlock = () => (targetHint && editor.contains(targetHint)
            ? targetHint
            : resolveTargetBlock(sel && sel.rangeCount ? sel.getRangeAt(0) : null));

        switch (actionId) {
            case 'clear': {
                if (hasSelection) document.execCommand('removeFormat', false, null);
                const block = getBlock();
                if (block.tagName === 'PRE' || !PLAIN_BLOCK_TAGS.includes(block.tagName)) {
                    if (['UL', 'OL'].includes(block.tagName)) setBlockType(block.tagName.toLowerCase(), block);
                    else unformatBlock(block);
                }
                break;
            }
            case 'bold': {
                document.execCommand('bold');
                break;
            }
            case 'italic': {
                document.execCommand('italic');
                break;
            }
            case 'h2':
            case 'h3': {
                setBlockType(actionId, getBlock());
                break;
            }
            case 'quote': {
                setBlockType('blockquote', getBlock());
                break;
            }
            case 'callout': {
                const block = getBlock();
                const bq = block.tagName === 'BLOCKQUOTE' ? block : setBlockType('blockquote', block);
                if (bq && !cleanText(bq.textContent).startsWith('💡')) {
                    if (bq.firstChild && bq.firstChild.nodeName === 'BR' && bq.childNodes.length === 1) bq.firstChild.remove();
                    bq.prepend(document.createTextNode('💡 '));
                    placeCaretAtEnd(bq);
                }
                break;
            }
            case 'bullet': {
                setBlockType('ul', getBlock());
                break;
            }
            case 'numbered': {
                setBlockType('ol', getBlock());
                break;
            }
            case 'code': {
                if (hasSelection) {
                    const selectedText = sel.toString();
                    document.execCommand('insertHTML', false, `<code>${escapeEditorHtml(selectedText)}</code>`);
                } else {
                    const block = getBlock();
                    const pre = document.createElement('pre');
                    const code = document.createElement('code');
                    const text = document.createTextNode('​');
                    code.appendChild(text);
                    pre.appendChild(code);
                    insertAfterBlock(block, pre);
                    restoreCaret({ node: text, offset: 1 });
                    editor.focus();
                }
                break;
            }
            case 'divider': {
                const block = getBlock();
                const hr = document.createElement('hr');
                const p = makeParagraph();
                insertAfterBlock(block, hr);
                hr.after(p);
                placeCaretAtStart(p);
                break;
            }
        }

        syncToHidden();
        editor.focus();
        recordHistory();
    }

    function applyCommand(cmd) {
        let targetBlock = null;
        // Supprimer le texte "/requête" si menu ouvert en tapant /
        if (slashRangeInfo && slashRangeInfo.textNode && editor.contains(slashRangeInfo.textNode)) {
            const { textNode, slashOffset, endOffset } = slashRangeInfo;
            // Le bloc visé est mémorisé AVANT d'effacer le « / » (ligne vide ensuite = curseur instable)
            if (!getTopBlock(textNode)) normalizeRoot();
            targetBlock = getTopBlock(textNode);
            const before = textNode.textContent.substring(0, slashOffset);
            const after = textNode.textContent.substring(endOffset);
            textNode.textContent = before + after;
            if (targetBlock && isEmptyNode(targetBlock) && !targetBlock.querySelector('br')) {
                targetBlock.appendChild(document.createElement('br'));
            }
            restoreCaret({ node: textNode, offset: slashOffset });
        }
        closeMenu();

        // Applique la mise en forme (au bloc mémorisé, à la sélection ou au bloc courant)
        applyFormat(cmd.id, targetBlock);
    }

    // Input Rules : transformation instantanée du Markdown à la frappe
    function checkInputRules() {
        const sel = window.getSelection();
        if (!sel || !sel.rangeCount) return false;
        const range = sel.getRangeAt(0);
        let block = range.startContainer;
        while (block && block !== editor && !['P', 'DIV', 'H1', 'H2', 'H3', 'BLOCKQUOTE', 'LI'].includes(block.tagName)) {
            block = block.parentElement;
        }
        if (!block || block === editor) return false;

        const text = block.textContent;

        // Titre H2 : "## " ou "# "
        if (text.startsWith('## ') || text.startsWith('# ')) {
            const prefixLen = text.startsWith('## ') ? 3 : 2;
            const content = text.substring(prefixLen);
            const h2 = document.createElement('h2');
            h2.textContent = content || '\u200B';
            block.replaceWith(h2);
            setCursorAt(h2, h2.textContent.length);
            syncToHidden();
            return true;
        }

        // Sous-titre H3 : "### "
        if (text.startsWith('### ')) {
            const content = text.substring(4);
            const h3 = document.createElement('h3');
            h3.textContent = content || '\u200B';
            block.replaceWith(h3);
            setCursorAt(h3, h3.textContent.length);
            syncToHidden();
            return true;
        }

        // Citation : "> "
        if (text.startsWith('> ')) {
            const content = text.substring(2);
            const bq = document.createElement('blockquote');
            bq.textContent = content || '\u200B';
            block.replaceWith(bq);
            setCursorAt(bq, bq.textContent.length);
            syncToHidden();
            return true;
        }

        // Puces : "- " ou "* "
        if ((text.startsWith('- ') || text.startsWith('* ')) && block.tagName !== 'LI') {
            const content = text.substring(2);
            const ul = document.createElement('ul');
            const li = document.createElement('li');
            li.textContent = content || '\u200B';
            ul.appendChild(li);
            block.replaceWith(ul);
            setCursorAt(li, li.textContent.length);
            syncToHidden();
            return true;
        }

        // Liste numérotée : "1. "
        if (text.startsWith('1. ') && block.tagName !== 'LI') {
            const content = text.substring(3);
            const ol = document.createElement('ol');
            const li = document.createElement('li');
            li.textContent = content || '\u200B';
            ol.appendChild(li);
            block.replaceWith(ol);
            setCursorAt(li, li.textContent.length);
            syncToHidden();
            return true;
        }

        // Séparateur : "---"
        if (text.trim() === '---') {
            const hr = document.createElement('hr');
            const p = document.createElement('p');
            p.innerHTML = '<br>';
            block.replaceWith(hr);
            hr.after(p);
            setCursorAt(p);
            syncToHidden();
            return true;
        }
        return false;
    }

    // Gestion du clavier
    // Applique une touche « de bloc » (Entrée, ⌫, Tab, flèches) en l'inscrivant dans l'historique
    const BLOCK_KEYS = ['Enter', 'Backspace', 'Tab', 'ArrowDown', 'ArrowRight'];

    function runBlockKey(e) {
        if (!BLOCK_KEYS.includes(e.key)) return false;
        const before = takeSnapshot();
        if (!handleBlockKeys(e)) return false;
        pushSnapshot(before);
        recordHistory();
        return true;
    }

    editor.addEventListener('keydown', (e) => {
        const isModifier = e.ctrlKey || e.metaKey;
        const lowerKey = (e.key || '').toLowerCase();

        // Annuler / rétablir (⌘Z, ⌘⇧Z, Ctrl+Y)
        if (isModifier && !e.altKey && (lowerKey === 'z' || lowerKey === 'y')) {
            e.preventDefault();
            if (lowerKey === 'y' || e.shiftKey) redo();
            else undo();
            return;
        }

        // Navigation dans le menu Slash
        if (isSlashOpen) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (filteredCommands.length > 0) {
                    activeIndex = (activeIndex + 1) % filteredCommands.length;
                    renderMenu();
                }
                return;
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (filteredCommands.length > 0) {
                    activeIndex = (activeIndex - 1 + filteredCommands.length) % filteredCommands.length;
                    renderMenu();
                }
                return;
            }
            if (e.key === 'Enter' || e.key === 'Tab') {
                e.preventDefault();
                e.stopPropagation();
                if (filteredCommands[activeIndex]) {
                    applyCommand(filteredCommands[activeIndex]);
                }
                return;
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                closeMenu();
                return;
            }
        }

        // Sortie de bloc : Entrée / Retour arrière / Tab / flèches (citation, titre, code, listes)
        if (runBlockKey(e)) return;

        // Si du texte est surligné et qu'on tape '/', ouvrir le dropdown sans effacer le texte !
        if (e.key === '/') {
            const sel = window.getSelection();
            if (sel && !sel.isCollapsed && editor.contains(sel.anchorNode)) {
                e.preventDefault();
                saveCurrentSelection();
                openMenu('');
                return;
            }
        }

        // Raccourcis clavier (⌘B, ⌘I, ⌘K)
        if (isModifier && lowerKey === 'b') {
            e.preventDefault();
            withHistory(() => document.execCommand('bold'));
            syncToHidden();
            return;
        }
        if (isModifier && lowerKey === 'i') {
            e.preventDefault();
            withHistory(() => document.execCommand('italic'));
            syncToHidden();
            return;
        }
        if (isModifier && lowerKey === 'k') {
            e.preventDefault();
            editLink();
        }
    });

    // Claviers virtuels (Android notamment) : keydown renvoie souvent « Unidentified ».
    // beforeinput porte l'intention réelle (nouvelle ligne, effacement, annulation…).
    editor.addEventListener('beforeinput', (e) => {
        const proxy = (key, shiftKey = false) => ({
            key,
            shiftKey,
            metaKey: false,
            ctrlKey: false,
            altKey: false,
            isComposing: e.isComposing,
            preventDefault: () => e.preventDefault(),
        });
        switch (e.inputType) {
            case 'historyUndo':
                e.preventDefault();
                undo();
                return;
            case 'historyRedo':
                e.preventDefault();
                redo();
                return;
            case 'insertParagraph':
            case 'insertLineBreak':
                if (isSlashOpen) {
                    e.preventDefault();
                    if (filteredCommands[activeIndex]) applyCommand(filteredCommands[activeIndex]);
                    return;
                }
                runBlockKey(proxy('Enter', e.inputType === 'insertLineBreak'));
                return;
            case 'deleteContentBackward':
                runBlockKey(proxy('Backspace'));
                return;
            case 'insertText': {
                // « / » tapé sur une sélection : ouvre le menu sans effacer le texte sélectionné
                const sel = window.getSelection();
                if (e.data === '/' && sel && !sel.isCollapsed && editor.contains(sel.anchorNode)) {
                    e.preventDefault();
                    saveCurrentSelection();
                    openMenu('');
                }
                return;
            }
            default:
        }
    });

    editor.addEventListener('paste', handlePaste);

    // ⌘/Ctrl+clic sur un lien : ouverture dans un nouvel onglet
    editor.addEventListener('click', (e) => {
        const link = e.target.closest && e.target.closest('a[href]');
        if (link && editor.contains(link) && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            window.open(link.getAttribute('href'), '_blank', 'noopener');
        }
    });

    // Type du dernier pointeur : le menu contextuel personnalisé est réservé à la souris,
    // l'appui long tactile garde le menu natif (sélection, copier-coller).
    let lastPointerType = 'mouse';
    editor.addEventListener('pointerdown', (e) => {
        lastPointerType = e.pointerType || 'mouse';
    });

    // Écoute de la saisie pour détecter "/", filtrer et exécuter les Input Rules
    editor.addEventListener('input', (e) => {
        // Texte tapé hors de tout bloc (éditeur vide) → rangé dans un paragraphe
        if (!e.isComposing) normalizeRoot();
        syncToHidden();
        const beforeRule = takeSnapshot();
        if (checkInputRules()) {
            pushSnapshot(beforeRule);
            recordHistory();
        } else {
            scheduleHistory();
        }

        const sel = window.getSelection();
        if (!sel || !sel.rangeCount) return;
        const range = sel.getRangeAt(0);
        const textNode = range.startContainer;

        if (textNode.nodeType === Node.TEXT_NODE) {
            const text = textNode.textContent.substring(0, range.startOffset);
            const lastSlash = text.lastIndexOf('/');

            if (lastSlash !== -1) {
                const charBefore = lastSlash === 0 ? '\n' : text.charAt(lastSlash - 1);
                if (charBefore === '\n' || charBefore === ' ' || charBefore === '\t' || charBefore === '\u200B') {
                    const query = text.substring(lastSlash + 1);
                    if (!query.includes(' ') && !query.includes('\n')) {
                        slashRangeInfo = { textNode, slashOffset: lastSlash, endOffset: range.startOffset };
                        openMenu(query);
                        return;
                    }
                }
            }
        }

        if (isSlashOpen) {
            closeMenu();
        }
    });

    // Clic droit : ouverture du menu contextuel personnalisé
    editor.addEventListener('contextmenu', (e) => {
        if (lastPointerType !== 'mouse') return;
        e.preventDefault();
        saveCurrentSelection();

        if (!contextMenu) return;

        // Positionnement à la souris avec contraintes de fenêtre
        const menuWidth = 235;
        const menuHeight = 350;
        let posX = e.clientX;
        let posY = e.clientY;

        if (posX + menuWidth > window.innerWidth) {
            posX = window.innerWidth - menuWidth - 10;
        }
        if (posY + menuHeight > window.innerHeight) {
            posY = window.innerHeight - menuHeight - 10;
        }

        contextMenu.style.left = `${posX}px`;
        contextMenu.style.top = `${posY}px`;
        contextMenu.classList.add('is-open');
    });

    // Clic sur les actions du menu contextuel
    if (contextMenu) {
        contextMenu.querySelectorAll('.notion-context-item').forEach((item) => {
            item.addEventListener('mousedown', (e) => {
                e.preventDefault(); // évite la perte de focus de l'éditeur
                const action = item.getAttribute('data-action');
                if (action) {
                    applyFormat(action);
                }
                contextMenu.classList.remove('is-open');
            });
        });
    }

    // Fermer les menus si clic en dehors ou appui sur Escape
    document.addEventListener('click', (e) => {
        if (!editor.contains(e.target) && !menu.contains(e.target)) {
            closeMenu();
        }
        if (contextMenu && !contextMenu.contains(e.target)) {
            contextMenu.classList.remove('is-open');
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (contextMenu && contextMenu.classList.contains('is-open')) {
                contextMenu.classList.remove('is-open');
            }
        }
    });

    // Soumission du formulaire
    const form = editor.closest('form');
    if (form) {
        form.addEventListener('submit', (e) => {
            syncToHidden();
            const titleInput = form.querySelector('input[name="title"]');
            if (titleInput && !titleInput.value.trim()) {
                e.preventDefault();
                titleInput.focus();
                return;
            }
            if (!hiddenInput.value.trim()) {
                e.preventDefault();
                editor.focus();
            }
        });
    }

    syncToHidden();
    resetHistory();

    const api = {
        undo,
        redo,
        sync: syncToHidden,
        // Restaure le contenu d'origine (annulation d'une édition)
        reset() {
            closeMenu();
            if (contextMenu) contextMenu.classList.remove('is-open');
            editor.innerHTML = initialHTML;
            syncToHidden();
            resetHistory();
        },
        focusEnd() {
            const last = editor.lastElementChild || editor;
            setCursorAt(last);
        },
    };
    wrapper._notionEditor = api;
    return api;
}

window.initNotionEditor = initNotionEditor;
window.editorToMarkdown = editorToMarkdown;
