/**
 * Gestion dynamique de la liste structurée des lieux de tournage (Formulaire Projet)
 * - Ajout d'un nouveau lieu (Nom + Adresse)
 * - Suppression d'un lieu
 * - Réordonnancement par glisser-déposer pur (HTML5 Drag & Drop) via poignée
 * - Sérialisation et synchronisation automatique vers le champ hidden #shooting_locations_input
 */
(function () {
    'use strict';

    function initProjectLocations() {
        const container = document.getElementById('projectLocationsWrapper');
        const listEl = document.getElementById('projectLocationsList');
        const hiddenInput = document.getElementById('shooting_locations_input');
        const addBtn = document.getElementById('addLocationBtn');
        const emptyState = document.getElementById('projectLocationsEmpty');

        if (!container || !listEl || !hiddenInput || !addBtn) {
            return;
        }

        // Éviter les doubles initialisations
        if (container.dataset.initialized === 'true') {
            return;
        }
        container.dataset.initialized = 'true';

        let draggedCard = null;

        /**
         * Met à jour le champ JSON caché à partir des valeurs du DOM
         */
        function syncToHiddenInput() {
            const cards = listEl.querySelectorAll('.project-location-card');
            const locations = [];

            cards.forEach((card) => {
                const nameInput = card.querySelector('.project-location-name-input');
                const addrInput = card.querySelector('.project-location-addr-input');
                const name = nameInput ? nameInput.value.trim() : '';
                const address = addrInput ? addrInput.value.trim() : '';

                if (name) {
                    locations.push({ name, address });
                }
            });

            hiddenInput.value = JSON.stringify(locations);

            if (emptyState) {
                if (cards.length === 0) {
                    emptyState.classList.remove('u-d-none');
                } else {
                    emptyState.classList.add('u-d-none');
                }
            }
        }

        /**
         * Crée un élément DOM pour un lieu donné
         */
        function createLocationCard(name = '', address = '') {
            const card = document.createElement('div');
            card.className = 'project-location-card';
            card.setAttribute('draggable', 'false');

            card.innerHTML = `
                <div class="project-location-handle" title="Glisser pour réordonner" aria-label="Déplacer ce lieu">
                    <i data-lucide="grip-vertical" class="project-location-handle-icon"></i>
                </div>
                <div class="project-location-inputs">
                    <div class="form-group u-mb-0">
                        <label class="form-label u-text-xs u-mb-1">Nom du lieu <span class="u-text-danger">*</span></label>
                        <input type="text" class="form-input project-location-name-input" placeholder="Ex: Circuit Paul Ricard, Studios de Bry..." value="${escapeHtml(name)}" required>
                    </div>
                    <div class="form-group u-mb-0">
                        <label class="form-label u-text-xs u-mb-1">Adresse (facultative)</label>
                        <input type="text" class="form-input project-location-addr-input" placeholder="Ex: 2760 Rte des Hauts du Camp, 83330 Le Castellet" value="${escapeHtml(address)}">
                    </div>
                </div>
                <div class="project-location-actions">
                    <button type="button" class="project-location-delete-btn" title="Supprimer ce lieu" aria-label="Supprimer ce lieu">
                        <i data-lucide="trash-2"></i>
                    </button>
                </div>
            `;

            // Poignée de Drag & Drop
            const handle = card.querySelector('.project-location-handle');
            handle.addEventListener('mousedown', () => {
                card.setAttribute('draggable', 'true');
            });
            handle.addEventListener('touchstart', () => {
                card.setAttribute('draggable', 'true');
            }, { passive: true });

            card.addEventListener('dragstart', (e) => {
                draggedCard = card;
                card.classList.add('is-dragging');
                if (e.dataTransfer) {
                    e.dataTransfer.effectAllowed = 'move';
                    e.dataTransfer.setData('text/plain', '');
                }
            });

            card.addEventListener('dragend', () => {
                card.removeAttribute('draggable');
                card.classList.remove('is-dragging');
                draggedCard = null;
                syncToHiddenInput();
            });

            card.addEventListener('dragover', (e) => {
                e.preventDefault();
                if (e.dataTransfer) {
                    e.dataTransfer.dropEffect = 'move';
                }
                if (!draggedCard || draggedCard === card) {
                    return;
                }

                const rect = card.getBoundingClientRect();
                const next = (e.clientY - rect.top) / (rect.bottom - rect.top) > 0.5;
                listEl.insertBefore(draggedCard, next ? card.nextSibling : card);
            });

            // Bouton de suppression
            const deleteBtn = card.querySelector('.project-location-delete-btn');
            deleteBtn.addEventListener('click', () => {
                card.remove();
                syncToHiddenInput();
            });

            // Événements de saisie
            const nameInput = card.querySelector('.project-location-name-input');
            const addrInput = card.querySelector('.project-location-addr-input');
            nameInput.addEventListener('input', syncToHiddenInput);
            addrInput.addEventListener('input', syncToHiddenInput);

            // Empêcher la touche Entrée de soumettre le formulaire
            const preventEnterSubmit = (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                }
            };
            nameInput.addEventListener('keydown', preventEnterSubmit);
            addrInput.addEventListener('keydown', preventEnterSubmit);

            // Icônes Lucide
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons({
                    root: card,
                    nameAttr: 'data-lucide'
                });
            }

            return card;
        }

        function escapeHtml(str) {
            if (!str) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
        }

        // Initialisation avec les données existantes
        let initialLocations = [];
        try {
            const rawVal = hiddenInput.value;
            if (rawVal) {
                initialLocations = JSON.parse(rawVal);
            }
        } catch (e) {
            initialLocations = [];
        }

        listEl.innerHTML = '';
        if (Array.isArray(initialLocations) && initialLocations.length > 0) {
            initialLocations.forEach((loc) => {
                if (loc && (loc.name || loc.address)) {
                    listEl.appendChild(createLocationCard(loc.name || '', loc.address || ''));
                }
            });
        }

        syncToHiddenInput();

        // Bouton d'ajout
        addBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const newCard = createLocationCard();
            listEl.appendChild(newCard);
            syncToHiddenInput();

            const firstInput = newCard.querySelector('.project-location-name-input');
            if (firstInput) {
                firstInput.focus();
            }
        });
    }

    // Support chargement direct et transitions Swup
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initProjectLocations);
    } else {
        initProjectLocations();
    }
    document.addEventListener('swup:contentReplaced', initProjectLocations);
})();

