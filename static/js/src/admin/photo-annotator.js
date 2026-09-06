/**
 * photo-annotator.js — Outil d'annotation directe sur photos (Canvas Image Marker).
 * Direction Artistique Belle Vitesse (Light Mode, finesse, aligné sur incidents_list.html et productions_list.html).
 */

(function () {
    'use strict';

    // Outils et réglages par défaut (couleurs fidèles à la charte light admin : --red-error, --blue-info, etc.)
    let currentTool = 'circle'; // 'select', 'circle', 'arrow', 'freehand', 'text'
    let currentColor = '#b91c1c'; // Rouge incident / défaut par défaut (--red-error)
    let currentLineWidth = 5;
    let originalImage = null;
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

    // Pile des actions / annotations
    let historyStack = [];

    function createModalDom() {
        if (document.getElementById('photoAnnotatorModal')) return;

        const modalHtml = `
        <div id="photoAnnotatorModal" class="bv-annotator-overlay" style="display: none;">
            <div class="bv-annotator-container">
                <!-- Header Light Mode -->
                <div class="bv-annotator-header">
                    <div class="bv-annotator-title">
                        <span class="bv-annotator-badge-icon">✏️</span>
                        <span class="bv-annotator-title-text">Constat & Annotation Photo</span>
                    </div>
                    <button type="button" class="bv-annotator-close" id="annotatorCloseBtn" title="Fermer (Échap)">&times;</button>
                </div>

                <!-- Barre d'outils Fine & Épurée -->
                <div class="bv-annotator-toolbar">
                    <div class="bv-tool-group">
                        <button type="button" class="bv-btn-tool" data-tool="select" title="Sélectionner, déplacer ou redimensionner">👆 Sélection</button>
                        <button type="button" class="bv-btn-tool active" data-tool="circle" title="Cercle (entourer un impact)">⭕ Cercle</button>
                        <button type="button" class="bv-btn-tool" data-tool="arrow" title="Flèche (pointer un défaut)">➡️ Flèche</button>
                        <button type="button" class="bv-btn-tool" data-tool="freehand" title="Tracé libre">✏️ Pinceau</button>
                        <button type="button" class="bv-btn-tool" data-tool="text" title="Ajouter une étiquette texte">🔤 Texte</button>
                    </div>

                    <div class="bv-tool-divider"></div>

                    <!-- Nuancier issu du design system Belle Vitesse -->
                    <div class="bv-tool-group" title="Couleur de l'annotation">
                        <button type="button" class="bv-swatch active" data-color="#b91c1c" style="background:#b91c1c;" title="Rouge (Défaut / Impact)"></button>
                        <button type="button" class="bv-swatch" data-color="#d97706" style="background:#d97706;" title="Ambre (Attention / À surveiller)"></button>
                        <button type="button" class="bv-swatch" data-color="#0369a1" style="background:#0369a1;" title="Bleu (Repère technique)"></button>
                        <button type="button" class="bv-swatch" data-color="#28a745" style="background:#28a745;" title="Vert (Conforme / Réf)"></button>
                        <button type="button" class="bv-swatch" data-color="#151515" style="background:#151515;" title="Noir (Contraste carrosserie blanche)"></button>
                        <button type="button" class="bv-swatch" data-color="#ffffff" style="background:#ffffff; border-color:#d1d5db;" title="Blanc (Contraste carrosserie sombre)"></button>
                    </div>

                    <div class="bv-tool-divider"></div>

                    <!-- Épaisseur -->
                    <div class="bv-tool-group">
                        <button type="button" class="bv-btn-size" data-size="3" title="Tracé fin">Fin</button>
                        <button type="button" class="bv-btn-size active" data-size="5" title="Tracé moyen">Moyen</button>
                        <button type="button" class="bv-btn-size" data-size="9" title="Tracé épais">Épais</button>
                    </div>

                    <div class="bv-tool-divider"></div>

                    <!-- Mode d'affichage (Défilement scrollable vs Vue globale) -->
                    <div class="bv-tool-group">
                        <button type="button" class="bv-btn-tool active" id="annotatorViewScrollBtn" title="Photo grand format avec défilement vertical complet">↕️ Défilement</button>
                        <button type="button" class="bv-btn-tool" id="annotatorViewFitBtn" title="Ajuster l'ensemble de la photo à la fenêtre">🔍 Vue globale</button>
                    </div>

                    <div class="bv-tool-group u-ml-auto">
                        <button type="button" class="bv-btn-tool bv-btn-danger" id="annotatorDeleteSelectedBtn" title="Supprimer l'annotation sélectionnée (Touche Suppr)" style="display: none;">🗑️ Supprimer</button>
                        <button type="button" class="bv-btn-tool" id="annotatorUndoBtn" title="Annuler le dernier tracé (Ctrl+Z)">↩️ Annuler</button>
                        <button type="button" class="bv-btn-tool" id="annotatorClearBtn" title="Tout effacer">🔄 Effacer tout</button>
                    </div>
                </div>

                <!-- Zone Canvas Défilable en Light Mode -->
                <div class="bv-annotator-canvas-wrap mode-scroll" id="canvasWrap">
                    <canvas id="photoAnnotatorCanvas"></canvas>

                    <!-- Popover flottant de texte Light Mode -->
                    <div id="annotatorTextPopover" class="bv-text-popover" style="display: none;">
                        <input type="text" id="annotatorTextInput" placeholder="Ex: Rayure 15cm, éclat carrosserie..." maxlength="75" />
                        <button type="button" id="annotatorTextOkBtn" class="bv-popover-btn bv-popover-btn-ok" title="Valider">OK</button>
                        <button type="button" id="annotatorTextCancelBtn" class="bv-popover-btn bv-popover-btn-cancel" title="Annuler">&times;</button>
                    </div>
                </div>

                <!-- Footer Light Mode -->
                <div class="bv-annotator-footer">
                    <span class="bv-annotator-tip" id="annotatorTip">
                        Tracez sur la photo pour annoter. Utilisez 👆 Sélection pour déplacer ou redimensionner un repère.
                    </span>
                    <div class="u-flex u-gap-2">
                        <button type="button" class="admin-btn admin-btn-secondary" id="annotatorCancelBtn">Annuler</button>
                        <button type="button" class="admin-btn admin-btn-primary" id="annotatorSaveBtn">💾 Enregistrer l'annotation</button>
                    </div>
                </div>
            </div>
        </div>
        `;

        const style = document.createElement('style');
        style.textContent = `
            /* ── ANNOTATEUR PHOTO LIGHT MODE — DIRECTION ARTISTIQUE BELLE VITESSE ── */
            .bv-annotator-overlay {
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(15, 23, 42, 0.45);
                backdrop-filter: blur(4px);
                -webkit-backdrop-filter: blur(4px);
                z-index: 99999;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 1rem;
                font-family: var(--font-primary, 'Poppins', sans-serif);
            }
            .bv-annotator-container {
                background: #FFFFFF;
                color: var(--grey-1, #151515);
                border-radius: 8px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.16);
                width: 100%;
                max-width: 1020px;
                height: 92vh;
                display: flex;
                flex-direction: column;
                overflow: hidden;
                border: 1px solid var(--white-3, #e9ecef);
            }
            .bv-annotator-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0.85rem 1.4rem;
                background: #FFFFFF;
                border-bottom: 1px solid var(--white-3, #e9ecef);
                flex-shrink: 0;
            }
            .bv-annotator-title {
                display: flex;
                align-items: center;
                gap: 0.6rem;
            }
            .bv-annotator-badge-icon {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 28px;
                height: 28px;
                background: var(--neutral-bg, #f4f4f4);
                border-radius: 6px;
                font-size: 0.85rem;
            }
            .bv-annotator-title-text {
                font-size: 1rem;
                font-weight: 600;
                color: var(--grey-1, #151515);
            }
            .bv-annotator-close {
                background: none;
                border: none;
                color: var(--grey-2, #515151);
                font-size: 1.5rem;
                cursor: pointer;
                line-height: 1;
                padding: 0.2rem 0.5rem;
                border-radius: 4px;
                transition: background 0.15s ease, color 0.15s ease;
            }
            .bv-annotator-close:hover {
                background: var(--white-3, #e9ecef);
                color: var(--grey-1, #151515);
            }

            /* Toolbar Light */
            .bv-annotator-toolbar {
                display: flex;
                align-items: center;
                flex-wrap: wrap;
                gap: 0.5rem;
                padding: 0.6rem 1.2rem;
                background: #f8f9fa;
                border-bottom: 1px solid var(--white-3, #e9ecef);
                flex-shrink: 0;
            }
            .bv-tool-group {
                display: flex;
                align-items: center;
                gap: 0.35rem;
            }
            .bv-tool-divider {
                width: 1px;
                height: 22px;
                background: var(--white-3, #e9ecef);
                margin: 0 0.25rem;
            }
            .bv-btn-tool, .bv-btn-size {
                background: #FFFFFF;
                color: var(--grey-1, #151515);
                border: 1px solid var(--white-3, #e9ecef);
                border-radius: 5px;
                padding: 0.4rem 0.75rem;
                font-size: 0.8rem;
                font-family: var(--font-primary, 'Poppins', sans-serif);
                font-weight: 500;
                cursor: pointer;
                transition: all 0.15s ease;
                white-space: nowrap;
            }
            .bv-btn-tool:hover, .bv-btn-size:hover {
                background: var(--white-2, #fafafa);
                border-color: #d1d5db;
                color: var(--grey-1, #151515);
            }
            .bv-btn-tool.active, .bv-btn-size.active {
                background: var(--admin-accent, #FFC845) !important;
                border-color: var(--admin-accent, #FFC845) !important;
                color: var(--grey-1, #151515) !important;
                font-weight: 600 !important;
                box-shadow: 0 1px 3px rgba(255, 200, 69, 0.3);
            }
            .bv-btn-danger {
                background: #fee2e2 !important;
                border-color: #fecaca !important;
                color: #b91c1c !important;
                font-weight: 600;
            }
            .bv-btn-danger:hover {
                background: #fca5a5 !important;
                color: #7f1d1d !important;
            }

            /* Swatches */
            .bv-swatch {
                width: 22px;
                height: 22px;
                border-radius: 50%;
                border: 2px solid #FFFFFF;
                box-shadow: 0 0 0 1px #d1d5db;
                cursor: pointer;
                transition: transform 0.15s ease, box-shadow 0.15s ease;
            }
            .bv-swatch:hover {
                transform: scale(1.15);
            }
            .bv-swatch.active {
                box-shadow: 0 0 0 2px var(--admin-accent, #FFC845);
                transform: scale(1.1);
            }

            /* Canvas Wrap Light */
            .bv-annotator-canvas-wrap {
                position: relative;
                flex: 1;
                background: #f1f3f5;
                display: flex;
                justify-content: center;
                align-items: flex-start;
                overflow-y: auto;
                overflow-x: auto;
                padding: 1.5rem 1rem;
                -webkit-overflow-scrolling: touch;
            }
            .bv-annotator-canvas-wrap::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }
            .bv-annotator-canvas-wrap::-webkit-scrollbar-track {
                background: #f1f3f5;
            }
            .bv-annotator-canvas-wrap::-webkit-scrollbar-thumb {
                background: #ced4da;
                border-radius: 4px;
            }
            .bv-annotator-canvas-wrap::-webkit-scrollbar-thumb:hover {
                background: #adb5bd;
            }

            /* Mode Défilement */
            .bv-annotator-canvas-wrap.mode-scroll #photoAnnotatorCanvas {
                width: 100%;
                max-width: 900px;
                height: auto;
                display: block;
                margin: 0 auto;
                background: #FFFFFF;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
                border: 1px solid #dcdfe3;
                border-radius: 4px;
            }

            /* Mode Vue Globale */
            .bv-annotator-canvas-wrap.mode-fit {
                align-items: center;
            }
            .bv-annotator-canvas-wrap.mode-fit #photoAnnotatorCanvas {
                max-width: 100%;
                max-height: 100%;
                width: auto;
                height: auto;
                display: block;
                margin: auto;
                object-fit: contain;
                background: #FFFFFF;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
                border: 1px solid #dcdfe3;
                border-radius: 4px;
            }

            /* Popover Texte Light */
            .bv-text-popover {
                position: absolute;
                z-index: 1000;
                background: #FFFFFF;
                border: 1.5px solid var(--admin-accent, #FFC845);
                border-radius: 6px;
                padding: 5px 6px;
                display: flex;
                align-items: center;
                gap: 5px;
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
            }
            .bv-text-popover input {
                background: #f8f9fa;
                border: 1px solid var(--white-3, #e9ecef);
                border-radius: 4px;
                color: var(--grey-1, #151515);
                padding: 5px 8px;
                font-size: 0.82rem;
                font-family: var(--font-primary, 'Poppins', sans-serif);
                width: 190px;
                outline: none;
            }
            .bv-text-popover input:focus {
                border-color: var(--admin-accent, #FFC845);
                background: #FFFFFF;
            }
            .bv-popover-btn {
                border: none;
                border-radius: 4px;
                padding: 5px 9px;
                font-size: 0.8rem;
                cursor: pointer;
                font-family: var(--font-primary, 'Poppins', sans-serif);
                transition: all 0.15s ease;
            }
            .bv-popover-btn-ok {
                background: var(--grey-1, #151515);
                color: #FFFFFF;
                font-weight: 600;
            }
            .bv-popover-btn-ok:hover {
                background: var(--admin-accent, #FFC845);
                color: var(--grey-1, #151515);
            }
            .bv-popover-btn-cancel {
                background: var(--white-3, #e9ecef);
                color: var(--grey-2, #515151);
                font-size: 0.9rem;
            }
            .bv-popover-btn-cancel:hover {
                background: #d1d5db;
                color: var(--grey-1, #151515);
            }

            /* Footer Light */
            .bv-annotator-footer {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0.85rem 1.4rem;
                background: #FFFFFF;
                border-top: 1px solid var(--white-3, #e9ecef);
                flex-wrap: wrap;
                gap: 0.5rem;
                flex-shrink: 0;
            }
            .bv-annotator-tip {
                font-size: 0.8rem;
                color: var(--grey-2, #515151);
            }

            /* Vignettes de prévisualisation avec badge d'édition discret */
            .photo-preview-item {
                position: relative;
                display: inline-block;
                margin: 4px;
            }
            .photo-preview-item img {
                display: block;
                border-radius: 4px;
            }
            .photo-preview-item .annotator-edit-badge {
                position: absolute;
                bottom: 4px;
                right: 4px;
                background: #FFFFFF;
                color: var(--grey-1, #151515);
                border: 1px solid var(--white-3, #e9ecef);
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                font-family: var(--font-primary, 'Poppins', sans-serif);
                font-weight: 500;
                cursor: pointer;
                box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
                transition: all 0.15s ease;
            }
            .photo-preview-item .annotator-edit-badge:hover {
                background: var(--admin-accent, #FFC845);
                border-color: var(--admin-accent, #FFC845);
                color: var(--grey-1, #151515);
            }
        `;
        document.head.appendChild(style);

        const div = document.createElement('div');
        div.innerHTML = modalHtml;
        document.body.appendChild(div.firstElementChild);

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

        // Épaisseur
        modal.querySelectorAll('[data-size]').forEach(btn => {
            btn.onclick = () => {
                modal.querySelectorAll('[data-size]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentLineWidth = parseInt(btn.getAttribute('data-size'), 10);

                if (selectedShapeIndex !== null && historyStack[selectedShapeIndex]) {
                    const sh = historyStack[selectedShapeIndex];
                    if (sh.type === 'text') {
                        sh.sizeIndex = currentLineWidth;
                    } else {
                        sh.lineWidth = currentLineWidth;
                    }
                    redrawCanvas();
                }
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
            if (!modal || modal.style.display === 'none') return;
            if (document.activeElement === popoverInput) return;

            if (e.key === 'Delete' || e.key === 'Backspace') {
                if (selectedShapeIndex !== null) {
                    e.preventDefault();
                    deleteSelectedShape();
                }
            } else if (e.key === 'Escape') {
                closeModal();
            }
        });

        // Pointer Events sur le canvas
        canvas.addEventListener('pointerdown', handlePointerDown);
        canvas.addEventListener('pointermove', handlePointerMove);
        canvas.addEventListener('pointerup', handlePointerUp);
        canvas.addEventListener('pointercancel', handlePointerUp);
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
            tip.textContent = "💡 Cliquez sur une annotation pour la sélectionner. Glissez pour déplacer, attrapez les poignées pour redimensionner.";
        } else if (currentTool === 'text') {
            tip.textContent = "💡 Cliquez sur la photo à l'endroit désiré pour saisir votre texte d'annotation.";
        } else {
            tip.textContent = "💡 Tracez sur la photo pour entourer ou pointer. Basculez sur 👆 Sélection pour déplacer ou redimensionner.";
        }
    }

    function updateDeleteBtnVisibility() {
        const btn = document.getElementById('annotatorDeleteSelectedBtn');
        if (btn) {
            btn.style.display = (selectedShapeIndex !== null && historyStack[selectedShapeIndex]) ? 'inline-block' : 'none';
        }
    }

    function deleteSelectedShape() {
        if (selectedShapeIndex !== null && historyStack[selectedShapeIndex]) {
            historyStack.splice(selectedShapeIndex, 1);
            selectedShapeIndex = null;
            updateDeleteBtnVisibility();
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

    /* ══════════════ CALCUL DES BORNES & POIGNÉES ══════════════ */

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
            const fontMultiplier = shape.sizeIndex === 3 ? 16 : (shape.sizeIndex === 9 ? 28 : 22);
            const fontSize = Math.round(fontMultiplier * baseScale);
            const paddingX = Math.round(12 * baseScale);
            const paddingY = Math.round(6 * baseScale);

            ctx.save();
            ctx.font = `600 ${fontSize}px var(--font-primary, 'Poppins', sans-serif)`;
            const metrics = ctx.measureText(shape.text);
            ctx.restore();

            const boxWidth = metrics.width + (paddingX * 2);
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

        const pad = 5 * scale;
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
            return normDist <= 1.1;
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

    function showTextPopover(e, coords) {
        const wrap = document.getElementById('canvasWrap');
        const popover = document.getElementById('annotatorTextPopover');
        const input = document.getElementById('annotatorTextInput');
        if (!wrap || !popover || !input) return;

        pendingTextCanvasCoords = coords;
        popover.style.borderColor = currentColor;

        const wrapRect = wrap.getBoundingClientRect();
        const relativeX = e.clientX - wrapRect.left + wrap.scrollLeft;
        const relativeY = e.clientY - wrapRect.top + wrap.scrollTop;

        const posX = Math.max(10, Math.min(relativeX - 20, wrap.scrollWidth - 250));
        const posY = Math.max(10, Math.min(relativeY - 45, wrap.scrollHeight - 50));

        popover.style.left = `${posX}px`;
        popover.style.top = `${posY}px`;
        popover.style.display = 'flex';

        input.value = '';
        setTimeout(() => input.focus(), 50);
    }

    function hideTextPopover() {
        const popover = document.getElementById('annotatorTextPopover');
        if (popover) popover.style.display = 'none';
        pendingTextCanvasCoords = null;
    }

    function submitTextAnnotation() {
        const input = document.getElementById('annotatorTextInput');
        if (!input || !pendingTextCanvasCoords) return;

        const textVal = input.value.trim();
        if (textVal) {
            historyStack.push({
                type: 'text',
                x: pendingTextCanvasCoords.x,
                y: pendingTextCanvasCoords.y,
                text: textVal,
                color: currentColor,
                sizeIndex: currentLineWidth
            });
            selectedShapeIndex = historyStack.length - 1;
            updateDeleteBtnVisibility();
            redrawCanvas();
        }
        hideTextPopover();
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
                canvas.setPointerCapture(e.pointerId);
                redrawCanvas();
                return;
            } else {
                selectedShapeIndex = null;
                updateDeleteBtnVisibility();
                redrawCanvas();
                return;
            }
        }

        // 3. Outil Texte
        if (currentTool === 'text') {
            e.preventDefault();
            selectedShapeIndex = null;
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
                    if (ratio < 0.75) shape.sizeIndex = 3;
                    else if (ratio > 1.35) shape.sizeIndex = 9;
                    else shape.sizeIndex = 5;
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
        ctx.strokeStyle = '#0284c7'; // Bleu sélection fin et précis
        ctx.lineWidth = Math.max(1.5, Math.round(1.8 * scale));
        ctx.setLineDash([5 * scale, 5 * scale]);

        if (shape.type === 'arrow') {
            ctx.beginPath();
            ctx.moveTo(shape.startX, shape.startY);
            ctx.lineTo(shape.endX, shape.endY);
            ctx.stroke();

            ctx.setLineDash([]);
            drawHandle(shape.startX, shape.startY, handleR, '#0284c7');
            drawHandle(shape.endX, shape.endY, handleR, '#0284c7');
        } else {
            const pad = 5 * scale;
            const x = bounds.minX - pad;
            const y = bounds.minY - pad;
            const w = bounds.width + (pad * 2);
            const h = bounds.height + (pad * 2);

            ctx.strokeRect(x, y, w, h);

            ctx.setLineDash([]);
            drawHandle(x, y, handleR, '#0284c7');
            drawHandle(x + w, y, handleR, '#0284c7');
            drawHandle(x + w, y + h, handleR, '#0284c7');
            drawHandle(x, y + h, handleR, '#0284c7');
        }
        ctx.restore();
    }

    function drawHandle(x, y, r, strokeColor) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(x, y, r, 0, 2 * Math.PI);
        ctx.fillStyle = '#FFFFFF';
        ctx.shadowColor = 'rgba(0, 0, 0, 0.2)';
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
        ctx.lineWidth = shape.lineWidth;
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
            const headlen = Math.max(16, shape.lineWidth * 3.2);
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
            // Étiquette Badge Finesse : Fond blanc pur semi-opaque, bordure colorée fine, typographie Poppins
            const baseScale = Math.max(1, canvas.width / 1100);
            const fontMultiplier = shape.sizeIndex === 3 ? 15 : (shape.sizeIndex === 9 ? 25 : 19);
            const fontSize = Math.round(fontMultiplier * baseScale);
            const paddingX = Math.round(12 * baseScale);
            const paddingY = Math.round(6 * baseScale);
            const borderRadius = Math.round(4 * baseScale);

            ctx.font = `600 ${fontSize}px var(--font-primary, 'Poppins', sans-serif)`;
            const metrics = ctx.measureText(shape.text);
            const textWidth = metrics.width;
            const textHeight = fontSize;

            const boxWidth = textWidth + (paddingX * 2);
            const boxHeight = textHeight + (paddingY * 2);
            const boxX = Math.max(4, Math.min(shape.x, canvas.width - boxWidth - 4));
            const boxY = Math.max(4, Math.min(shape.y - boxHeight, canvas.height - boxHeight - 4));

            // Fond blanc net avec ombre douce
            ctx.shadowColor = 'rgba(0, 0, 0, 0.2)';
            ctx.shadowBlur = 6;
            ctx.fillStyle = '#FFFFFF';
            ctx.strokeStyle = shape.color;
            ctx.lineWidth = Math.max(1.5, Math.round(2 * baseScale));

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
            ctx.arc(shape.x, shape.y, Math.round(3.5 * baseScale), 0, 2 * Math.PI);
            ctx.fill();

            // Texte dans la couleur de repère ou gris-1
            ctx.fillStyle = '#151515';
            ctx.shadowColor = 'transparent';
            ctx.textBaseline = 'middle';
            ctx.fillText(shape.text, boxX + paddingX, boxY + (boxHeight / 2));
        }

        ctx.restore();
    }

    /* ══════════════ FERMETURE & SAUVEGARDE ══════════════ */

    function closeModal() {
        hideTextPopover();
        const modal = document.getElementById('photoAnnotatorModal');
        if (modal) modal.style.display = 'none';
        originalImage = null;
        originalFile = null;
        historyStack = [];
        selectedShapeIndex = null;
        updateDeleteBtnVisibility();
        onSaveCallback = null;
    }

    function saveAnnotation() {
        if (!canvas) return;
        hideTextPopover();

        selectedShapeIndex = null;
        redrawCanvas();

        canvas.toBlob(blob => {
            if (!blob) return;
            const filename = originalFile ? originalFile.name : `annotated_${Date.now()}.jpg`;
            const annotatedFile = new File([blob], filename, { type: 'image/jpeg', lastModified: Date.now() });
            const dataUrl = canvas.toDataURL('image/jpeg', 0.92);

            if (typeof onSaveCallback === 'function') {
                onSaveCallback(annotatedFile, dataUrl);
            }
            closeModal();
        }, 'image/jpeg', 0.92);
    }

    function openPhotoAnnotator(imageSource, callback) {
        createModalDom();
        onSaveCallback = callback;
        historyStack = [];
        selectedShapeIndex = null;
        hideTextPopover();
        updateDeleteBtnVisibility();

        const img = new Image();
        img.crossOrigin = 'anonymous';

        function onLoad() {
            originalImage = img;
            canvas.width = img.naturalWidth || img.width;
            canvas.height = img.naturalHeight || img.height;
            redrawCanvas();

            const modal = document.getElementById('photoAnnotatorModal');
            modal.style.display = 'flex';

            const wrap = document.getElementById('canvasWrap');
            if (wrap) wrap.scrollTop = 0;
        }

        if (imageSource instanceof File || imageSource instanceof Blob) {
            originalFile = imageSource;
            const reader = new FileReader();
            reader.onload = e => {
                img.onload = onLoad;
                img.src = e.target.result;
            };
            reader.readAsDataURL(imageSource);
        } else if (typeof imageSource === 'string') {
            originalFile = null;
            img.onload = onLoad;
            img.src = imageSource;
        }
    }

    function replaceFileInInput(input, index, newFile) {
        if (!input || !window.DataTransfer) return;
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
    }

    // Export global
    window.openPhotoAnnotator = openPhotoAnnotator;
    window.replaceFileInInput = replaceFileInInput;

})();
