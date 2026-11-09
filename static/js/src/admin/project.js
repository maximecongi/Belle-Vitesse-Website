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
                const targetSrc = trigger.dataset.protocolUrl || (iframe ? iframe.dataset.src : '');
                if (iframe && targetSrc) {
                    if (iframe.getAttribute('src') !== targetSrc) {
                        iframe.setAttribute('src', targetSrc);
                    }
                }
                vehiclesModal.classList.add('is-active');
            });
        });

        if (closeVModalBtn && !closeVModalBtn._modalBound) {
            closeVModalBtn._modalBound = true;
            closeVModalBtn.addEventListener('click', () => {
                vehiclesModal.classList.remove('is-active');
            });
        }

        if (!vehiclesModal._backdropBound) {
            vehiclesModal._backdropBound = true;
            window.addEventListener('click', (event) => {
                if (event.target === vehiclesModal) {
                    vehiclesModal.classList.remove('is-active');
                }
            });
        }
    }
}
window.initVehiclesModal = initVehiclesModal;

function initProjectNotionSlashEditor() {
    // Éditeur de création, initialisé au chargement
    const wrapper = document.getElementById('notionEditorWrapper-new');
    if (wrapper) initNotionEditor(wrapper);
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
            if (labelEl) labelEl.textContent = 'Plier';
            if (iconEl) iconEl.textContent = '▴';
            toggleBtn.setAttribute('aria-expanded', 'true');
        } else {
            wrapper.classList.remove('is-expanded');
            wrapper.classList.add('is-collapsed');
            if (labelEl) labelEl.textContent = 'Déplier';
            if (iconEl) iconEl.textContent = '▾';
            toggleBtn.setAttribute('aria-expanded', 'false');
        }
    });
}

function initProjectReportsEdit() {
    if (document._projectReportsEditBound) return;
    document._projectReportsEditBound = true;

    function openEdit(reportId) {
        const viewEl = document.getElementById(`reportView-${reportId}`);
        const editEl = document.getElementById(`reportEdit-${reportId}`);
        if (!viewEl || !editEl) return;
        viewEl.classList.add('is-hidden');
        editEl.classList.remove('is-hidden');
        // Initialisation paresseuse : un seul éditeur riche monté par rapport réellement édité
        const api = initNotionEditor(editEl.querySelector('.notion-wysiwyg-wrapper'));
        if (api) api.focusEnd();
        // Brouillons (project-reports.js) : restauration éventuelle d'une modification non enregistrée
        editEl.dispatchEvent(new CustomEvent('report-edit-open', { bubbles: true }));
    }

    function closeEdit(reportId) {
        const viewEl = document.getElementById(`reportView-${reportId}`);
        const editEl = document.getElementById(`reportEdit-${reportId}`);
        if (!viewEl || !editEl) return;
        // Annuler = revenir au contenu publié (titre, catégorie, jour, photos, corps)
        editEl.reset();
        const wrapper = editEl.querySelector('.notion-wysiwyg-wrapper');
        if (wrapper && wrapper._notionEditor) wrapper._notionEditor.reset();
        editEl.classList.add('is-hidden');
        viewEl.classList.remove('is-hidden');
        editEl.dispatchEvent(new CustomEvent('report-edit-cancel', { bubbles: true }));
    }

    document.addEventListener('click', (e) => {
        const editBtn = e.target.closest('[data-action="edit-report"]');
        if (editBtn) {
            openEdit(editBtn.getAttribute('data-report-id'));
            return;
        }

        const cancelBtn = e.target.closest('[data-action="cancel-edit"]');
        if (cancelBtn) {
            closeEdit(cancelBtn.getAttribute('data-report-id'));
        }
    });

    // Raccourci Escape pour annuler l'édition en cours (sauf si Escape ferme un menu de l'éditeur)
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape' || e.defaultPrevented) return;
        if (document.querySelector('.notion-slash-menu.is-open, .notion-context-menu.is-open')) return;
        const activeEditForm = document.querySelector('.project-report-edit-form:not(.is-hidden)');
        if (activeEditForm) {
            closeEdit(activeEditForm.id.replace('reportEdit-', ''));
        }
    });
}

function escapeProjectNotesHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function initProjectNotesEdit() {
    if (document._projectNotesEditBound) return;
    document._projectNotesEditBound = true;

    // Clic : Activer ou Annuler l'édition
    document.addEventListener('click', (e) => {
        const editBtn = e.target.closest('[data-action="edit-notes"]');
        if (editBtn) {
            const displayEl = document.getElementById('projectNotesDisplay');
            const formEl = document.getElementById('projectNotesForm');
            const textarea = document.getElementById('projectNotesInput');
            if (displayEl && formEl) {
                displayEl.classList.add('is-hidden');
                formEl.classList.remove('is-hidden');
                editBtn.classList.add('is-hidden');
                if (textarea) {
                    textarea.focus();
                    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
                }
            }
            return;
        }

        const cancelBtn = e.target.closest('[data-action="cancel-notes"]');
        if (cancelBtn) {
            const displayEl = document.getElementById('projectNotesDisplay');
            const formEl = document.getElementById('projectNotesForm');
            const editBtn = document.getElementById('projectNotesEditBtn');
            if (displayEl && formEl) {
                formEl.classList.add('is-hidden');
                displayEl.classList.remove('is-hidden');
                if (editBtn) editBtn.classList.remove('is-hidden');
            }
            return;
        }
    });

    // Raccourci Échap pour annuler l'édition
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const formEl = document.getElementById('projectNotesForm');
            const displayEl = document.getElementById('projectNotesDisplay');
            const editBtn = document.getElementById('projectNotesEditBtn');
            if (formEl && !formEl.classList.contains('is-hidden')) {
                formEl.classList.add('is-hidden');
                if (displayEl) displayEl.classList.remove('is-hidden');
                if (editBtn) editBtn.classList.remove('is-hidden');
            }
        }
    });

    // Raccourci Ctrl+Entrée ou Cmd+Entrée pour soumettre le formulaire
    document.addEventListener('keydown', (e) => {
        const isEnter = e.key === 'Enter' || e.code === 'Enter' || e.keyCode === 13;
        const isModifier = e.ctrlKey || e.metaKey;
        if (isModifier && isEnter) {
            const formEl = document.getElementById('projectNotesForm');
            const textarea = document.getElementById('projectNotesInput');
            if (formEl && !formEl.classList.contains('is-hidden') && document.activeElement === textarea) {
                e.preventDefault();
                if (typeof formEl.requestSubmit === 'function') {
                    formEl.requestSubmit();
                } else {
                    formEl.submit();
                }
            }
        }
    });

    // Soumission AJAX avec fallback automatique
    document.addEventListener('submit', async (e) => {
        const formEl = e.target.closest('#projectNotesForm');
        if (!formEl) return;

        e.preventDefault();
        const submitBtn = document.getElementById('projectNotesSubmitBtn');
        const displayEl = document.getElementById('projectNotesDisplay');
        const editBtn = document.getElementById('projectNotesEditBtn');
        const editBtnLabel = document.getElementById('projectNotesEditBtnLabel');
        const originalBtnHtml = submitBtn ? submitBtn.innerHTML : '';

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Enregistrement...';
        }

        try {
            const formData = new FormData(formEl);
            const response = await fetch(formEl.action, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            });

            if (response.ok) {
                const data = await response.json();
                const newNotes = (data.notes || '').trim();

                if (newNotes) {
                    displayEl.innerHTML = `<div class="project-notes-content" id="projectNotesText">${escapeProjectNotesHtml(newNotes)}</div>`;
                    if (editBtnLabel) editBtnLabel.textContent = 'Modifier';
                } else {
                    displayEl.innerHTML = `
                        <div class="empty-state empty-state-sm">
                            <div class="empty-state-icon">
                                <i data-lucide="clipboard-pen"></i>
                            </div>
                            <div class="empty-state-title">Aucune note enregistrée</div>
                        </div>
                    `;
                    if (editBtnLabel) editBtnLabel.textContent = 'Ajouter une note';
                    if (window.lucide && typeof window.lucide.createIcons === 'function') {
                        window.lucide.createIcons();
                    }
                }

                formEl.classList.add('is-hidden');
                displayEl.classList.remove('is-hidden');
                if (editBtn) editBtn.classList.remove('is-hidden');
            } else {
                formEl.submit();
            }
        } catch (err) {
            formEl.submit();
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnHtml;
            }
        }
    });
}

function initSafetyRulesSignerModal() {
    if (document._safetyRulesSignerModalBound) return;
    document._safetyRulesSignerModalBound = true;

    // Ouverture déléguée
    document.addEventListener('click', (e) => {
        const openBtn = e.target.closest('.js-open-add-safety-signer-modal');
        if (openBtn) {
            e.preventDefault();
            const modal = document.getElementById('addSafetyRulesSignerModal');
            if (modal) {
                modal.classList.remove('u-d-none');
                modal.classList.add('is-active');
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
            }
            return;
        }

        // Fermeture via bouton fermer ou annuler
        const closeBtn = e.target.closest('.js-close-safety-signer-modal');
        if (closeBtn) {
            e.preventDefault();
            const modal = document.getElementById('addSafetyRulesSignerModal');
            if (modal) {
                modal.classList.add('u-d-none');
                modal.classList.remove('is-active');
            }
            return;
        }

        // Fermeture au clic sur le fond (overlay)
        const modal = document.getElementById('addSafetyRulesSignerModal');
        if (modal && e.target === modal) {
            modal.classList.add('u-d-none');
            modal.classList.remove('is-active');
        }
    });

    // Fermeture avec la touche Échap
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' || e.key === 'Esc') {
            const modal = document.getElementById('addSafetyRulesSignerModal');
            if (modal && modal.classList.contains('is-active')) {
                modal.classList.add('u-d-none');
                modal.classList.remove('is-active');
            }
        }
    });

    // Bascule du champ personnalisé "Autre"
    document.addEventListener('change', (e) => {
        if (e.target && e.target.id === 'new_signer_role') {
            const customRoleGroup = document.getElementById('new_signer_role_custom_group');
            if (customRoleGroup) {
                if (e.target.value === 'other') {
                    customRoleGroup.classList.remove('u-d-none');
                    const customInput = customRoleGroup.querySelector('input');
                    if (customInput) customInput.focus();
                } else {
                    customRoleGroup.classList.add('u-d-none');
                }
            }
        }
    });
}

function initPilotSignerModal() {
    if (document._pilotSignerModalBound) return;
    document._pilotSignerModalBound = true;

    function updatePilotVehicleValidation(modal) {
        if (!modal) return;
        const checked = modal.querySelectorAll('input[name="selected_vehicles"]:checked');
        const err = modal.querySelector('#pilotVehiclesError');
        const submitBtn = modal.querySelector('button[type="submit"]');
        const hasVehicles = checked.length > 0;

        if (err) {
            if (hasVehicles) {
                err.classList.add('u-d-none');
            } else {
                err.classList.remove('u-d-none');
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
            }
        }

        if (submitBtn) {
            submitBtn.disabled = !hasVehicles;
            submitBtn.classList.toggle('is-disabled', !hasVehicles);
        }
    }

    // Ouverture déléguée
    document.addEventListener('click', (e) => {
        const openBtn = e.target.closest('.js-open-add-pilot-signer-modal');
        if (openBtn) {
            e.preventDefault();
            const modal = document.getElementById('addPilotSignerModal');
            if (modal) {
                updatePilotVehicleValidation(modal);
                modal.classList.remove('u-d-none');
                modal.classList.add('is-active');
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
            }
            return;
        }

        // Fermeture via bouton fermer ou annuler
        const closeBtn = e.target.closest('.js-close-pilot-signer-modal');
        if (closeBtn) {
            e.preventDefault();
            const modal = document.getElementById('addPilotSignerModal');
            if (modal) {
                modal.classList.add('u-d-none');
                modal.classList.remove('is-active');
            }
            return;
        }

        // Fermeture au clic sur le fond (overlay)
        const modal = document.getElementById('addPilotSignerModal');
        if (modal && e.target === modal) {
            modal.classList.add('u-d-none');
            modal.classList.remove('is-active');
        }
    });

    // Fermeture avec la touche Échap
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' || e.key === 'Esc') {
            const modal = document.getElementById('addPilotSignerModal');
            if (modal && modal.classList.contains('is-active')) {
                modal.classList.add('u-d-none');
                modal.classList.remove('is-active');
            }
        }
    });

    // Bascule dynamique visuelle sur les cartes à cocher .project-checkbox-card
    document.addEventListener('change', (e) => {
        const cb = e.target;
        if (cb && cb.matches('.project-checkbox-card input[type="checkbox"]')) {
            const card = cb.closest('.project-checkbox-card');
            if (card) {
                card.classList.toggle('selected', cb.checked);
            }
            if (cb.matches('#addPilotSignerModal input[name="selected_vehicles"]')) {
                const modal = document.getElementById('addPilotSignerModal');
                if (modal) {
                    updatePilotVehicleValidation(modal);
                }
            }
        }
    });

    // Validation à la soumission du formulaire d'attestation pilote : empêche la création si aucun véhicule sélectionné
    document.addEventListener('submit', (e) => {
        const form = e.target.closest('#addPilotSignerForm, #addPilotSignerModal form');
        if (!form) return;

        const checkedVehicles = form.querySelectorAll('input[name="selected_vehicles"]:checked');
        if (checkedVehicles.length === 0) {
            e.preventDefault();
            e.stopImmediatePropagation();

            const modal = form.closest('#addPilotSignerModal') || document.getElementById('addPilotSignerModal');
            if (modal) {
                updatePilotVehicleValidation(modal);
                const err = modal.querySelector('#pilotVehiclesError');
                if (err) {
                    err.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }

            if (typeof window.showFlash === 'function') {
                window.showFlash("Veuillez sélectionner au moins 1 véhicule.", "error");
            }
            return false;
        }
    });
}

function initRiskSignerModal() {
    if (document._riskSignerModalBound) return;
    document._riskSignerModalBound = true;

    // Ouverture déléguée
    document.addEventListener('click', (e) => {
        const openBtn = e.target.closest('.js-open-add-risk-signer-modal');
        if (openBtn) {
            e.preventDefault();
            const modal = document.getElementById('addRiskSignerModal');
            if (modal) {
                modal.classList.remove('u-d-none');
                modal.classList.add('is-active');
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
            }
            return;
        }

        const closeBtn = e.target.closest('.js-close-risk-signer-modal');
        if (closeBtn) {
            e.preventDefault();
            const modal = document.getElementById('addRiskSignerModal');
            if (modal) {
                modal.classList.add('u-d-none');
                modal.classList.remove('is-active');
            }
            return;
        }

        const modal = document.getElementById('addRiskSignerModal');
        if (modal && e.target === modal) {
            modal.classList.add('u-d-none');
            modal.classList.remove('is-active');
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' || e.key === 'Esc') {
            const modal = document.getElementById('addRiskSignerModal');
            if (modal && modal.classList.contains('is-active')) {
                modal.classList.add('u-d-none');
                modal.classList.remove('is-active');
            }
        }
    });

    document.addEventListener('change', (e) => {
        if (e.target && e.target.id === 'new_risk_signer_role') {
            const customRoleGroup = document.getElementById('new_risk_signer_role_custom_group');
            if (customRoleGroup) {
                if (e.target.value === 'other') {
                    customRoleGroup.classList.remove('u-d-none');
                    const customInput = customRoleGroup.querySelector('input');
                    if (customInput) customInput.focus();
                } else {
                    customRoleGroup.classList.add('u-d-none');
                }
            }
        }
    });
}

function initRoadLegalToggle() {
    document.addEventListener('click', async (e) => {
        const btn = e.target.closest('.js-toggle-road-legal');
        if (!btn || btn.classList.contains('is-loading')) return;

        e.preventDefault();
        const url = btn.dataset.url;
        if (!url) return;

        btn.classList.add('is-loading');

        try {
            const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfTokenMeta ? csrfTokenMeta.getAttribute('content') : '';

            const resp = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({})
            });

            if (!resp.ok) {
                throw new Error('Erreur réseau lors de la bascule');
            }

            const data = await resp.json();
            if (data.status === 'success') {
                const isLegal = data.is_road_legal;
                btn.classList.toggle('is-road-legal', isLegal);
                btn.classList.toggle('is-closed-road', !isLegal);

                const label = btn.querySelector('.js-road-legal-label');
                if (label) {
                    label.textContent = isLegal ? 'Homologué route' : 'Route fermée';
                }

                const icon = btn.querySelector('i, svg');
                if (icon) {
                    const newIconName = isLegal ? 'check-circle' : 'alert-triangle';
                    icon.setAttribute('data-lucide', newIconName);
                    // Remplacement dynamique du markup SVG si nécessaire
                    if (window.lucide && typeof window.lucide.createIcons === 'function') {
                        window.lucide.createIcons({
                            root: btn
                        });
                    }
                }
            } else {
                alert(data.message || 'Erreur lors de la modification.');
            }
        } catch (err) {
            console.error('Erreur toggle road legal:', err);
            alert('Impossible de mettre à jour le statut du véhicule.');
        } finally {
            btn.classList.remove('is-loading');
        }
    });
}

function initProjectInteractions() {
    try { initProjectFormHighlight(); } catch (e) { console.error('Error in initProjectFormHighlight', e); }
    try { initProjectDateValidation(); } catch (e) { console.error('Error in initProjectDateValidation', e); }
    try { initVehiclesModal(); } catch (e) { console.error('Error in initVehiclesModal', e); }
    try { initProjectNotionSlashEditor(); } catch (e) { console.error('Error in initProjectNotionSlashEditor', e); }
    try { initProjectReportsCollapsible(); } catch (e) { console.error('Error in initProjectReportsCollapsible', e); }
    try { initProjectReportsEdit(); } catch (e) { console.error('Error in initProjectReportsEdit', e); }
    try { initProjectNotesEdit(); } catch (e) { console.error('Error in initProjectNotesEdit', e); }
    try { initSafetyRulesSignerModal(); } catch (e) { console.error('Error in initSafetyRulesSignerModal', e); }
    try { initPilotSignerModal(); } catch (e) { console.error('Error in initPilotSignerModal', e); }
    try { initRiskSignerModal(); } catch (e) { console.error('Error in initRiskSignerModal', e); }
    try { initRoadLegalToggle(); } catch (e) { console.error('Error in initRoadLegalToggle', e); }
}

window.initSafetyRulesSignerModal = initSafetyRulesSignerModal;
window.initPilotSignerModal = initPilotSignerModal;
window.initRiskSignerModal = initRiskSignerModal;
window.initRoadLegalToggle = initRoadLegalToggle;
window.initProjectInteractions = initProjectInteractions;

// Initialisation immédiate des écouteurs de modals dès l'évaluation du script
initSafetyRulesSignerModal();
initPilotSignerModal();
initRiskSignerModal();
initRoadLegalToggle();

