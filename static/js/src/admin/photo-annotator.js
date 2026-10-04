/**
 * photo-annotator.js — Outil d'annotation directe sur photos (Canvas Image Marker).
 * Direction Artistique Belle Vitesse (Light Mode, finesse, aligné sur incidents_list.html et checkins_list.html).
 * Icônes Lucide officielles (zéro émoji), dimensionnement vectoriel précis du texte et réouverture avec état préservé.
 */

(function () {
    'use strict';

    const CANVAS_FONT_FAMILY = "'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

    // Outils et réglages par défaut
    let currentTool = 'circle'; // 'select', 'circle', 'arrow', 'freehand', 'text'
    let currentColor = '#C32F27'; // Rouge BV officiel par défaut
    let currentLineWidth = 5; // Utilisé pour les tracés (3: S, 5: M, 9: L, 14: XL)
    let currentTextSizeIndex = 5; // 3: S, 5: M, 9: L, 14: XL

    let originalImage = null;
    let originalBaseSource = null;
    let originalFile = null;
    let onSaveCallback = null;

    let canvas = null;
    let ctx = null;
    let isDrawing = false;
    let startX = 0;
    let startY = 0;
    let activeFreehandPath = null;

    // Gestion de la sélection, déplacement et redimensionnement
    let selectedShapeIndex = null;
    let dragMode = null; // null, 'move', 'resize'
    let activeResizeHandle = null; // 'nw', 'ne', 'se', 'sw', 'arrow_start', 'arrow_end'
    let dragStartCoords = null;
    let shapeSnapshot = null;

    // Coordonnées pour l'annotation texte en cours
    let pendingTextCanvasCoords = null;
    let editingTextIndex = null;

    // Pile des actions / annotations
    let historyStack = [];

    function renderLucideIcons() {
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
    }

    function createModalDom() {
        if (document.getElementById('photoAnnotatorModal')) return;

        const modalHtml = `
        <div id="photoAnnotatorModal" class="bv-annotator-overlay" style="display: none;" aria-hidden="true">
            <div class="bv-annotator-container">
                <!-- Header Light Mode -->
                <div class="bv-annotator-header">
                    <div class="bv-annotator-title">
                        <span class="bv-annotator-badge-icon"><i data-lucide="pen-tool"></i></span>
                        <span class="bv-annotator-title-text">Constat & Annotation Photo</span>
                    </div>
                    <button type="button" class="bv-annotator-close" id="annotatorCloseBtn" title="Fermer (Échap)">
                        <i data-lucide="x"></i>
                    </button>
                </div>

                <!-- Barre d'outils Fine & Épurée -->
                <div class="bv-annotator-toolbar">
                    <div class="bv-tool-group">
                        <button type="button" class="bv-btn-tool" data-tool="select" title="Sélectionner, déplacer ou redimensionner">
                            <i data-lucide="mouse-pointer-2"></i> Sélection
                        </button>
                        <button type="button" class="bv-btn-tool active" data-tool="circle" title="Cercle (entourer un impact)">
                            <i data-lucide="circle"></i> Cercle
                        </button>
                        <button type="button" class="bv-btn-tool" data-tool="arrow" title="Flèche (pointer un défaut)">
                            <i data-lucide="arrow-up-right"></i> Flèche
                        </button>
                        <button type="button" class="bv-btn-tool" data-tool="freehand" title="Tracé libre">
                            <i data-lucide="pencil"></i> Pinceau
                        </button>
                        <button type="button" class="bv-btn-tool" data-tool="text" title="Ajouter une étiquette texte">
                            <i data-lucide="type"></i> Texte
                        </button>
                    </div>

                    <div class="bv-tool-divider"></div>

                    <!-- Nuancier officiel Belle Vitesse -->
                    <div class="bv-tool-group" title="Couleur de l'annotation">
                        <button type="button" class="bv-swatch active" data-color="#C32F27" title="Rouge BV (#C32F27 — Impact / Défaut critique)"></button>
                        <button type="button" class="bv-swatch" data-color="#F59E0B" title="Ambre BV (#F59E0B — Attention / À surveiller)"></button>
                        <button type="button" class="bv-swatch" data-color="#FFC845" title="Jaune BV (#FFC845 — Repère prioritaire)"></button>
                        <button type="button" class="bv-swatch" data-color="#5299D3" title="Bleu Acier BV (#5299D3 — Repère technique)"></button>
                        <button type="button" class="bv-swatch" data-color="#618B4A" title="Vert Sauge BV (#618B4A — Conforme / Réf)"></button>
                        <button type="button" class="bv-swatch" data-color="#151515" title="Noir Carbone BV (#151515 — Contraste carrosserie claire)"></button>
                        <button type="button" class="bv-swatch" data-color="#FFFFFF" title="Blanc Pur BV (#FFFFFF — Contraste carrosserie sombre)"></button>
                    </div>

                    <div class="bv-tool-divider"></div>

                    <!-- Sélecteur de Taille / Épaisseur -->
                    <div class="bv-tool-group" id="annotatorSizeGroup" title="Taille du texte ou épaisseur du tracé">
                        <span class="bv-tool-label" id="annotatorSizeLabel"><i data-lucide="scaling"></i> Taille :</span>
                        <button type="button" class="bv-btn-size" data-size="3" title="Taille fine / Petite (S)">S</button>
                        <button type="button" class="bv-btn-size active" data-size="5" title="Taille moyenne (M)">M</button>
                        <button type="button" class="bv-btn-size" data-size="9" title="Grande taille (L)">L</button>
                        <button type="button" class="bv-btn-size" data-size="14" title="Très grande taille (XL)">XL</button>
                    </div>

                    <div class="bv-tool-divider"></div>

                    <!-- Mode d'affichage (Défilement scrollable vs Vue globale) -->
                    <div class="bv-tool-group">
                        <button type="button" class="bv-btn-tool active" id="annotatorViewScrollBtn" title="Photo grand format avec défilement vertical complet">
                            <i data-lucide="arrow-up-down"></i> Défilement
                        </button>
                        <button type="button" class="bv-btn-tool" id="annotatorViewFitBtn" title="Ajuster l'ensemble de la photo à la fenêtre">
                            <i data-lucide="maximize-2"></i> Vue globale
                        </button>
                    </div>

                    <div class="bv-tool-group u-ml-auto">
                        <button type="button" class="bv-btn-tool bv-btn-danger" id="annotatorDeleteSelectedBtn" title="Supprimer l'annotation sélectionnée (Touche Suppr)" style="display: none;">
                            <i data-lucide="trash-2"></i> Supprimer
                        </button>
                        <button type="button" class="bv-btn-tool" id="annotatorUndoBtn" title="Annuler le dernier tracé (Ctrl+Z)">
                            <i data-lucide="undo-2"></i> Annuler
                        </button>
                        <button type="button" class="bv-btn-tool" id="annotatorClearBtn" title="Tout effacer">
                            <i data-lucide="rotate-ccw"></i> Effacer tout
                        </button>
                    </div>
                </div>

                <!-- Zone Canvas Défilable en Light Mode -->
                <div class="bv-annotator-canvas-wrap mode-scroll" id="canvasWrap">
                    <canvas id="photoAnnotatorCanvas"></canvas>

                    <!-- Popover flottant de texte Light Mode -->
                    <div id="annotatorTextPopover" class="bv-text-popover">
                        <div class="bv-popover-header">
                            <span class="bv-popover-title"><i data-lucide="type"></i> Texte d'annotation</span>
                            <button type="button" id="annotatorTextCancelBtn" class="bv-popover-btn-close" title="Fermer (Échap)">
                                <i data-lucide="x"></i>
                            </button>
                        </div>
                        <div class="bv-popover-body">
                            <input type="text" id="annotatorTextInput" class="bv-popover-input" placeholder="Ex: Rayure 15cm, éclat carrosserie..." maxlength="80" autocomplete="off" />
                            <div class="bv-popover-size-bar">
                                <span class="bv-popover-size-label">Taille :</span>
                                <button type="button" class="bv-popover-size-btn" data-popover-size="3" title="Petite (S)">S</button>
                                <button type="button" class="bv-popover-size-btn active" data-popover-size="5" title="Moyenne (M)">M</button>
                                <button type="button" class="bv-popover-size-btn" data-popover-size="9" title="Grande (L)">L</button>
                                <button type="button" class="bv-popover-size-btn" data-popover-size="14" title="Très grande (XL)">XL</button>
                            </div>
                        </div>
                        <div class="bv-popover-footer">
                            <button type="button" id="annotatorTextOkBtn" class="bv-popover-btn-ok" title="Valider">
                                <i data-lucide="check"></i> Insérer le texte
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Footer Light Mode -->
                <div class="bv-annotator-footer">
                    <span class="bv-annotator-tip" id="annotatorTip">
                        <i data-lucide="info"></i> Tracez sur la photo pour annoter. Utilisez Sélection pour déplacer ou redimensionner un repère.
                    </span>
                    <div class="u-flex u-gap-2">
                        <button type="button" class="admin-btn admin-btn-secondary" id="annotatorCancelBtn">Annuler</button>
                        <button type="button" class="admin-btn admin-btn-primary" id="annotatorSaveBtn">
                            <i data-lucide="check"></i> Enregistrer l'annotation
                        </button>
                    </div>
                </div>
            </div>
        </div>
        `;

        const div = document.createElement('div');
        div.innerHTML = modalHtml;
        document.body.appendChild(div.firstElementChild);

        renderLucideIcons();
        initModalEvents();
    }

    function initModalEvents() {
        const modal = document.getElementById('photoAnnotatorModal');
        const wrap = document.getElementById('canvasWrap');
        canvas = document.getElementById('photoAnnotatorCanvas');
        ctx = canvas.getContext('2d');

        // Fermeture
        document.getElementById('annotatorCloseBtn').onclick = closeModal;
        document.getElementById('annotatorCancelBtn').onclick = closeModal;

        // Outils
        modal.querySelectorAll('[data-tool]').forEach(btn => {
            btn.onclick = () => {
                modal.querySelectorAll('[data-tool]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentTool = btn.getAttribute('data-tool');
                hideTextPopover();

                updateSizeToolbarUI();
                updateToolCursor();
                updateTipText();
            };
        });

        // Nuancier
        modal.querySelectorAll('[data-color]').forEach(btn => {
            btn.onclick = () => {
                modal.querySelectorAll('[data-color]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentColor = btn.getAttribute('data-color');

                if (selectedShapeIndex !== null && historyStack[selectedShapeIndex]) {
                    historyStack[selectedShapeIndex].color = currentColor;
                    redrawCanvas();
                }

                const popover = document.getElementById('annotatorTextPopover');
                if (popover) popover.style.borderColor = currentColor;
            };
        });

        // Tailles dans la toolbar
        modal.querySelectorAll('[data-size]').forEach(btn => {
            btn.onclick = () => {
                const sz = parseInt(btn.getAttribute('data-size'), 10);
                setActiveSize(sz);
            };
        });

        // Tailles dans le popover texte
        modal.querySelectorAll('[data-popover-size]').forEach(btn => {
            btn.onclick = () => {
                const sz = parseInt(btn.getAttribute('data-popover-size'), 10);
                setActiveSize(sz);
            };
        });

        // Affichage Défilement vs Vue Globale
        const btnScroll = document.getElementById('annotatorViewScrollBtn');
        const btnFit = document.getElementById('annotatorViewFitBtn');

        btnScroll.onclick = () => {
            wrap.classList.remove('mode-fit');
            wrap.classList.add('mode-scroll');
            btnScroll.classList.add('active');
            btnFit.classList.remove('active');
            hideTextPopover();
        };

        btnFit.onclick = () => {
            wrap.classList.remove('mode-scroll');
            wrap.classList.add('mode-fit');
            btnFit.classList.add('active');
            btnScroll.classList.remove('active');
            hideTextPopover();
        };

        // Supprimer la forme sélectionnée
        const btnDeleteSelected = document.getElementById('annotatorDeleteSelectedBtn');
        btnDeleteSelected.onclick = deleteSelectedShape;

        // Undo
        document.getElementById('annotatorUndoBtn').onclick = () => {
            hideTextPopover();
            if (historyStack.length > 0) {
                historyStack.pop();
                selectedShapeIndex = null;
                updateDeleteBtnVisibility();
                redrawCanvas();
            }
        };

        // Clear all
        document.getElementById('annotatorClearBtn').onclick = () => {
            hideTextPopover();
            if (historyStack.length > 0 && confirm("Effacer toutes les annotations sur cette photo ?")) {
                historyStack = [];
                selectedShapeIndex = null;
                updateDeleteBtnVisibility();
                redrawCanvas();
            }
        };

        // Enregistrer
        document.getElementById('annotatorSaveBtn').onclick = saveAnnotation;

        // Popover text buttons
        const popoverOk = document.getElementById('annotatorTextOkBtn');
        const popoverCancel = document.getElementById('annotatorTextCancelBtn');
        const popoverInput = document.getElementById('annotatorTextInput');

        popoverOk.onclick = submitTextAnnotation;
        popoverCancel.onclick = hideTextPopover;
        popoverInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitTextAnnotation();
            } else if (e.key === 'Escape') {
                hideTextPopover();
            }
        });

        // Raccourcis clavier
        window.addEventListener('keydown', (e) => {
            const modal = document.getElementById('photoAnnotatorModal');
            if (!modal || !modal.classList.contains('is-active')) return;
            if (document.activeElement === popoverInput) return;

            if (e.key === 'Delete' || e.key === 'Backspace') {
                if (selectedShapeIndex !== null) {
                    e.preventDefault();
                    deleteSelectedShape();
                }
            } else if (e.key === 'Escape') {
                closeModal();
            } else if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z')) {
                e.preventDefault();
                document.getElementById('annotatorUndoBtn')?.click();
            }
        });

        // Pointer Events sur le canvas
        canvas.addEventListener('pointerdown', handlePointerDown);
        canvas.addEventListener('pointermove', handlePointerMove);
        canvas.addEventListener('pointerup', handlePointerUp);
        canvas.addEventListener('pointercancel', handlePointerUp);

        // Double-clic pour éditer une annotation texte existante
        canvas.addEventListener('dblclick', handleCanvasDblClick);
    }

    function setActiveSize(sizeValue) {
        const modal = document.getElementById('photoAnnotatorModal');
        if (!modal) return;

        currentLineWidth = sizeValue;
        currentTextSizeIndex = sizeValue;

        // Met à jour les boutons toolbar
        modal.querySelectorAll('[data-size]').forEach(b => {
            const bVal = parseInt(b.getAttribute('data-size'), 10);
            b.classList.toggle('active', bVal === sizeValue);
        });

        // Met à jour les boutons popover
        modal.querySelectorAll('[data-popover-size]').forEach(b => {
            const bVal = parseInt(b.getAttribute('data-popover-size'), 10);
            b.classList.toggle('active', bVal === sizeValue);
        });

        // Applique à la forme sélectionnée si active
        if (selectedShapeIndex !== null && historyStack[selectedShapeIndex]) {
            const sh = historyStack[selectedShapeIndex];
            if (sh.type === 'text') {
                sh.sizeIndex = sizeValue;
            } else {
                sh.lineWidth = sizeValue;
            }
            redrawCanvas();
        }
    }

    function updateSizeToolbarUI() {
        const modal = document.getElementById('photoAnnotatorModal');
        const label = document.getElementById('annotatorSizeLabel');
        if (!modal || !label) return;

        const isTextContext = (currentTool === 'text') ||
            (selectedShapeIndex !== null && historyStack[selectedShapeIndex] && historyStack[selectedShapeIndex].type === 'text');

        if (isTextContext) {
            label.innerHTML = '<i data-lucide="type"></i> Taille texte :';
            const activeSz = (selectedShapeIndex !== null && historyStack[selectedShapeIndex]) ?
                (historyStack[selectedShapeIndex].sizeIndex || currentTextSizeIndex) : currentTextSizeIndex;
            setActiveSizeButtonsOnly(activeSz);
        } else {
            label.innerHTML = '<i data-lucide="scaling"></i> Épaisseur :';
            const activeSz = (selectedShapeIndex !== null && historyStack[selectedShapeIndex]) ?
                (historyStack[selectedShapeIndex].lineWidth || currentLineWidth) : currentLineWidth;
            setActiveSizeButtonsOnly(activeSz);
        }
        renderLucideIcons();
    }

    function setActiveSizeButtonsOnly(sizeValue) {
        const modal = document.getElementById('photoAnnotatorModal');
        if (!modal) return;

        modal.querySelectorAll('[data-size]').forEach(b => {
            const bVal = parseInt(b.getAttribute('data-size'), 10);
            b.classList.toggle('active', bVal === sizeValue);
        });
        modal.querySelectorAll('[data-popover-size]').forEach(b => {
            const bVal = parseInt(b.getAttribute('data-popover-size'), 10);
            b.classList.toggle('active', bVal === sizeValue);
        });
    }

    function updateToolCursor() {
        if (!canvas) return;
        if (currentTool === 'text') {
            canvas.style.cursor = 'text';
        } else if (currentTool === 'select') {
            canvas.style.cursor = 'default';
        } else {
            canvas.style.cursor = 'crosshair';
        }
    }

    function updateTipText() {
        const tip = document.getElementById('annotatorTip');
        if (!tip) return;
        if (currentTool === 'select') {
            tip.innerHTML = '<i data-lucide="mouse-pointer-2"></i> Cliquez sur une annotation pour la sélectionner. Glissez pour déplacer, étirez les poignées pour agrandir.';
        } else if (currentTool === 'text') {
            tip.innerHTML = '<i data-lucide="type"></i> Cliquez sur la photo à l\'endroit désiré pour saisir votre texte d\'annotation.';
        } else {
            tip.innerHTML = '<i data-lucide="info"></i> Tracez sur la photo pour entourer ou pointer. Basculez sur Sélection pour déplacer ou redimensionner.';
        }
        renderLucideIcons();
    }

    function updateDeleteBtnVisibility() {
        const btn = document.getElementById('annotatorDeleteSelectedBtn');
        if (btn) {
            btn.style.display = (selectedShapeIndex !== null && historyStack[selectedShapeIndex]) ? 'inline-flex' : 'none';
        }
    }

    function deleteSelectedShape() {
        if (selectedShapeIndex !== null && historyStack[selectedShapeIndex]) {
            historyStack.splice(selectedShapeIndex, 1);
            selectedShapeIndex = null;
            updateDeleteBtnVisibility();
            updateSizeToolbarUI();
            redrawCanvas();
        }
    }

    function getCanvasCoordinates(e) {
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
    }

    /* ══════════════ TAILLE DU TEXTE & BORNES ══════════════ */

    function getFontSizeForShape(shape) {
        const baseScale = Math.max(1, canvas.width / 1100);
        const sz = shape.sizeIndex || 5;

        // Paliers nets et très lisibles
        let mult = 26; // M par défaut
        if (sz <= 3) mult = 16;       // S
        else if (sz <= 5) mult = 26;  // M
        else if (sz <= 9) mult = 42;  // L (Grand)
        else mult = 64;               // XL (Très grand)

        return Math.max(13, Math.round(mult * baseScale));
    }

    function getShapeBounds(shape) {
        if (!shape) return { minX: 0, minY: 0, maxX: 0, maxY: 0, width: 0, height: 0 };

        if (shape.type === 'circle' || shape.type === 'arrow') {
            const minX = Math.min(shape.startX, shape.endX);
            const maxX = Math.max(shape.startX, shape.endX);
            const minY = Math.min(shape.startY, shape.endY);
            const maxY = Math.max(shape.startY, shape.endY);
            return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
        } else if (shape.type === 'text') {
            const baseScale = Math.max(1, canvas.width / 1100);
            const fontSize = getFontSizeForShape(shape);
            const paddingX = Math.round(14 * baseScale);
            const paddingY = Math.round(8 * baseScale);

            ctx.save();
            ctx.font = `600 ${fontSize}px ${CANVAS_FONT_FAMILY}`;
            const metrics = ctx.measureText(shape.text || '');
            ctx.restore();

            const textWidth = Math.max(10, metrics.width);
            const boxWidth = textWidth + (paddingX * 2);
            const boxHeight = fontSize + (paddingY * 2);
            const boxX = Math.max(4, Math.min(shape.x, canvas.width - boxWidth - 4));
            const boxY = Math.max(4, Math.min(shape.y - boxHeight, canvas.height - boxHeight - 4));

            return { minX: boxX, minY: boxY, maxX: boxX + boxWidth, maxY: boxY + boxHeight, width: boxWidth, height: boxHeight };
        } else if (shape.type === 'freehand') {
            if (!shape.points || shape.points.length === 0) {
                return { minX: 0, minY: 0, maxX: 0, maxY: 0, width: 0, height: 0 };
            }
            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
            shape.points.forEach(p => {
                if (p.x < minX) minX = p.x;
                if (p.x > maxX) maxX = p.x;
                if (p.y < minY) minY = p.y;
                if (p.y > maxY) maxY = p.y;
            });
            return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
        }
        return { minX: 0, minY: 0, maxX: 0, maxY: 0, width: 0, height: 0 };
    }

    function getShapeHandles(shape) {
        const bounds = getShapeBounds(shape);
        const scale = Math.max(1, canvas.width / 1100);
        const handleRadius = Math.max(7, Math.round(8 * scale));

        if (shape.type === 'arrow') {
            return [
                { id: 'arrow_start', x: shape.startX, y: shape.startY, radius: handleRadius },
                { id: 'arrow_end', x: shape.endX, y: shape.endY, radius: handleRadius },
            ];
        }

        const pad = 6 * scale;
        const x = bounds.minX - pad;
        const y = bounds.minY - pad;
        const w = bounds.width + (pad * 2);
        const h = bounds.height + (pad * 2);

        return [
            { id: 'nw', x: x, y: y, radius: handleRadius },
            { id: 'ne', x: x + w, y: y, radius: handleRadius },
            { id: 'se', x: x + w, y: y + h, radius: handleRadius },
            { id: 'sw', x: x, y: y + h, radius: handleRadius },
        ];
    }

    /* ══════════════ HIT-TESTING ══════════════ */

    function hitTestHandle(shape, coords) {
        if (!shape) return null;
        const handles = getShapeHandles(shape);
        for (let i = 0; i < handles.length; i++) {
            const h = handles[i];
            const dist = Math.hypot(coords.x - h.x, coords.y - h.y);
            if (dist <= h.radius * 1.8) {
                return h.id;
            }
        }
        return null;
    }

    function distanceToSegment(p, a, b) {
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const l2 = dx * dx + dy * dy;
        if (l2 === 0) return Math.hypot(p.x - a.x, p.y - a.y);
        let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / l2;
        t = Math.max(0, Math.min(1, t));
        return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
    }

    function hitTestShape(shape, coords) {
        const bounds = getShapeBounds(shape);
        const scale = Math.max(1, canvas.width / 1100);
        const tolerance = Math.max(12, Math.round(15 * scale));

        if (shape.type === 'circle') {
            const cx = (shape.startX + shape.endX) / 2;
            const cy = (shape.startY + shape.endY) / 2;
            const rx = Math.abs(shape.endX - shape.startX) / 2;
            const ry = Math.abs(shape.endY - shape.startY) / 2;
            const normDist = Math.pow((coords.x - cx) / (rx + tolerance), 2) + Math.pow((coords.y - cy) / (ry + tolerance), 2);
            return normDist <= 1.15;
        } else if (shape.type === 'arrow') {
            const dist = distanceToSegment(coords, { x: shape.startX, y: shape.startY }, { x: shape.endX, y: shape.endY });
            return dist <= tolerance;
        } else if (shape.type === 'text') {
            return (coords.x >= bounds.minX - tolerance && coords.x <= bounds.maxX + tolerance &&
                    coords.y >= bounds.minY - tolerance && coords.y <= bounds.maxY + tolerance);
        } else if (shape.type === 'freehand') {
            if (!shape.points || shape.points.length === 0) return false;
            for (let i = 0; i < shape.points.length - 1; i++) {
                const dist = distanceToSegment(coords, shape.points[i], shape.points[i + 1]);
                if (dist <= tolerance) return true;
            }
            return false;
        }
        return false;
    }

    /* ══════════════ POPOVER TEXTE ══════════════ */

    function showTextPopover(e, coords, existingText = '', existingSize = null) {
        const wrap = document.getElementById('canvasWrap');
        const popover = document.getElementById('annotatorTextPopover');
        const input = document.getElementById('annotatorTextInput');
        if (!wrap || !popover || !input) return;

        pendingTextCanvasCoords = coords;
        popover.style.borderColor = currentColor;

        const sizeToUse = existingSize !== null ? existingSize : currentTextSizeIndex;
        setActiveSizeButtonsOnly(sizeToUse);

        const wrapRect = wrap.getBoundingClientRect();
        const relativeX = e.clientX - wrapRect.left + wrap.scrollLeft;
        const relativeY = e.clientY - wrapRect.top + wrap.scrollTop;

        const posX = Math.max(10, Math.min(relativeX - 30, wrap.scrollWidth - 300));
        const posY = Math.max(10, Math.min(relativeY - 60, wrap.scrollHeight - 160));

        popover.style.left = `${posX}px`;
        popover.style.top = `${posY}px`;
        popover.classList.add('is-active');

        input.value = existingText || '';
        setTimeout(() => {
            input.focus();
            if (existingText) input.select();
        }, 50);

        renderLucideIcons();
    }

    function hideTextPopover() {
        const popover = document.getElementById('annotatorTextPopover');
        if (popover) popover.classList.remove('is-active');
        pendingTextCanvasCoords = null;
        editingTextIndex = null;
    }

    function submitTextAnnotation() {
        const input = document.getElementById('annotatorTextInput');
        if (!input || !pendingTextCanvasCoords) return;

        const textVal = input.value.trim();
        if (textVal) {
            if (editingTextIndex !== null && historyStack[editingTextIndex]) {
                // Modification d'un texte existant
                const sh = historyStack[editingTextIndex];
                sh.text = textVal;
                sh.color = currentColor;
                sh.sizeIndex = currentTextSizeIndex;
                selectedShapeIndex = editingTextIndex;
            } else {
                // Nouveau texte
                historyStack.push({
                    type: 'text',
                    x: pendingTextCanvasCoords.x,
                    y: pendingTextCanvasCoords.y,
                    text: textVal,
                    color: currentColor,
                    sizeIndex: currentTextSizeIndex
                });
                selectedShapeIndex = historyStack.length - 1;
            }
            updateDeleteBtnVisibility();
            updateSizeToolbarUI();
            redrawCanvas();
        }
        hideTextPopover();
    }

    function handleCanvasDblClick(e) {
        const coords = getCanvasCoordinates(e);
        for (let i = historyStack.length - 1; i >= 0; i--) {
            const shape = historyStack[i];
            if (shape.type === 'text' && hitTestShape(shape, coords)) {
                editingTextIndex = i;
                selectedShapeIndex = i;
                currentColor = shape.color || currentColor;
                currentTextSizeIndex = shape.sizeIndex || currentTextSizeIndex;
                updateSizeToolbarUI();
                showTextPopover(e, { x: shape.x, y: shape.y }, shape.text, shape.sizeIndex);
                return;
            }
        }
    }

    /* ══════════════ POINTER EVENTS (DESSIN & MANIPULATION) ══════════════ */

    function handlePointerDown(e) {
        const coords = getCanvasCoordinates(e);

        // 1. Clic sur une poignée de redimensionnement de l'élément sélectionné
        if (selectedShapeIndex !== null && historyStack[selectedShapeIndex]) {
            const handleId = hitTestHandle(historyStack[selectedShapeIndex], coords);
            if (handleId) {
                e.preventDefault();
                dragMode = 'resize';
                activeResizeHandle = handleId;
                dragStartCoords = coords;
                shapeSnapshot = JSON.parse(JSON.stringify(historyStack[selectedShapeIndex]));
                canvas.setPointerCapture(e.pointerId);
                return;
            }
        }

        // 2. Outil Sélection ou clic sur forme existante
        if (currentTool === 'select') {
            e.preventDefault();
            let foundIndex = null;
            for (let i = historyStack.length - 1; i >= 0; i--) {
                if (hitTestShape(historyStack[i], coords)) {
                    foundIndex = i;
                    break;
                }
            }

            if (foundIndex !== null) {
                selectedShapeIndex = foundIndex;
                dragMode = 'move';
                dragStartCoords = coords;
                shapeSnapshot = JSON.parse(JSON.stringify(historyStack[selectedShapeIndex]));
                updateDeleteBtnVisibility();
                updateSizeToolbarUI();
                canvas.setPointerCapture(e.pointerId);
                redrawCanvas();
                return;
            } else {
                selectedShapeIndex = null;
                updateDeleteBtnVisibility();
                updateSizeToolbarUI();
                redrawCanvas();
                return;
            }
        }

        // 3. Outil Texte
        if (currentTool === 'text') {
            e.preventDefault();
            selectedShapeIndex = null;
            editingTextIndex = null;
            updateDeleteBtnVisibility();
            showTextPopover(e, coords);
            return;
        }

        // 4. Nouveau tracé (Cercle, Flèche, Pinceau)
        hideTextPopover();
        selectedShapeIndex = null;
        updateDeleteBtnVisibility();

        e.preventDefault();
        isDrawing = true;
        canvas.setPointerCapture(e.pointerId);

        startX = coords.x;
        startY = coords.y;

        if (currentTool === 'freehand') {
            activeFreehandPath = {
                type: 'freehand',
                color: currentColor,
                lineWidth: currentLineWidth,
                points: [{ x: startX, y: startY }]
            };
        }
    }

    function handlePointerMove(e) {
        const coords = getCanvasCoordinates(e);

        // Redimensionnement
        if (dragMode === 'resize' && selectedShapeIndex !== null && historyStack[selectedShapeIndex]) {
            e.preventDefault();
            const shape = historyStack[selectedShapeIndex];

            if (shape.type === 'arrow') {
                if (activeResizeHandle === 'arrow_start') {
                    shape.startX = coords.x;
                    shape.startY = coords.y;
                } else if (activeResizeHandle === 'arrow_end') {
                    shape.endX = coords.x;
                    shape.endY = coords.y;
                }
            } else if (shape.type === 'circle') {
                if (activeResizeHandle === 'se') {
                    shape.endX = coords.x;
                    shape.endY = coords.y;
                } else if (activeResizeHandle === 'nw') {
                    shape.startX = coords.x;
                    shape.startY = coords.y;
                } else if (activeResizeHandle === 'ne') {
                    shape.endX = coords.x;
                    shape.startY = coords.y;
                } else if (activeResizeHandle === 'sw') {
                    shape.startX = coords.x;
                    shape.endY = coords.y;
                }
            } else if (shape.type === 'text') {
                const initialBounds = getShapeBounds(shapeSnapshot);
                const currentDist = Math.hypot(coords.x - initialBounds.minX, coords.y - initialBounds.minY);
                const initialDist = Math.hypot(initialBounds.width, initialBounds.height);
                if (initialDist > 0) {
                    const ratio = currentDist / initialDist;
                    if (ratio < 0.7) shape.sizeIndex = 3;      // S
                    else if (ratio < 1.25) shape.sizeIndex = 5; // M
                    else if (ratio < 1.7) shape.sizeIndex = 9;  // L
                    else shape.sizeIndex = 14;                  // XL
                    setActiveSizeButtonsOnly(shape.sizeIndex);
                }
            } else if (shape.type === 'freehand') {
                const initialBounds = getShapeBounds(shapeSnapshot);
                if (initialBounds.width > 0 && initialBounds.height > 0) {
                    const scaleX = Math.max(0.2, (coords.x - initialBounds.minX) / initialBounds.width);
                    const scaleY = Math.max(0.2, (coords.y - initialBounds.minY) / initialBounds.height);
                    shape.points = shapeSnapshot.points.map(p => ({
                        x: initialBounds.minX + (p.x - initialBounds.minX) * scaleX,
                        y: initialBounds.minY + (p.y - initialBounds.minY) * scaleY
                    }));
                }
            }
            redrawCanvas();
            return;
        }

        // Déplacement
        if (dragMode === 'move' && selectedShapeIndex !== null && historyStack[selectedShapeIndex]) {
            e.preventDefault();
            const dx = coords.x - dragStartCoords.x;
            const dy = coords.y - dragStartCoords.y;
            const shape = historyStack[selectedShapeIndex];

            if (shape.type === 'circle' || shape.type === 'arrow') {
                shape.startX = shapeSnapshot.startX + dx;
                shape.startY = shapeSnapshot.startY + dy;
                shape.endX = shapeSnapshot.endX + dx;
                shape.endY = shapeSnapshot.endY + dy;
            } else if (shape.type === 'text') {
                shape.x = shapeSnapshot.x + dx;
                shape.y = shapeSnapshot.y + dy;
            } else if (shape.type === 'freehand') {
                shape.points = shapeSnapshot.points.map(p => ({
                    x: p.x + dx,
                    y: p.y + dy
                }));
            }
            redrawCanvas();
            return;
        }

        // Curseur de survol en mode sélection
        if (currentTool === 'select' && !dragMode) {
            if (selectedShapeIndex !== null && historyStack[selectedShapeIndex]) {
                const handle = hitTestHandle(historyStack[selectedShapeIndex], coords);
                if (handle) {
                    if (handle === 'nw' || handle === 'se') canvas.style.cursor = 'nwse-resize';
                    else if (handle === 'ne' || handle === 'sw') canvas.style.cursor = 'nesw-resize';
                    else canvas.style.cursor = 'grab';
                    return;
                }
            }
            let isOverAny = false;
            for (let i = historyStack.length - 1; i >= 0; i--) {
                if (hitTestShape(historyStack[i], coords)) {
                    isOverAny = true;
                    break;
                }
            }
            canvas.style.cursor = isOverAny ? 'move' : 'default';
            return;
        }

        // Tracé en cours
        if (!isDrawing) return;
        e.preventDefault();

        if (currentTool === 'freehand') {
            activeFreehandPath.points.push({ x: coords.x, y: coords.y });
            redrawCanvas();
            drawShape(activeFreehandPath);
        } else {
            redrawCanvas();
            const tempShape = {
                type: currentTool,
                startX: startX,
                startY: startY,
                endX: coords.x,
                endY: coords.y,
                color: currentColor,
                lineWidth: currentLineWidth
            };
            drawShape(tempShape);
        }
    }

    function handlePointerUp(e) {
        if (dragMode) {
            dragMode = null;
            activeResizeHandle = null;
            dragStartCoords = null;
            shapeSnapshot = null;
            try { canvas.releasePointerCapture(e.pointerId); } catch (_) {}
            redrawCanvas();
            return;
        }

        if (!isDrawing || currentTool === 'text' || currentTool === 'select') return;
        isDrawing = false;
        try { canvas.releasePointerCapture(e.pointerId); } catch (_) {}

        const coords = getCanvasCoordinates(e);

        if (currentTool === 'freehand') {
            if (activeFreehandPath && activeFreehandPath.points.length > 1) {
                historyStack.push(activeFreehandPath);
                selectedShapeIndex = historyStack.length - 1;
                updateDeleteBtnVisibility();
                updateSizeToolbarUI();
            }
            activeFreehandPath = null;
        } else {
            const dist = Math.hypot(coords.x - startX, coords.y - startY);
            if (dist > 5) {
                historyStack.push({
                    type: currentTool,
                    startX: startX,
                    startY: startY,
                    endX: coords.x,
                    endY: coords.y,
                    color: currentColor,
                    lineWidth: currentLineWidth
                });
                selectedShapeIndex = historyStack.length - 1;
                updateDeleteBtnVisibility();
                updateSizeToolbarUI();
            }
        }
        redrawCanvas();
    }

    /* ══════════════ RENDU DU CANVAS & OVERLAY DE SÉLECTION ══════════════ */

    function redrawCanvas() {
        if (!originalImage) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(originalImage, 0, 0);

        // Dessine toutes les formes
        historyStack.forEach(shape => drawShape(shape));

        // Overlay de sélection fin et élégant
        if (selectedShapeIndex !== null && historyStack[selectedShapeIndex]) {
            drawSelectionOverlay(historyStack[selectedShapeIndex]);
        }
    }

    function drawSelectionOverlay(shape) {
        const bounds = getShapeBounds(shape);
        const scale = Math.max(1, canvas.width / 1100);
        const handleR = Math.max(6, Math.round(7.5 * scale));

        ctx.save();
        ctx.strokeStyle = '#5299D3'; // Bleu acier BV cinématique
        ctx.lineWidth = Math.max(1.5, Math.round(1.8 * scale));
        ctx.setLineDash([5 * scale, 5 * scale]);

        if (shape.type === 'arrow') {
            ctx.beginPath();
            ctx.moveTo(shape.startX, shape.startY);
            ctx.lineTo(shape.endX, shape.endY);
            ctx.stroke();

            ctx.setLineDash([]);
            drawHandle(shape.startX, shape.startY, handleR, '#5299D3');
            drawHandle(shape.endX, shape.endY, handleR, '#5299D3');
        } else {
            const pad = 6 * scale;
            const x = bounds.minX - pad;
            const y = bounds.minY - pad;
            const w = bounds.width + (pad * 2);
            const h = bounds.height + (pad * 2);

            ctx.strokeRect(x, y, w, h);

            ctx.setLineDash([]);
            drawHandle(x, y, handleR, '#5299D3');
            drawHandle(x + w, y, handleR, '#5299D3');
            drawHandle(x + w, y + h, handleR, '#5299D3');
            drawHandle(x, y + h, handleR, '#5299D3');
        }
        ctx.restore();
    }

    function drawHandle(x, y, r, strokeColor) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(x, y, r, 0, 2 * Math.PI);
        ctx.fillStyle = '#FFFFFF';
        ctx.shadowColor = 'rgba(0, 0, 0, 0.25)';
        ctx.shadowBlur = 4;
        ctx.fill();
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = Math.max(2, r * 0.3);
        ctx.stroke();
        ctx.restore();
    }

    function drawShape(shape) {
        ctx.save();
        ctx.strokeStyle = shape.color;
        ctx.fillStyle = shape.color;
        ctx.lineWidth = shape.lineWidth || currentLineWidth;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        // Ombre très fine et légère pour décoller le trait
        ctx.shadowColor = 'rgba(0, 0, 0, 0.35)';
        ctx.shadowBlur = 4;
        ctx.shadowOffsetX = 1;
        ctx.shadowOffsetY = 1;

        if (shape.type === 'circle') {
            const centerX = (shape.startX + shape.endX) / 2;
            const centerY = (shape.startY + shape.endY) / 2;
            const radiusX = Math.abs(shape.endX - shape.startX) / 2;
            const radiusY = Math.abs(shape.endY - shape.startY) / 2;

            ctx.beginPath();
            ctx.ellipse(centerX, centerY, radiusX, radiusY, 0, 0, 2 * Math.PI);
            ctx.stroke();
        } else if (shape.type === 'arrow') {
            const fromX = shape.startX;
            const fromY = shape.startY;
            const toX = shape.endX;
            const toY = shape.endY;
            const headlen = Math.max(16, (shape.lineWidth || 5) * 3.2);
            const angle = Math.atan2(toY - fromY, toX - fromX);

            ctx.beginPath();
            ctx.moveTo(fromX, fromY);
            ctx.lineTo(toX, toY);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(toX, toY);
            ctx.lineTo(toX - headlen * Math.cos(angle - Math.PI / 6), toY - headlen * Math.sin(angle - Math.PI / 6));
            ctx.lineTo(toX - headlen * Math.cos(angle + Math.PI / 6), toY - headlen * Math.sin(angle + Math.PI / 6));
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
        } else if (shape.type === 'freehand') {
            if (shape.points && shape.points.length > 0) {
                ctx.beginPath();
                ctx.moveTo(shape.points[0].x, shape.points[0].y);
                for (let i = 1; i < shape.points.length; i++) {
                    ctx.lineTo(shape.points[i].x, shape.points[i].y);
                }
                ctx.stroke();
            }
        } else if (shape.type === 'text') {
            const baseScale = Math.max(1, canvas.width / 1100);
            const fontSize = getFontSizeForShape(shape);
            const paddingX = Math.round(14 * baseScale);
            const paddingY = Math.round(8 * baseScale);
            const borderRadius = Math.round(6 * baseScale);

            ctx.font = `600 ${fontSize}px ${CANVAS_FONT_FAMILY}`;
            const metrics = ctx.measureText(shape.text || '');
            const textWidth = Math.max(10, metrics.width);
            const textHeight = fontSize;

            const boxWidth = textWidth + (paddingX * 2);
            const boxHeight = textHeight + (paddingY * 2);
            const boxX = Math.max(4, Math.min(shape.x, canvas.width - boxWidth - 4));
            const boxY = Math.max(4, Math.min(shape.y - boxHeight, canvas.height - boxHeight - 4));

            // Fond blanc net avec ombre douce
            ctx.shadowColor = 'rgba(0, 0, 0, 0.25)';
            ctx.shadowBlur = 6;
            ctx.shadowOffsetX = 1;
            ctx.shadowOffsetY = 2;
            ctx.fillStyle = '#FFFFFF';
            ctx.strokeStyle = shape.color;
            ctx.lineWidth = Math.max(2, Math.round(2.5 * baseScale));

            ctx.beginPath();
            if (typeof ctx.roundRect === 'function') {
                ctx.roundRect(boxX, boxY, boxWidth, boxHeight, borderRadius);
            } else {
                ctx.rect(boxX, boxY, boxWidth, boxHeight);
            }
            ctx.fill();
            ctx.stroke();

            // Point d'ancrage subtil
            ctx.fillStyle = shape.color;
            ctx.beginPath();
            ctx.arc(shape.x, shape.y, Math.round(4 * baseScale), 0, 2 * Math.PI);
            ctx.fill();

            // Texte dans la couleur sombre contrastée
            ctx.fillStyle = '#151515';
            ctx.shadowColor = 'transparent';
            ctx.shadowBlur = 0;
            ctx.textBaseline = 'middle';
            ctx.fillText(shape.text || '', boxX + paddingX, boxY + (boxHeight / 2));
        }

        ctx.restore();
    }

    /* ══════════════ FERMETURE & SAUVEGARDE ══════════════ */

    function closeModal() {
        hideTextPopover();
        const modal = document.getElementById('photoAnnotatorModal');
        if (modal) {
            modal.style.display = 'none';
            modal.classList.remove('is-active');
        }
        originalImage = null;
        originalBaseSource = null;
        originalFile = null;
        historyStack = [];
        selectedShapeIndex = null;
        editingTextIndex = null;
        updateDeleteBtnVisibility();
        onSaveCallback = null;
    }

    function saveAnnotation() {
        if (!canvas) return;
        hideTextPopover();

        selectedShapeIndex = null;
        redrawCanvas();

        const currentAnnotations = JSON.parse(JSON.stringify(historyStack));

        canvas.toBlob(blob => {
            if (!blob) return;
            const filename = originalFile ? originalFile.name : `annotated_${Date.now()}.jpg`;
            const annotatedFile = new File([blob], filename, { type: 'image/jpeg', lastModified: Date.now() });
            const dataUrl = canvas.toDataURL('image/jpeg', 0.92);

            if (typeof onSaveCallback === 'function') {
                // Renvoie le fichier annoté, la dataUrl ET la pile d'annotations vectorielles
                onSaveCallback(annotatedFile, dataUrl, currentAnnotations);
            }
            closeModal();
        }, 'image/jpeg', 0.92);
    }

    /**
     * Ouvre l'annotateur avec source d'image et support des annotations existantes.
     * @param {File|Blob|string} imageSource Source de l'image (fichier, blob ou dataURL)
     * @param {Function} callback Callback (annotatedFile, dataUrl, annotationsStack)
     * @param {Object} options Options complémentaires { annotations: Array, baseImage: File|Blob|string }
     */
    function openPhotoAnnotator(imageSource, callback, options = {}) {
        createModalDom();
        onSaveCallback = callback;
        hideTextPopover();

        // Récupère l'historique d'annotations existant si fourni (permet d'éditer sans reset)
        if (options && options.annotations && Array.isArray(options.annotations)) {
            historyStack = JSON.parse(JSON.stringify(options.annotations));
        } else {
            historyStack = [];
        }

        selectedShapeIndex = null;
        editingTextIndex = null;
        updateDeleteBtnVisibility();
        updateSizeToolbarUI();

        // Image de fond originale (sans brûlure de pixel si disponible)
        originalBaseSource = (options && options.baseImage) ? options.baseImage : imageSource;

        const img = new Image();
        img.crossOrigin = 'anonymous';

        function onLoad() {
            originalImage = img;
            canvas.width = img.naturalWidth || img.width;
            canvas.height = img.naturalHeight || img.height;
            redrawCanvas();

            const modal = document.getElementById('photoAnnotatorModal');
            if (modal) {
                modal.style.display = 'flex';
                modal.classList.add('is-active');
            }

            const wrap = document.getElementById('canvasWrap');
            if (wrap) wrap.scrollTop = 0;

            renderLucideIcons();
        }

        if (originalBaseSource instanceof File || originalBaseSource instanceof Blob) {
            originalFile = originalBaseSource;
            const reader = new FileReader();
            reader.onload = e => {
                img.onload = onLoad;
                img.src = e.target.result;
            };
            reader.readAsDataURL(originalBaseSource);
        } else if (typeof originalBaseSource === 'string') {
            originalFile = null;
            img.onload = onLoad;
            img.src = originalBaseSource;
        }
    }

    function replaceFileInInput(input, index, newFile) {
        if (!input || !window.DataTransfer) return;
        try {
            const dt = new DataTransfer();
            const files = Array.from(input.files);
            files.forEach((f, i) => {
                if (i === index) {
                    dt.items.add(newFile);
                } else {
                    dt.items.add(f);
                }
            });
            input.files = dt.files;
        } catch (err) {
            console.warn("replaceFileInInput: non supporté par ce navigateur, stockage de secours actif", err);
        }
    }

    // Export global
    window.openPhotoAnnotator = openPhotoAnnotator;
    window.replaceFileInInput = replaceFileInInput;

})();
