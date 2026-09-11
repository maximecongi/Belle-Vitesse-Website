/**
 * project.js — Interactions du formulaire de projet (dates, équipement) et modal protocoles.
 */

function initProjectFormHighlight() {
    document.querySelectorAll('input[name="vehicle_ids"], input[name="head_ids"]').forEach(cb => {
        if (cb._highlightBound) return;
        cb._highlightBound = true;

        cb.addEventListener('change', () => {
            const label = cb.closest('label');
            if (!label) return;
            if (cb.checked) {
                label.style.background = '#f8f9fa';
                label.style.borderColor = '#858585';
            } else {
                label.style.background = '';
                label.style.borderColor = '#e5e7eb';
            }
        });
    });
}

function initProjectDateValidation() {
    const depDate = document.querySelector('input[name="departure_date"]');
    const startTour = document.querySelector('input[name="shoot_start"]');
    const endTour = document.querySelector('input[name="shoot_end"]');
    const retDate = document.querySelector('input[name="return_date"]');

    if (depDate && startTour && endTour && retDate) {
        const updateMinDates = () => {
            if (depDate.value) {
                startTour.min = depDate.value;
            }
            if (startTour.value) {
                endTour.min = startTour.value;
            }
            if (endTour.value) {
                retDate.min = endTour.value;
            }
        };

        depDate.addEventListener('change', updateMinDates);
        startTour.addEventListener('change', updateMinDates);
        endTour.addEventListener('change', updateMinDates);

        // Exécution initiale
        updateMinDates();
    }
}

function initVehiclesModal() {
    const vehiclesModal = document.getElementById('vehiclesModal');
    const vTriggers = document.querySelectorAll('.vehicle-modal-trigger');
    const closeVModalBtn = document.getElementById('closeVehiclesModal');

    if (vehiclesModal && vTriggers.length > 0) {
        vTriggers.forEach(trigger => {
            if (trigger._modalBound) return;
            trigger._modalBound = true;

            trigger.addEventListener('click', (e) => {
                e.preventDefault();
                const iframe = vehiclesModal.querySelector('iframe');
                if (iframe && !iframe.getAttribute('src') && iframe.dataset.src) {
                    iframe.setAttribute('src', iframe.dataset.src);
                }
                vehiclesModal.style.display = 'flex';
            });
        });

        if (closeVModalBtn && !closeVModalBtn._modalBound) {
            closeVModalBtn._modalBound = true;
            closeVModalBtn.addEventListener('click', () => {
                vehiclesModal.style.display = 'none';
            });
        }

        if (!vehiclesModal._backdropBound) {
            vehiclesModal._backdropBound = true;
            window.addEventListener('click', (event) => {
                if (event.target === vehiclesModal) {
                    vehiclesModal.style.display = 'none';
                }
            });
        }
    }
}

// ── Fonctions utilitaires pour l'éditeur WYSIWYG Notion ──────────────

function escapeHtml(str) {
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
    { id: 'code', title: 'Bloc de données / Paramètres', desc: 'Données techniques ou code', icon: '💻', hint: '```' },
    { id: 'divider', title: 'Séparateur horizontal', desc: 'Ligne de séparation visuelle', icon: '➖', hint: '---' },
];

function nodeToMarkdown(node) {
    if (!node) return '';

    if (node.nodeType === Node.TEXT_NODE) {
        return node.textContent.replace(/\u200B/g, '');
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
            const lines = inner.trim().split('\n').filter(Boolean);
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
        case 'hr':
            return '\n---\n';
        case 'br':
            return '\n';
        case 'li': {
            const isOl = node.parentElement && node.parentElement.tagName.toLowerCase() === 'ol';
            return `${isOl ? '1. ' : '- '}${inner.trim()}\n`;
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

function initProjectNotionSlashEditor() {
    const editor = document.getElementById('reportContentEditor');
    const hiddenInput = document.getElementById('reportContentInput');
    const menu = document.getElementById('notionSlashMenu');
    const contextMenu = document.getElementById('notionContextMenu');
    if (!editor || !hiddenInput || !menu) return;
    if (editor._notionEditorBound) return;
    editor._notionEditorBound = true;

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

    function insertBlockAtCursor(element) {
        const sel = window.getSelection();
        if (!sel || !sel.rangeCount) {
            editor.appendChild(element);
            setCursorAt(element);
            return;
        }
        const range = sel.getRangeAt(0);
        range.deleteContents();
        range.insertNode(element);
        setCursorAt(element);
    }

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

        menu.querySelectorAll('.notion-slash-item').forEach((item) => {
            item.addEventListener('mousedown', (e) => {
                e.preventDefault();
                const index = parseInt(item.getAttribute('data-index'), 10);
                if (!isNaN(index) && filteredCommands[index]) {
                    applyCommand(filteredCommands[index]);
                }
            });
        });

        const activeElem = menu.querySelector('.notion-slash-item.is-active');
        if (activeElem) {
            activeElem.scrollIntoView({ block: 'nearest' });
        }
    }

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

        // Positionnement contextuel près du curseur ou de la sélection
        const sel = window.getSelection();
        if (sel && sel.rangeCount) {
            const rect = sel.getRangeAt(0).getBoundingClientRect();
            const container = editor.closest('.notion-slash-container');
            const containerRect = container.getBoundingClientRect();
            const top = rect.bottom - containerRect.top + 6;
            const left = Math.max(10, Math.min(rect.left - containerRect.left, containerRect.width - 300));
            menu.style.top = `${top}px`;
            menu.style.left = `${left}px`;
        }
    }

    function closeMenu() {
        isSlashOpen = false;
        slashRangeInfo = null;
        menu.classList.remove('is-open');
    }

    // Application unifiée d'une mise en forme (dropdown ou clic droit)
    function applyFormat(actionId) {
        // Restaurer la sélection active si existante
        const sel = window.getSelection();
        if (savedSelectionRange && (!sel || sel.rangeCount === 0 || !editor.contains(sel.anchorNode))) {
            sel.removeAllRanges();
            sel.addRange(savedSelectionRange);
        }

        const hasSelection = sel && !sel.isCollapsed && editor.contains(sel.anchorNode);

        switch (actionId) {
            case 'clear': {
                // 1. Supprimer le formatage de style inline (gras, italique, etc.)
                document.execCommand('removeFormat', false, null);

                // 2. Transformer le bloc en paragraphe normal
                document.execCommand('formatBlock', false, '<p>');

                // 3. Dé-lister si dans une puce ou numérotation
                let block = sel ? sel.anchorNode : null;
                while (block && block !== editor && !['P', 'DIV', 'LI', 'H1', 'H2', 'H3', 'BLOCKQUOTE'].includes(block.tagName)) {
                    block = block.parentElement;
                }
                if (block && block !== editor) {
                    if (block.tagName === 'LI') {
                        document.execCommand('insertUnorderedList');
                    }
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
            case 'h2': {
                document.execCommand('formatBlock', false, '<h2>');
                break;
            }
            case 'h3': {
                document.execCommand('formatBlock', false, '<h3>');
                break;
            }
            case 'quote': {
                document.execCommand('formatBlock', false, '<blockquote>');
                break;
            }
            case 'callout': {
                document.execCommand('formatBlock', false, '<blockquote>');
                if (!hasSelection) {
                    document.execCommand('insertText', false, '💡 ');
                }
                break;
            }
            case 'bullet': {
                document.execCommand('insertUnorderedList');
                break;
            }
            case 'numbered': {
                document.execCommand('insertOrderedList');
                break;
            }
            case 'code': {
                if (hasSelection) {
                    const selectedText = sel.toString();
                    document.execCommand('insertHTML', false, `<code>${escapeHtml(selectedText)}</code>`);
                } else {
                    const pre = document.createElement('pre');
                    const code = document.createElement('code');
                    code.textContent = '// Données ou code';
                    pre.appendChild(code);
                    insertBlockAtCursor(pre);
                }
                break;
            }
            case 'divider': {
                document.execCommand('insertHorizontalRule');
                break;
            }
        }

        syncToHidden();
        editor.focus();
    }

    function applyCommand(cmd) {
        // Supprimer le texte "/requête" si menu ouvert en tapant /
        if (slashRangeInfo && slashRangeInfo.textNode) {
            const { textNode, slashOffset, endOffset } = slashRangeInfo;
            const before = textNode.textContent.substring(0, slashOffset);
            const after = textNode.textContent.substring(endOffset);
            textNode.textContent = before + after;
            setCursorAt(textNode, slashOffset);
        }
        closeMenu();

        // Applique la mise en forme (à la sélection ou au bloc courant)
        applyFormat(cmd.id);
    }

    // Input Rules : transformation instantanée du Markdown à la frappe
    function checkInputRules() {
        const sel = window.getSelection();
        if (!sel || !sel.rangeCount) return;
        const range = sel.getRangeAt(0);
        let block = range.startContainer;
        while (block && block !== editor && !['P', 'DIV', 'H1', 'H2', 'H3', 'BLOCKQUOTE', 'LI'].includes(block.tagName)) {
            block = block.parentElement;
        }
        if (!block || block === editor) return;

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
            return;
        }

        // Sous-titre H3 : "### "
        if (text.startsWith('### ')) {
            const content = text.substring(4);
            const h3 = document.createElement('h3');
            h3.textContent = content || '\u200B';
            block.replaceWith(h3);
            setCursorAt(h3, h3.textContent.length);
            syncToHidden();
            return;
        }

        // Citation : "> "
        if (text.startsWith('> ')) {
            const content = text.substring(2);
            const bq = document.createElement('blockquote');
            bq.textContent = content || '\u200B';
            block.replaceWith(bq);
            setCursorAt(bq, bq.textContent.length);
            syncToHidden();
            return;
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
            return;
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
            return;
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
            return;
        }
    }

    // Gestion du clavier
    editor.addEventListener('keydown', (e) => {
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

        // Raccourcis clavier (Cmd+B, Cmd+I)
        const isModifier = e.ctrlKey || e.metaKey;
        if (isModifier && (e.key === 'b' || e.key === 'B')) {
            e.preventDefault();
            document.execCommand('bold');
            syncToHidden();
            return;
        }
        if (isModifier && (e.key === 'i' || e.key === 'I')) {
            e.preventDefault();
            document.execCommand('italic');
            syncToHidden();
            return;
        }
    });

    // Écoute de la saisie pour détecter "/", filtrer et exécuter les Input Rules
    editor.addEventListener('input', () => {
        syncToHidden();
        checkInputRules();

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
            if (!hiddenInput.value.trim()) {
                e.preventDefault();
                editor.focus();
            }
        });
    }

    syncToHidden();
}

function initProjectReportsCollapsible() {
    if (document._projectReportsCollapsibleBound) return;
    document._projectReportsCollapsibleBound = true;

    document.addEventListener('click', (e) => {
        const toggleBtn = e.target.closest('[data-action="toggle-report"]');
        if (!toggleBtn) return;

        const wrapper = toggleBtn.closest('.project-report-collapsible');
        if (!wrapper) return;

        const isCollapsed = wrapper.classList.contains('is-collapsed');
        const previewEl = wrapper.querySelector('.project-report-body-preview');
        const fullEl = wrapper.querySelector('.project-report-body-full');
        const labelEl = toggleBtn.querySelector('.project-report-toggle-label');
        const iconEl = toggleBtn.querySelector('.project-report-toggle-icon');

        if (isCollapsed) {
            wrapper.classList.remove('is-collapsed');
            wrapper.classList.add('is-expanded');
            if (previewEl) previewEl.style.display = 'none';
            if (fullEl) fullEl.style.display = 'block';
            if (labelEl) labelEl.textContent = 'Plier';
            if (iconEl) iconEl.textContent = '▴';
            toggleBtn.setAttribute('aria-expanded', 'true');
        } else {
            wrapper.classList.remove('is-expanded');
            wrapper.classList.add('is-collapsed');
            if (previewEl) previewEl.style.display = 'block';
            if (fullEl) fullEl.style.display = 'none';
            if (labelEl) labelEl.textContent = 'Déplier';
            if (iconEl) iconEl.textContent = '▾';
            toggleBtn.setAttribute('aria-expanded', 'false');
        }
    });
}

function initProjectInteractions() {
    initProjectFormHighlight();
    initProjectDateValidation();
    initVehiclesModal();
    initProjectNotionSlashEditor();
    initProjectReportsCollapsible();
}

window.initProjectInteractions = initProjectInteractions;
