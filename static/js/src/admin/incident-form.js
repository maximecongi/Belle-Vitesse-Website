/**
 * incident-form.js — Contrôleur dynamique du formulaire de signalement et d'édition d'incident.
 * Gère :
 * - Le sélecteur multi-équipements personnalisé (véhicules, têtes caméra, accessoires libres)
 * - La synchronisation avec le projet sélectionné et ses contrôles (check-in / check-out)
 * - La prévisualisation des photos et l'intégration de l'annotateur
 * - La prévisualisation des pièces jointes / documents
 * - La mise à jour visuelle des pilules de statut, gravité et impact
 */

(function () {
    let projectsData = [];
    let isEdit = false;
    let isSealed = false;
    let initialVehicleId = '';
    let initialEquipmentName = '';
    let initialAttachedInspection = '';
    let isInitialLoad = true;
    let customEquipmentItems = [];

    function escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    }
    window.escapeHtml = escapeHtml;

    function renderCustomEquipmentList() {
        const container = document.getElementById('customEquipmentList');
        const countBadge = document.getElementById('customCountBadge');
        if (!container) return;

        if (countBadge) countBadge.textContent = String(customEquipmentItems.length);

        if (customEquipmentItems.length === 0) {
            container.innerHTML = '<span class="u-text-xs u-text-muted">Aucun accessoire spécifique ajouté</span>';
            return;
        }

        let html = '';
        customEquipmentItems.forEach(item => {
            html += `
                <span class="admin-multiselect-custom-pill">
                    <span class="admin-multiselect-item-icon"><i data-lucide="box"></i></span>
                    <span class="admin-multiselect-custom-text" title="${escapeHtml(item)}">${escapeHtml(item)}</span>
                    <button type="button" class="admin-multiselect-custom-remove" data-action="remove-custom-item" data-value="${escapeHtml(item)}" title="Supprimer cet accessoire" aria-label="Supprimer">&times;</button>
                </span>
            `;
        });
        container.innerHTML = html;
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
    }

    function addCustomEquipment(val) {
        if (!val) return;
        const items = val.split(',').map(s => s.trim()).filter(Boolean);
        let changed = false;
        items.forEach(newItem => {
            if (!customEquipmentItems.some(i => i.toLowerCase() === newItem.toLowerCase())) {
                customEquipmentItems.push(newItem);
                changed = true;
            }
        });
        const input = document.getElementById('customEquipmentInput');
        if (input) input.value = '';
        if (changed) {
            renderCustomEquipmentList();
            syncSelectedEquipment();
        }
    }

    function removeCustomEquipment(val) {
        if (!val) return;
        customEquipmentItems = customEquipmentItems.filter(i => i.toLowerCase() !== val.toLowerCase());
        renderCustomEquipmentList();
        syncSelectedEquipment();
    }

    function updateProjectEquipment(projectId) {
        if (isSealed) return;
        const multiselect = document.getElementById('equipmentMultiselect');
        const placeholder = document.getElementById('equipmentMultiselectPlaceholder');
        const vehicleItemsList = document.getElementById('vehicleItemsList');
        const headItemsList = document.getElementById('headItemsList');
        const vehicleCountBadge = document.getElementById('vehicleCountBadge');
        const headCountBadge = document.getElementById('headCountBadge');
        const inspectionSelect = document.getElementById('attached_inspection');

        if (!multiselect || !vehicleItemsList || !headItemsList) return;

        if (!projectId) {
            multiselect.classList.add('is-disabled');
            multiselect.classList.remove('is-open');
            if (placeholder) placeholder.textContent = "— Sélectionnez d'abord un projet —";
            vehicleItemsList.innerHTML = '<div class="admin-multiselect-empty">Sélectionnez d\'abord un projet</div>';
            headItemsList.innerHTML = '<div class="admin-multiselect-empty">Sélectionnez d\'abord un projet</div>';
            if (vehicleCountBadge) vehicleCountBadge.textContent = '0';
            if (headCountBadge) headCountBadge.textContent = '0';
            customEquipmentItems = [];
            renderCustomEquipmentList();
            syncSelectedEquipment();

            if (inspectionSelect) {
                inspectionSelect.innerHTML = '<option value="">En cours d\'opération (sur le plateau)</option>';
                inspectionSelect.disabled = true;
            }
            return;
        }

        const project = projectsData.find(p => String(p.id) === String(projectId));
        multiselect.classList.remove('is-disabled');

        if (!project) {
            vehicleItemsList.innerHTML = '<div class="admin-multiselect-empty">Aucun véhicule disponible</div>';
            headItemsList.innerHTML = '<div class="admin-multiselect-empty">Aucune tête disponible</div>';
            if (vehicleCountBadge) vehicleCountBadge.textContent = '0';
            if (headCountBadge) headCountBadge.textContent = '0';
            syncSelectedEquipment();
            return;
        }

        // 1. Peupler les véhicules
        const vehicles = project.vehicles || [];
        if (vehicleCountBadge) vehicleCountBadge.textContent = String(vehicles.length);
        if (vehicles.length === 0) {
            vehicleItemsList.innerHTML = '<div class="admin-multiselect-empty">Aucun véhicule rattaché à ce projet</div>';
        } else {
            let vHtml = '';
            vehicles.forEach(v => {
                let isChecked = false;
                if (isInitialLoad) {
                    if (String(v.id) === String(initialVehicleId)) {
                        isChecked = true;
                    } else if (initialEquipmentName && initialEquipmentName.toLowerCase().includes(v.name.toLowerCase())) {
                        isChecked = true;
                    }
                }
                const checkedAttr = isChecked ? 'checked' : '';
                const selectedClass = isChecked ? 'is-selected' : '';
                vHtml += `
                    <label class="admin-multiselect-item ${selectedClass}" data-type="vehicle" data-id="${escapeHtml(v.id)}" data-name="${escapeHtml(v.name)}">
                        <input type="checkbox" class="admin-multiselect-checkbox" value="${escapeHtml(v.id)}" data-type="vehicle" data-name="${escapeHtml(v.name)}" ${checkedAttr}>
                        <span class="admin-multiselect-item-text">${escapeHtml(v.name)}</span>
                        <span class="admin-multiselect-item-tag">Véhicule</span>
                    </label>
                `;
            });
            vehicleItemsList.innerHTML = vHtml;
        }

        // 2. Peupler les têtes
        const heads = project.heads || [];
        if (headCountBadge) headCountBadge.textContent = String(heads.length);
        if (heads.length === 0) {
            headItemsList.innerHTML = '<div class="admin-multiselect-empty">Aucune tête rattachée à ce projet</div>';
        } else {
            let hHtml = '';
            heads.forEach(h => {
                let isChecked = false;
                if (isInitialLoad && initialEquipmentName) {
                    const parts = initialEquipmentName.split(',').map(s => s.trim().toLowerCase());
                    if (parts.includes(h.name.toLowerCase()) || initialEquipmentName.toLowerCase().includes(h.name.toLowerCase())) {
                        isChecked = true;
                    }
                }
                const checkedAttr = isChecked ? 'checked' : '';
                const selectedClass = isChecked ? 'is-selected' : '';
                hHtml += `
                    <label class="admin-multiselect-item ${selectedClass}" data-type="head" data-name="${escapeHtml(h.name)}">
                        <input type="checkbox" class="admin-multiselect-checkbox" value="${escapeHtml(h.name)}" data-type="head" data-name="${escapeHtml(h.name)}" ${checkedAttr}>
                        <span class="admin-multiselect-item-text">${escapeHtml(h.name)}</span>
                        <span class="admin-multiselect-item-tag">Tête</span>
                    </label>
                `;
            });
            headItemsList.innerHTML = hHtml;
        }

        // 3. Traiter le cas des accessoires libres lors du premier chargement
        if (isInitialLoad && initialEquipmentName) {
            const parts = initialEquipmentName.split(',').map(s => s.trim()).filter(Boolean);
            parts.forEach(p => {
                const pLower = p.toLowerCase();
                const matchedHead = heads.some(h => h.name.toLowerCase() === pLower);
                const matchedVeh = vehicles.some(v => v.name.toLowerCase() === pLower);
                if (!matchedHead && !matchedVeh) {
                    if (!customEquipmentItems.some(i => i.toLowerCase() === pLower)) {
                        customEquipmentItems.push(p);
                    }
                }
            });
            renderCustomEquipmentList();
        }

        // 4. Mettre à jour l'affichage des tags & synchroniser les inputs cachés
        syncSelectedEquipment();

        // 5. Peupler les contrôles rattachés (Check-out / Check-in) du projet
        if (inspectionSelect) {
            inspectionSelect.disabled = false;
            let insOptions = '<option value="">En cours d\'opération (sur le plateau)</option>';
            if (project.checkouts && project.checkouts.length > 0) {
                insOptions += '<optgroup label="📋 Contrôles au départ (Check-out)">';
                project.checkouts.forEach(co => {
                    const val = `checkout:${co.id}`;
                    const isSelected = (val === initialAttachedInspection) ? 'selected' : '';
                    insOptions += `<option value="${val}" ${isSelected}>Check-out ${co.inspection_number} (${co.date || 'Date N/A'})</option>`;
                });
                insOptions += '</optgroup>';
            }
            if (project.checkins && project.checkins.length > 0) {
                insOptions += '<optgroup label="📋 Contrôles au retour (Check-in)">';
                project.checkins.forEach(ci => {
                    const val = `checkin:${ci.id}`;
                    const isSelected = (val === initialAttachedInspection) ? 'selected' : '';
                    insOptions += `<option value="${val}" ${isSelected}>Check-in ${ci.inspection_number} (${ci.date || 'Date N/A'})</option>`;
                });
                insOptions += '</optgroup>';
            }
            inspectionSelect.innerHTML = insOptions;
        }

        isInitialLoad = false;
    }
    window.updateProjectEquipment = updateProjectEquipment;

    function syncSelectedEquipment() {
        const selectionContainer = document.getElementById('equipmentMultiselectSelection');
        const vehicleHidden = document.getElementById('vehicle_id');
        const equipmentHidden = document.getElementById('equipment_name');

        if (!selectionContainer || !vehicleHidden || !equipmentHidden) return;

        const checkedVehicles = Array.from(document.querySelectorAll('#vehicleItemsList input[type="checkbox"]:checked'));
        const checkedHeads = Array.from(document.querySelectorAll('#headItemsList input[type="checkbox"]:checked'));

        const totalSelected = checkedVehicles.length + checkedHeads.length + customEquipmentItems.length;

        if (totalSelected === 0) {
            selectionContainer.innerHTML = '<span class="admin-multiselect-placeholder" id="equipmentMultiselectPlaceholder">— Sélectionner le ou les équipements concernés —</span>';
            vehicleHidden.value = '';
            equipmentHidden.value = '';
            return;
        }

        let tagsHtml = '';

        checkedVehicles.forEach(cb => {
            const vId = cb.value;
            const vName = cb.dataset.name || cb.value;
            tagsHtml += `
                <span class="admin-multiselect-tag admin-multiselect-tag--vehicle">
                    <span class="admin-multiselect-tag-icon"><i data-lucide="motorbike"></i></span>
                    <span class="admin-multiselect-tag-label" title="${escapeHtml(vName)}">${escapeHtml(vName)}</span>
                    <button type="button" class="admin-multiselect-tag-remove" data-action="remove-vehicle" data-id="${escapeHtml(vId)}" title="Désélectionner" aria-label="Désélectionner">&times;</button>
                </span>
            `;
        });

        checkedHeads.forEach(cb => {
            const hName = cb.value;
            tagsHtml += `
                <span class="admin-multiselect-tag admin-multiselect-tag--head">
                    <span class="admin-multiselect-tag-icon"><i data-lucide="bot"></i></span>
                    <span class="admin-multiselect-tag-label" title="${escapeHtml(hName)}">${escapeHtml(hName)}</span>
                    <button type="button" class="admin-multiselect-tag-remove" data-action="remove-head" data-name="${escapeHtml(hName)}" title="Désélectionner" aria-label="Désélectionner">&times;</button>
                </span>
            `;
        });

        customEquipmentItems.forEach(item => {
            tagsHtml += `
                <span class="admin-multiselect-tag admin-multiselect-tag--custom">
                    <span class="admin-multiselect-tag-icon"><i data-lucide="box"></i></span>
                    <span class="admin-multiselect-tag-label" title="${escapeHtml(item)}">${escapeHtml(item)}</span>
                    <button type="button" class="admin-multiselect-tag-remove" data-action="remove-custom-item" data-value="${escapeHtml(item)}" title="Désélectionner" aria-label="Désélectionner">&times;</button>
                </span>
            `;
        });

        selectionContainer.innerHTML = tagsHtml;
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }

        // Mise à jour de vehicle_id avec le premier véhicule sélectionné
        if (checkedVehicles.length > 0) {
            vehicleHidden.value = checkedVehicles[0].value;
        } else {
            vehicleHidden.value = '';
        }

        // Construction de la chaîne d'équipements pour equipment_name
        const equipmentList = [];
        if (checkedVehicles.length > 1) {
            checkedVehicles.slice(1).forEach(cb => {
                equipmentList.push(cb.dataset.name || cb.value);
            });
        }
        checkedHeads.forEach(cb => {
            equipmentList.push(cb.dataset.name || cb.value);
        });
        customEquipmentItems.forEach(item => {
            equipmentList.push(item);
        });

        equipmentHidden.value = equipmentList.join(', ');
    }
    window.syncSelectedEquipment = syncSelectedEquipment;

    function previewFiles(input, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';
        if (input.files) {
            Array.from(input.files).forEach((file, index) => {
                if (file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = function (e) {
                        const wrapper = document.createElement('div');
                        wrapper.className = 'photo-preview-item';

                        const img = document.createElement('img');
                        img.src = e.target.result;
                        img.className = 'photo-preview-img';
                        wrapper.appendChild(img);

                        if (typeof window.openPhotoAnnotator === 'function') {
                            const btn = document.createElement('button');
                            btn.type = 'button';
                            btn.className = 'annotator-edit-badge';
                            btn.title = "Annoter cette photo (cercle, flèche)";
                            btn.innerHTML = '✏️ Annoter';
                            btn.onclick = function (ev) {
                                ev.preventDefault();
                                ev.stopPropagation();
                                window.openPhotoAnnotator(file, function (annotatedFile, dataUrl) {
                                    img.src = dataUrl;
                                    if (typeof window.replaceFileInInput === 'function') {
                                        window.replaceFileInInput(input, index, annotatedFile);
                                    }
                                });
                            };
                            wrapper.appendChild(btn);
                        }

                        container.appendChild(wrapper);
                    };
                    reader.readAsDataURL(file);
                }
            });
        }
    }
    window.previewFiles = previewFiles;

    function previewDocs(input, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';
        if (input.files) {
            Array.from(input.files).forEach(file => {
                const tag = document.createElement('span');
                tag.className = 'admin-badge doc-preview-tag u-text-xs';
                tag.innerText = '📄 ' + file.name;
                container.appendChild(tag);
            });
        }
    }
    window.previewDocs = previewDocs;

    // Mise à jour visuelle dynamique du badge de statut
    const STATUS_MAP = {
        'signale': 'neutral',
        'en_expertise': 'warning',
        'en_reparation': 'in_progress',
        'assurance': 'assurance',
        'resolu': 'ok',
        'cloture': 'cloture'
    };
    const STATUS_ICONS = {
        'signale': 'megaphone',
        'en_expertise': 'search',
        'en_reparation': 'wrench',
        'assurance': 'clipboard-list',
        'resolu': 'check-circle',
        'cloture': 'lock'
    };

    function updateIncidentStatusPill(selectElem) {
        const pill = document.getElementById('incidentStatusPill');
        const label = document.getElementById('incidentStatusLabel');
        if (!selectElem) return;
        const selectedVal = selectElem.value;
        const selectedText = selectElem.options[selectElem.selectedIndex]?.text || '';
        const dataVal = STATUS_MAP[selectedVal] || 'neutral';
        const iconName = STATUS_ICONS[selectedVal] || 'megaphone';

        if (pill) {
            pill.setAttribute('data-val', dataVal);
        }
        if (label) {
            label.innerHTML = `<i data-lucide="${iconName}"></i> ${selectedText}`;
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }
    }
    window.updateIncidentStatusPill = updateIncidentStatusPill;

    // Mise à jour visuelle dynamique du badge de gravité
    const SEVERITY_MAP = {
        'mineur': 'neutral',
        'modere': 'warning',
        'critique': 'critique'
    };
    const SEVERITY_ICONS = {
        'mineur': 'info',
        'modere': 'alert-triangle',
        'critique': 'alert-octagon'
    };

    function updateIncidentSeverityPill(selectElem) {
        const pill = document.getElementById('incidentSeverityPill');
        const label = document.getElementById('incidentSeverityLabel');
        if (!pill || !selectElem) return;

        const selectedVal = selectElem.value;
        const selectedText = selectElem.options[selectElem.selectedIndex]?.text || '';
        const dataVal = SEVERITY_MAP[selectedVal] || 'neutral';
        const iconName = SEVERITY_ICONS[selectedVal] || 'alert-triangle';

        pill.setAttribute('data-val', dataVal);
        if (label) {
            label.innerHTML = `<i data-lucide="${iconName}"></i> ${selectedText}`;
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }
    }
    window.updateIncidentSeverityPill = updateIncidentSeverityPill;

    // Mise à jour visuelle dynamique du badge d'impact sur le tournage
    const IMPACT_MAP = {
        'aucun': 'ok',
        'retard': 'warning',
        'interruption': 'in_progress',
        'annulation': 'critique'
    };
    const IMPACT_ICONS = {
        'aucun': 'check-circle',
        'retard': 'clock',
        'interruption': 'pause-circle',
        'annulation': 'ban'
    };

    function updateIncidentImpactPill(selectElem) {
        const pill = document.getElementById('incidentImpactPill');
        const label = document.getElementById('incidentImpactLabel');
        if (!pill || !selectElem) return;

        const selectedVal = selectElem.value;
        const selectedText = selectElem.options[selectElem.selectedIndex]?.text || '';
        const dataVal = IMPACT_MAP[selectedVal] || 'neutral';
        const iconName = IMPACT_ICONS[selectedVal] || 'check-circle';

        pill.setAttribute('data-val', dataVal);
        if (label) {
            label.innerHTML = `<i data-lucide="${iconName}"></i> ${selectedText}`;
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }
    }
    window.updateIncidentImpactPill = updateIncidentImpactPill;

    function initIncidentForm() {
        const dataEl = document.getElementById('incidentFormData');
        if (!dataEl) return;

        try {
            const config = JSON.parse(dataEl.textContent);
            projectsData = config.projects || [];
            isEdit = !!config.isEdit;
            isSealed = !!config.isSealed;
            initialVehicleId = config.initialVehicleId || '';
            initialEquipmentName = config.initialEquipmentName || '';
            initialAttachedInspection = config.initialAttachedInspection || '';
        } catch (e) {
            console.error("Erreur lors de la lecture des données d'incident :", e);
            return;
        }

        const multiselect = document.getElementById('equipmentMultiselect');
        const trigger = document.getElementById('equipmentMultiselectTrigger');
        const panel = document.getElementById('equipmentMultiselectPanel');
        const selectionContainer = document.getElementById('equipmentMultiselectSelection');
        const customList = document.getElementById('customEquipmentList');
        const addCustomBtn = document.getElementById('addCustomEquipmentBtn');
        const customInput = document.getElementById('customEquipmentInput');

        if (trigger && multiselect) {
            trigger.addEventListener('click', (e) => {
                if (multiselect.classList.contains('is-disabled')) return;
                if (e.target.closest('.admin-multiselect-tag-remove')) return;

                const isOpen = multiselect.classList.contains('is-open');
                if (isOpen) {
                    multiselect.classList.remove('is-open');
                    trigger.setAttribute('aria-expanded', 'false');
                } else {
                    multiselect.classList.add('is-open');
                    trigger.setAttribute('aria-expanded', 'true');
                }
            });

            // Fermer si clic à l'extérieur
            document.addEventListener('click', (e) => {
                if (!multiselect.contains(e.target)) {
                    multiselect.classList.remove('is-open');
                    trigger.setAttribute('aria-expanded', 'false');
                }
            });

            // Fermer sur Échap
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && multiselect.classList.contains('is-open')) {
                    multiselect.classList.remove('is-open');
                    trigger.setAttribute('aria-expanded', 'false');
                }
            });
        }

        // Clic sur bouton de suppression d'un tag
        if (selectionContainer) {
            selectionContainer.addEventListener('click', (e) => {
                const removeBtn = e.target.closest('.admin-multiselect-tag-remove');
                if (!removeBtn) return;
                e.preventDefault();
                e.stopPropagation();

                const action = removeBtn.dataset.action;
                if (action === 'remove-vehicle') {
                    const id = removeBtn.dataset.id;
                    const cb = document.querySelector(`#vehicleItemsList input[value="${id}"]`);
                    if (cb) {
                        cb.checked = false;
                        const label = cb.closest('.admin-multiselect-item');
                        if (label) label.classList.remove('is-selected');
                    }
                    syncSelectedEquipment();
                } else if (action === 'remove-head') {
                    const name = removeBtn.dataset.name;
                    const cb = document.querySelector(`#headItemsList input[value="${name}"]`);
                    if (cb) {
                        cb.checked = false;
                        const label = cb.closest('.admin-multiselect-item');
                        if (label) label.classList.remove('is-selected');
                    }
                    syncSelectedEquipment();
                } else if (action === 'remove-custom-item') {
                    removeCustomEquipment(removeBtn.dataset.value);
                }
            });
        }

        // Suppression d'un accessoire depuis la liste dans le panneau déroulant
        if (customList) {
            customList.addEventListener('click', (e) => {
                const removeBtn = e.target.closest('.admin-multiselect-custom-remove');
                if (!removeBtn) return;
                e.preventDefault();
                e.stopPropagation();
                removeCustomEquipment(removeBtn.dataset.value);
            });
        }

        // Ajout d'accessoires personnalisés (clic bouton ou touche Entrée)
        if (addCustomBtn && customInput) {
            addCustomBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                addCustomEquipment(customInput.value);
            });
            customInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    e.stopPropagation();
                    addCustomEquipment(customInput.value);
                }
            });
        }

        // Changement sur les checkboxes de véhicules et têtes
        if (panel) {
            panel.addEventListener('change', (e) => {
                const cb = e.target;
                if (cb.classList.contains('admin-multiselect-checkbox')) {
                    const label = cb.closest('.admin-multiselect-item');
                    if (label) {
                        if (cb.checked) {
                            label.classList.add('is-selected');
                        } else {
                            label.classList.remove('is-selected');
                        }
                    }
                    syncSelectedEquipment();
                }
            });
        }

        // Initialisation si un projet est déjà sélectionné
        if (!isSealed) {
            const projectSelect = document.getElementById('project_id');
            if (projectSelect && projectSelect.value) {
                updateProjectEquipment(projectSelect.value);
            } else {
                updateProjectEquipment('');
            }
        }
    }
    window.initIncidentForm = initIncidentForm;

    // Déclenchement automatique au chargement
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initIncidentForm);
    } else {
        initIncidentForm();
    }
})();
