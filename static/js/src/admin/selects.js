/**
 * selects.js — Contrôles déroulants enrichis (Badge selects, Projets, Véhicules, Contrôleurs).
 */

let updateVehicleOptions = null;

function updateVehicleContextAlert() {
    const alertEl = document.getElementById('vehicleContextAlert');
    if (!alertEl) return;

    const titleEl = document.getElementById('vehicleContextAlertTitle');
    const descEl = document.getElementById('vehicleContextAlertDesc');
    const forceAction = document.getElementById('forceCheckinAction');
    const forceCheckbox = document.getElementById('forceCheckinCheckbox');

    const pInput = document.querySelector('#projectSelect input[name="project_id"]');
    const vInput = document.querySelector('#vehicleSelect input[name="vehicle_id"]');

    const selectedProjectId = pInput ? pInput.value : '';
    const selectedVehicleId = vInput ? vInput.value : '';

    if (!selectedProjectId || !selectedVehicleId) {
        alertEl.classList.remove('is-visible');
        if (forceAction) forceAction.classList.add('u-d-none');
        return;
    }

    const vOpt = document.querySelector(`#vehicleOptions .rich-select-option[data-id="${selectedVehicleId}"]`);
    if (!vOpt) {
        alertEl.classList.remove('is-visible');
        if (forceAction) forceAction.classList.add('u-d-none');
        return;
    }

    const checkoutStatuses = JSON.parse(vOpt.dataset.checkoutStatuses || '{}');
    const checkinStatuses = JSON.parse(vOpt.dataset.checkinStatuses || '{}');
    const checkoutStatus = checkoutStatuses[selectedProjectId];
    const checkinStatus = checkinStatuses[selectedProjectId];

    // Vérifier si formulaire Check-in ou Checkout
    const isCheckinForm = vOpt.hasAttribute('data-checkin-statuses');
    const isCheckoutForm = vOpt.hasAttribute('data-checkout-statuses') && !isCheckinForm;

    let hasWarning = false;
    let titleText = 'Attention';
    let descText = '';
    let showForceCheckbox = false;

    if (isCheckinForm) {
        // En Check-in :
        // Si tout va bien (départ signé/validé, et pas de check-in déjà fait) => ON N'AFFICHE RIEN
        const isCheckoutSigned = (checkoutStatus === 'signed' || checkoutStatus === 'validated');

        if (checkinStatus) {
            // Un retour a déjà été enregistré pour ce projet
            hasWarning = true;
            titleText = 'Retour déjà enregistré';
            const statusLabel = (checkinStatus === 'signed' || checkinStatus === 'validated') ? 'validé' : 'en cours';
            descText = `Un état des lieux de retour a déjà été enregistré pour ce véhicule sur ce projet (${statusLabel}).`;
        } else if (!isCheckoutSigned) {
            // Aucun départ ou départ non signé
            hasWarning = true;
            titleText = 'Départ non validé';
            if (checkoutStatus) {
                descText = 'Le départ de ce véhicule est en cours mais n\'a pas encore été validé par une signature.';
            } else {
                descText = 'Aucun état des lieux de départ n\'a été enregistré pour ce véhicule sur ce projet.';
            }
            showForceCheckbox = true;
        }
    } else if (isCheckoutForm) {
        // En Checkout :
        // Si tout va bien (véhicule disponible, pas déjà parti pour ce projet) => ON N'AFFICHE RIEN
        const blockedByProject = vOpt.dataset.blockedBy;

        if (checkoutStatus) {
            hasWarning = true;
            titleText = 'Départ déjà existant';
            const statusLabel = (checkoutStatus === 'signed' || checkoutStatus === 'validated') ? 'validé' : 'en cours';
            descText = `Un départ a déjà été enregistré pour ce véhicule sur ce projet (${statusLabel}).`;
        } else if (blockedByProject) {
            hasWarning = true;
            titleText = 'Véhicule en cours d\'utilisation';
            descText = `Ce véhicule est actuellement engagé sur un autre projet (« ${blockedByProject} ») et son retour n'a pas encore été validé.`;
        }
    }

    if (hasWarning) {
        if (titleEl) titleEl.textContent = titleText;
        if (descEl) descEl.textContent = descText;
        alertEl.classList.add('is-visible');
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }

        if (forceAction) {
            if (showForceCheckbox) {
                forceAction.classList.remove('u-d-none');
            } else {
                forceAction.classList.add('u-d-none');
                if (forceCheckbox) forceCheckbox.checked = false;
            }
        }
    } else {
        alertEl.classList.remove('is-visible');
        if (forceAction) {
            forceAction.classList.add('u-d-none');
            if (forceCheckbox) forceCheckbox.checked = false;
        }
    }
}

function initBadgeSelects() {
    document.querySelectorAll('.badge-select').forEach(sel => {
        const trigger = sel.querySelector('.badge-select-trigger');
        const input = sel.querySelector('input');
        const pill = trigger ? trigger.querySelector('.badge-pill') : null;

        if (!trigger || !input) return;

        trigger.addEventListener('click', () => {
            document.querySelectorAll('.badge-select.open').forEach(s => {
                if (s !== sel) s.classList.remove('open');
            });
            document.querySelectorAll('.rich-select.open').forEach(s => s.classList.remove('open'));
            sel.classList.toggle('open');
        });

        sel.querySelectorAll('.badge-select-option').forEach(opt => {
            opt.addEventListener('click', () => {
                const val = opt.dataset.value;
                const optPill = opt.querySelector('.badge-pill');
                input.value = val;
                if (pill) {
                    if (optPill) {
                        pill.innerHTML = optPill.innerHTML;
                    } else {
                        pill.textContent = val;
                    }
                    pill.dataset.val = val;
                    if (window.lucide && typeof window.lucide.createIcons === 'function') {
                        window.lucide.createIcons();
                    }
                }
                sel.classList.remove('open');
            });
        });
    });
}

function initProjectSelect() {
    const pSelect = document.getElementById('projectSelect');
    if (!pSelect) return;

    const pTrigger = document.getElementById('projectTrigger');
    const pInput = pSelect.querySelector('input[name="project_id"]');
    const pLabel = document.getElementById('projectLabel');
    const pSearch = document.getElementById('projectSearch');
    const pOptions = document.querySelectorAll('#projectOptions .rich-select-option');

    if (!pTrigger || !pInput) return;

    pTrigger.addEventListener('click', () => {
        document.querySelectorAll('.badge-select.open').forEach(s => s.classList.remove('open'));
        pSelect.classList.toggle('open');
        if (pSelect.classList.contains('open') && pSearch) {
            pSearch.value = '';
            pOptions.forEach(o => o.style.display = '');
            setTimeout(() => pSearch.focus(), 50);
        }
    });

    if (pSearch) {
        pSearch.addEventListener('input', () => {
            const q = pSearch.value.toLowerCase();
            pOptions.forEach(opt => {
                const text = (opt.dataset.search || opt.dataset.name || '').toLowerCase();
                opt.style.display = text.includes(q) ? '' : 'none';
            });
        });
    }

    updateVehicleOptions = (opt) => {
        if (!opt) return;

        // Activer le sélecteur de véhicule
        const vSelectEl = document.getElementById('vehicleSelect');
        if (vSelectEl) {
            vSelectEl.classList.remove('u-disabled-select');
            vSelectEl.style.opacity = '';
            vSelectEl.style.pointerEvents = '';
            vSelectEl.removeAttribute('data-disabled');
        }

        pInput.dispatchEvent(new Event('change', { bubbles: true }));

        const selectedProjectId = pInput.value;
        const vehiclesStr = opt.dataset.vehicles || '';
        const allowedVehicles = vehiclesStr ? vehiclesStr.split(',').map(s => s.trim()).filter(Boolean) : [];
        const vOptions = document.querySelectorAll('#vehicleOptions .rich-select-option');
        const vInput = document.querySelector('#vehicleSelect input[name="vehicle_id"]');
        const vLabel = document.getElementById('vehicleLabel');
        const noVehNotice = document.getElementById('noVehicleNotice');
        const selProjNotice = document.getElementById('selectProjectNotice');

        if (selProjNotice) selProjNotice.style.display = selectedProjectId ? 'none' : 'block';

        if (!selectedProjectId) {
            if (vOptions) vOptions.forEach(o => o.style.display = 'none');
            if (noVehNotice) noVehNotice.style.display = 'none';
            if (vInput && vInput.value) {
                vInput.value = '';
                if (vLabel) vLabel.textContent = "— Sélectionnez d'abord un projet —";
                vInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
            return;
        }

        if (allowedVehicles.length === 0) {
            if (vOptions) vOptions.forEach(o => o.style.display = 'none');
            if (noVehNotice) noVehNotice.style.display = 'block';
            if (vInput) {
                vInput.value = '';
                if (vLabel) vLabel.textContent = "— Aucun véhicule rattaché à ce projet —";
                vInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
            return;
        }

        if (noVehNotice) noVehNotice.style.display = 'none';

        // Afficher UNIQUEMENT les véhicules rattachés au projet
        if (vOptions && vOptions.length) {
            vOptions.forEach(vOpt => {
                const vid = vOpt.dataset.id;
                if (!vid || !allowedVehicles.includes(vid)) {
                    vOpt.style.display = 'none';
                    return;
                }

                vOpt.style.display = '';
                vOpt.removeAttribute('data-disabled');
            });

            // Réinitialiser si le véhicule actuellement sélectionné ne fait plus partie du projet
            if (vInput && vInput.value && !allowedVehicles.includes(vInput.value)) {
                vInput.value = '';
                if (vLabel) vLabel.textContent = '— Sélectionner un véhicule —';
                vInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        updateVehicleContextAlert();
    };

    pOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            if (opt.dataset.disabled === 'true') return;
            pInput.value = opt.dataset.id;
            if (pLabel) pLabel.textContent = opt.dataset.name;
            pSelect.classList.remove('open');
            updateVehicleOptions(opt);
        });
    });

    if (pInput.value) {
        const initialOpt = Array.from(pOptions).find(o => o.dataset.id === pInput.value);
        if (initialOpt) updateVehicleOptions(initialOpt);
    } else {
        const vOptionsInitial = document.querySelectorAll('#vehicleOptions .rich-select-option');
        if (vOptionsInitial) vOptionsInitial.forEach(o => o.style.display = 'none');
        const selProjNotice = document.getElementById('selectProjectNotice');
        if (selProjNotice) selProjNotice.style.display = 'block';
    }
}

function initVehicleSelect() {
    const vSelect = document.getElementById('vehicleSelect');
    if (!vSelect) return;

    const vTrigger = document.getElementById('vehicleTrigger');
    const vInput = vSelect.querySelector('input[name="vehicle_id"]');
    const vLabel = document.getElementById('vehicleLabel');
    const vSearch = document.getElementById('vehicleSearch');
    const vOptions = document.querySelectorAll('#vehicleOptions .rich-select-option');

    if (!vTrigger || !vInput) return;

    vTrigger.addEventListener('click', () => {
        const pInput = document.querySelector('#projectSelect input[name="project_id"]');
        const selectedProjectId = pInput ? pInput.value : '';

        // Si aucun projet sélectionné, guider l'utilisateur en ouvrant le sélecteur de projet
        if (!selectedProjectId) {
            const pSelect = document.getElementById('projectSelect');
            if (pSelect) {
                document.querySelectorAll('.badge-select.open').forEach(s => s.classList.remove('open'));
                document.querySelectorAll('.rich-select.open').forEach(s => s.classList.remove('open'));
                pSelect.classList.add('open');
                const pSearch = document.getElementById('projectSearch');
                if (pSearch) {
                    pSearch.value = '';
                    setTimeout(() => pSearch.focus(), 50);
                }
                return;
            }
        }

        document.querySelectorAll('.badge-select.open').forEach(s => s.classList.remove('open'));
        document.querySelectorAll('.rich-select.open').forEach(s => {
            if (s !== vSelect) s.classList.remove('open');
        });
        vSelect.classList.toggle('open');
        if (vSelect.classList.contains('open')) {
            if (vSearch) {
                vSearch.value = '';
                setTimeout(() => vSearch.focus(), 50);
            }

            // Filtrer pour n'afficher que les véhicules du projet sélectionné via updateVehicleOptions
            const selectedProjectOpt = document.querySelector(
                '#projectOptions .rich-select-option[data-id="' + selectedProjectId + '"]'
            );
            if (typeof updateVehicleOptions === 'function' && selectedProjectOpt) {
                updateVehicleOptions(selectedProjectOpt);
            }
        }
    });

    if (vSearch) {
        vSearch.addEventListener('input', () => {
            const q = vSearch.value.toLowerCase().trim();
            const pInput = document.querySelector('#projectSelect input[name="project_id"]');
            const selectedProjectId = pInput ? pInput.value : '';
            const selectedProjectOpt = document.querySelector(
                '#projectOptions .rich-select-option[data-id="' + selectedProjectId + '"]'
            );
            const vehiclesStr = selectedProjectOpt?.dataset.vehicles || '';
            const allowed = vehiclesStr ? vehiclesStr.split(',').map(s => s.trim()).filter(Boolean) : [];

            vOptions.forEach(opt => {
                const vid = opt.dataset.id;
                if (!vid || !allowed.includes(vid)) {
                    opt.style.display = 'none';
                    return;
                }
                const text = (opt.dataset.search || opt.dataset.name || '').toLowerCase();
                opt.style.display = (!q || text.includes(q)) ? '' : 'none';
            });
        });
    }

    vOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            if (!opt.dataset.id) return;
            vInput.value = opt.dataset.id;
            const thumb = opt.dataset.thumb;
            if (thumb && vLabel) {
                vLabel.innerHTML = `<span class="u-flex u-align-center u-gap-2">
                    <img src="${thumb}" class="vehicle-small-thumbnail">
                    ${opt.dataset.name}
                </span>`;
            } else if (vLabel) {
                vLabel.textContent = opt.dataset.name;
            }
            vSelect.classList.remove('open');
            vInput.dispatchEvent(new Event('change', { bubbles: true }));
            updateVehicleContextAlert();
        });
    });

    vInput.addEventListener('change', updateVehicleContextAlert);
    updateVehicleContextAlert();
}

function initControllerSelect() {
    const cSelect = document.getElementById('controllerSelect');
    if (!cSelect) return;

    const cTrigger = document.getElementById('controllerTrigger');
    const cInput = cSelect.querySelector('input[name="controller_id"]');
    const cLabel = document.getElementById('controllerLabel');
    const cOptions = document.querySelectorAll('#controllerOptions .rich-select-option');

    if (!cTrigger || !cInput) return;

    cTrigger.addEventListener('click', () => {
        document.querySelectorAll('.badge-select.open').forEach(s => s.classList.remove('open'));
        document.querySelectorAll('.rich-select.open').forEach(s => {
            if (s !== cSelect) s.classList.remove('open');
        });
        cSelect.classList.toggle('open');
    });

    cOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            if (opt.dataset.disabled === 'true') return;
            cInput.value = opt.dataset.id;
            if (cLabel) cLabel.textContent = opt.dataset.name;
            cSelect.classList.remove('open');
        });
    });
}

function initSelects() {
    initBadgeSelects();
    initProjectSelect();
    initVehicleSelect();
    initControllerSelect();
    updateVehicleContextAlert();
}

window.initSelects = initSelects;
window.updateVehicleContextAlert = updateVehicleContextAlert;
