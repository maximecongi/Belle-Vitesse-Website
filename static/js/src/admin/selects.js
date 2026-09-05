/**
 * selects.js — Contrôles déroulants enrichis (Badge selects, Projets, Véhicules, Contrôleurs).
 */

let updateVehicleOptions = null;

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
                const label = opt.querySelector('.badge-pill')?.textContent || val;
                input.value = val;
                if (pill) {
                    pill.textContent = label;
                    pill.dataset.val = val;
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
            const statusMap = {
                'signed': 'Signé',
                'pending': 'À signer',
                'in_progress': 'En cours',
                'validated': 'Validé',
                'to_sign': 'À signer'
            };

            vOptions.forEach(vOpt => {
                const vid = vOpt.dataset.id;
                if (!vid || !allowedVehicles.includes(vid)) {
                    vOpt.style.display = 'none';
                    return;
                }

                vOpt.style.display = '';
                vOpt.removeAttribute('data-disabled');

                const checkoutStatuses = JSON.parse(vOpt.dataset.checkoutStatuses || '{}');
                const checkinStatuses = JSON.parse(vOpt.dataset.checkinStatuses || '{}');
                const checkoutStatus = checkoutStatuses[selectedProjectId];
                const checkinStatus = checkinStatuses[selectedProjectId];
                const badgeEl = vOpt.querySelector('.vehicle-status-badge');

                if (vOpt.hasAttribute('data-checkin-statuses')) {
                    // Formulaire de Retour (Check-in)
                    const isCheckoutSigned = (checkoutStatus === 'signed' || checkoutStatus === 'validated');
                    if (checkinStatus) {
                        if (badgeEl) {
                            badgeEl.textContent = 'Retour : ' + (statusMap[checkinStatus] || checkinStatus);
                            badgeEl.style.background = "var(--input-bg)";
                            badgeEl.style.color = "var(--text-color)";
                        }
                    } else if (isCheckoutSigned) {
                        if (badgeEl) {
                            badgeEl.textContent = "À contrôler";
                            badgeEl.style.background = "#059669";
                            badgeEl.style.color = "#ffffff";
                        }
                    } else if (checkoutStatus) {
                        if (badgeEl) {
                            badgeEl.textContent = "Départ en cours (" + (statusMap[checkoutStatus] || checkoutStatus) + ")";
                            badgeEl.style.background = "#fef3c7";
                            badgeEl.style.color = "#92400e";
                        }
                    } else {
                        if (badgeEl) {
                            badgeEl.textContent = "À contrôler";
                            badgeEl.style.background = "var(--brand-blue)";
                            badgeEl.style.color = "#ffffff";
                        }
                    }
                } else if (vOpt.hasAttribute('data-checkout-statuses')) {
                    // Formulaire de Départ (Check-out)
                    const blockedByProject = vOpt.dataset.blockedBy;
                    if (checkoutStatus) {
                        if (badgeEl) {
                            badgeEl.textContent = 'Départ : ' + (statusMap[checkoutStatus] || checkoutStatus);
                            badgeEl.style.background = "var(--input-bg)";
                            badgeEl.style.color = "var(--text-color)";
                        }
                    } else if (blockedByProject) {
                        if (badgeEl) {
                            badgeEl.textContent = "Retour en attente : " + blockedByProject;
                            badgeEl.style.background = "#fee2e2";
                            badgeEl.style.color = "#dc2626";
                        }
                    } else {
                        if (badgeEl) {
                            badgeEl.textContent = "À contrôler";
                            badgeEl.style.background = "var(--brand-blue)";
                            badgeEl.style.color = "#ffffff";
                        }
                    }
                }
            });

            // Réinitialiser si le véhicule actuellement sélectionné ne fait plus partie du projet
            if (vInput && vInput.value && !allowedVehicles.includes(vInput.value)) {
                vInput.value = '';
                if (vLabel) vLabel.textContent = '— Sélectionner un véhicule —';
                vInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
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
                vLabel.innerHTML = `<span style="display:flex;align-items:center;gap:0.5rem;">
                    <img src="${thumb}" style="width:28px;height:28px;border-radius:4px;object-fit:cover;">
                    ${opt.dataset.name}
                </span>`;
            } else if (vLabel) {
                vLabel.textContent = opt.dataset.name;
            }
            vSelect.classList.remove('open');
            vInput.dispatchEvent(new Event('change', { bubbles: true }));
        });
    });
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
}

window.initSelects = initSelects;
