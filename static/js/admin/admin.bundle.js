/**
 * admin.bundle.js — Bundle JavaScript unifié pour l'administration Belle Vitesse.
 * Concaténé et validé automatiquement par scripts/build_bundles.py.
 */

/* ── js/src/admin/flash.js ── */
/**
 * flash.js — Gestion des messages flash et toasts d'administration.
 */

function dismissFlash(f) {
    if (!f || !f.parentNode) return;
    f.style.opacity = '0';
    f.style.transform = 'translateX(100%)';
    f.style.transition = 'all 0.5s ease';
    setTimeout(() => f.remove(), 500);
}

/**
 * Affiche dynamiquement un message flash (toast).
 * @param {string} message
 * @param {string} category (info, success, warning, error)
 */
window.showFlash = function (message, category = 'info') {
    const container = document.querySelector('.admin-flash-container');
    if (!container) return;

    const flash = document.createElement('div');
    flash.className = `admin-flash-item flash-${category}`;
    flash.textContent = message;

    container.appendChild(flash);

    // Auto-dismiss après 5s
    setTimeout(() => {
        dismissFlash(flash);
    }, 5000);
};

function initFlash() {
    const flashes = document.querySelectorAll('.admin-flash-item');
    if (flashes.length) {
        setTimeout(() => {
            flashes.forEach(f => dismissFlash(f));
        }, 5000);
    }
}

window.initFlash = initFlash;
;

/* ── js/src/admin/nav.js ── */
/**
 * nav.js — Gestion de la navigation, persistance sidebar et liens actifs.
 */

function restoreNavState() {
    document.querySelectorAll('.admin-nav-group').forEach(group => {
        const id = group.dataset.navGroup;
        if (!id) return;
        const state = localStorage.getItem(`nav-group-${id}`);
        if (state === 'open') {
            group.classList.add('open');
        } else if (state === 'closed') {
            group.classList.remove('open');
        } else if (group.classList.contains('default-open')) {
            group.classList.add('open');
        }
    });
}

function updateActiveNavLink() {
    const currentPath = window.location.pathname;
    let bestMatch = null;
    let maxLen = -1;

    const navItems = document.querySelectorAll('.admin-nav-item');
    navItems.forEach(link => {
        link.classList.remove('active');
        const href = link.getAttribute('href');
        if (!href || href === '#' || href === '') return;

        if (href === currentPath) {
            bestMatch = link;
            maxLen = 999;
        } else if (currentPath.startsWith(href) && href !== '/admin/dashboard' && href !== '/admin') {
            if (href.length > maxLen) {
                maxLen = href.length;
                bestMatch = link;
            }
        }
    });

    if (bestMatch) {
        bestMatch.classList.add('active');
    }
}

// Global click listener pour sidebar triggers et fermeture dropdowns/tooltips
if (!window._adminNavClickAttached) {
    window._adminNavClickAttached = true;
    document.addEventListener('click', e => {
        const trigger = e.target.closest('.admin-nav-group-trigger');
        if (trigger) {
            const group = trigger.closest('.admin-nav-group');
            group.classList.toggle('open');

            const id = group.dataset.navGroup;
            if (id) {
                localStorage.setItem(`nav-group-${id}`, group.classList.contains('open') ? 'open' : 'closed');
            }
        }

        // Fermeture des menus déroulants et tooltips en cliquant en dehors
        if (!e.target.closest('.badge-select') && !e.target.closest('.rich-select') && !e.target.closest('.admin-tooltip-container')) {
            document.querySelectorAll('.badge-select.open, .rich-select.open, .admin-tooltip-container.open')
                .forEach(s => s.classList.remove('open'));
        }

        const tooltipTrigger = e.target.closest('.note-tooltip-trigger');
        if (tooltipTrigger) {
            const container = tooltipTrigger.closest('.admin-tooltip-container');
            const wasOpen = container.classList.contains('open');
            document.querySelectorAll('.admin-tooltip-container.open').forEach(c => c.classList.remove('open'));
            if (!wasOpen) {
                container.classList.add('open');
            }
        }
    });
}

// ── Gestion du tiroir latéral escamotable pour tablette & mobile ─
function initSidebarDrawer() {
    const sidebar = document.getElementById('adminSidebar');
    const toggle = document.getElementById('adminSidebarToggle');
    const backdrop = document.getElementById('adminSidebarBackdrop');
    const closeBtn = document.getElementById('adminSidebarClose');

    if (!sidebar || !toggle) return;

    function openSidebar() {
        sidebar.classList.add('is-open');
        if (backdrop) backdrop.classList.add('is-active');
        toggle.setAttribute('aria-expanded', 'true');
        document.body.classList.add('u-overflow-hidden');
        if (window.bvIpadBridge) window.bvIpadBridge.triggerHaptic('light');
    }

    function closeSidebar() {
        sidebar.classList.remove('is-open');
        if (backdrop) backdrop.classList.remove('is-active');
        toggle.setAttribute('aria-expanded', 'false');
        document.body.classList.remove('u-overflow-hidden');
    }

    toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        if (sidebar.classList.contains('is-open')) {
            closeSidebar();
        } else {
            openSidebar();
        }
    });

    if (backdrop) {
        backdrop.addEventListener('click', closeSidebar);
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', closeSidebar);
    }

    // Fermer avec Échap
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar.classList.contains('is-open')) {
            closeSidebar();
        }
    });

    // Fermer le tiroir lors du clic sur un lien nav (sur tablette)
    sidebar.querySelectorAll('.admin-nav-item').forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 1200) {
                closeSidebar();
            }
        });
    });

    // Support du geste de balayage (swipe vers la gauche) pour fermer le tiroir
    let touchStartX = 0;
    sidebar.addEventListener('touchstart', (e) => {
        touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });

    sidebar.addEventListener('touchend', (e) => {
        const touchEndX = e.changedTouches[0].screenX;
        if (touchStartX - touchEndX > 50) {
            closeSidebar();
        }
    }, { passive: true });
}

function initNav() {
    restoreNavState();
    updateActiveNavLink();
    initSidebarDrawer();
}

window.initNav = initNav;
window.restoreNavState = restoreNavState;
window.updateActiveNavLink = updateActiveNavLink;

// Support Swup et initialisation directe
document.addEventListener('swup:contentReplaced', restoreNavState);
document.addEventListener('swup:contentReplaced', updateActiveNavLink);
document.addEventListener('swup:transitionEnd', updateActiveNavLink);

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNav);
} else {
    initNav();
}
;

/* ── js/src/admin/selects.js ── */
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

    const submitBtn = document.querySelector('#inspectionForm button[type="submit"], form button[type="submit"]');

    if (!selectedProjectId || !selectedVehicleId) {
        alertEl.classList.remove('is-visible');
        if (forceAction) forceAction.classList.add('u-d-none');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.classList.remove('is-disabled');
            submitBtn.removeAttribute('title');
        }
        return;
    }

    const vOpt = document.querySelector(`#vehicleOptions .rich-select-option[data-id="${selectedVehicleId}"]`);
    if (!vOpt) {
        alertEl.classList.remove('is-visible');
        if (forceAction) forceAction.classList.add('u-d-none');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.classList.remove('is-disabled');
            submitBtn.removeAttribute('title');
        }
        return;
    }

    const checkoutStatuses = JSON.parse(vOpt.dataset.checkoutStatuses || '{}');
    const checkinStatuses = JSON.parse(vOpt.dataset.checkinStatuses || '{}');
    const rawCheckout = checkoutStatuses[selectedProjectId];
    const rawCheckin = checkinStatuses[selectedProjectId];

    const checkoutStatus = (rawCheckout && typeof rawCheckout === 'object') ? rawCheckout.status : rawCheckout;
    const checkoutId = (rawCheckout && typeof rawCheckout === 'object') ? rawCheckout.id : null;
    const checkoutCode = (rawCheckout && typeof rawCheckout === 'object') ? rawCheckout.code : null;

    const checkinStatus = (rawCheckin && typeof rawCheckin === 'object') ? rawCheckin.status : rawCheckin;
    const checkinId = (rawCheckin && typeof rawCheckin === 'object') ? rawCheckin.id : null;
    const checkinCode = (rawCheckin && typeof rawCheckin === 'object') ? rawCheckin.code : null;

    // Vérifier si formulaire Check-in ou Checkout
    const isCheckinForm = window.location.pathname.includes('/checkin') || vOpt.hasAttribute('data-checkin-statuses');
    const isCheckoutForm = vOpt.hasAttribute('data-checkout-statuses') && !isCheckinForm;

    let hasWarning = false;
    let titleText = 'Attention';
    let descText = '';
    let showForceCheckbox = false;

    if (isCheckinForm) {
        // En Check-in :
        const signedStatuses = ['signed', 'validated', 'completed', 'approved', 'ok', 'signé', 'validé'];
        const isCheckoutSigned = checkoutStatus && signedStatuses.includes(String(checkoutStatus).trim().toLowerCase());

        if (checkinStatus) {
            // Un retour existe déjà pour ce véhicule sur ce projet : VALIDATION BLOQUÉE
            hasWarning = true;
            const isSigned = (checkinStatus === 'signed' || checkinStatus === 'validated' || checkinStatus === 'completed');
            titleText = isSigned ? 'Retour déjà validé' : 'Retour déjà en cours';
            const statusLabel = isSigned ? 'validé' : 'en cours';
            const linkHtml = checkinId ? ` <a href="/admin/checkins/${checkinId}" class="u-text-underline u-fw-bold u-ml-1">Consulter le retour existant (${checkinCode || 'n° ' + checkinId}) →</a>` : '';
            descText = `Un état des lieux de retour est déjà enregistré pour ce véhicule sur ce projet (${statusLabel}). La validation d'un nouveau retour est impossible tant qu'il n'a pas été supprimé ou clôturé.${linkHtml}`;
            showForceCheckbox = false;

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.classList.add('is-disabled');
                submitBtn.setAttribute('title', 'Impossible de valider : un retour est déjà en cours pour ce véhicule');
            }
        } else {
            // Aucun retour n'existe encore
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.classList.remove('is-disabled');
                submitBtn.removeAttribute('title');
            }

            if (!isCheckoutSigned) {
                // Aucun départ ou départ non signé
                hasWarning = true;
                titleText = 'Départ non validé';
                if (checkoutStatus) {
                    const coLink = checkoutId ? ` <a href="/admin/checkouts/${checkoutId}" class="u-text-underline u-fw-bold u-ml-1">Consulter le départ (${checkoutCode || 'n° ' + checkoutId}) →</a>` : '';
                    descText = `Le départ de ce véhicule est en cours mais n'a pas encore été validé par une signature.${coLink}`;
                } else {
                    descText = 'Aucun état des lieux de départ n\'a été enregistré pour ce véhicule sur ce projet.';
                }
                showForceCheckbox = true;
            }
        }
    } else if (isCheckoutForm) {
        // En Checkout :
        const blockedByProject = vOpt.dataset.blockedBy;

        if (checkoutStatus) {
            hasWarning = true;
            titleText = 'Départ déjà existant';
            const statusLabel = (checkoutStatus === 'signed' || checkoutStatus === 'validated') ? 'validé' : 'en cours';
            const coLink = checkoutId ? ` <a href="/admin/checkouts/${checkoutId}" class="u-text-underline u-fw-bold u-ml-1">Consulter le départ existant (${checkoutCode || '#' + checkoutId}) →</a>` : '';
            descText = `Un départ a déjà été enregistré pour ce véhicule sur ce projet (${statusLabel}).${coLink}`;

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.classList.add('is-disabled');
                submitBtn.setAttribute('title', 'Impossible de valider : un départ est déjà enregistré pour ce véhicule');
            }
        } else if (blockedByProject) {
            hasWarning = true;
            titleText = 'Véhicule en cours d\'utilisation';
            descText = `Ce véhicule est actuellement engagé sur un autre projet (« ${blockedByProject} ») et son retour n'a pas encore été validé.`;

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.classList.add('is-disabled');
                submitBtn.setAttribute('title', 'Véhicule engagé sur un autre projet');
            }
        } else {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.classList.remove('is-disabled');
                submitBtn.removeAttribute('title');
            }
        }
    }

    if (hasWarning) {
        if (titleEl) titleEl.textContent = titleText;
        if (descEl) descEl.innerHTML = descText;
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
            const isCheckin = window.location.pathname.includes('/checkin') || document.querySelector('#vehicleOptions [data-checkin-statuses]') !== null;

            vOptions.forEach(vOpt => {
                const vid = vOpt.dataset.id;
                if (!vid || !allowedVehicles.includes(vid)) {
                    vOpt.style.display = 'none';
                    return;
                }

                vOpt.style.display = '';

                const statusSlot = vOpt.querySelector('.vehicle-option-status-slot');
                if (statusSlot) statusSlot.innerHTML = '';

                if (isCheckin) {
                    const checkinStatuses = JSON.parse(vOpt.dataset.checkinStatuses || '{}');
                    const rawCheckin = checkinStatuses[selectedProjectId];

                    if (rawCheckin) {
                        const status = typeof rawCheckin === 'object' ? rawCheckin.status : rawCheckin;
                        const isSigned = (status === 'signed' || status === 'validated' || status === 'completed');
                        const badgeLabel = isSigned ? 'Retour effectué' : 'Retour en cours';
                        const badgeVal = isSigned ? 'signed' : 'in_progress';

                        vOpt.setAttribute('data-disabled', 'true');
                        vOpt.classList.add('is-disabled');
                        vOpt.setAttribute('title', isSigned ? 'Le retour de ce véhicule a déjà été effectué' : 'Un retour est déjà en cours pour ce véhicule');

                        if (statusSlot) {
                            statusSlot.innerHTML = `<span class="badge-pill u-text-xs" data-val="${badgeVal}">${badgeLabel}</span>`;
                        }
                    } else {
                        vOpt.removeAttribute('data-disabled');
                        vOpt.classList.remove('is-disabled');
                        vOpt.removeAttribute('title');
                    }
                } else {
                    const checkoutStatuses = JSON.parse(vOpt.dataset.checkoutStatuses || '{}');
                    const rawCheckout = checkoutStatuses[selectedProjectId];
                    const blockedBy = vOpt.dataset.blockedBy;

                    if (rawCheckout) {
                        const status = typeof rawCheckout === 'object' ? rawCheckout.status : rawCheckout;
                        const isSigned = (status === 'signed' || status === 'validated' || status === 'completed');
                        const badgeLabel = isSigned ? 'Départ effectué' : 'Départ en cours';
                        const badgeVal = isSigned ? 'signed' : 'in_progress';

                        vOpt.setAttribute('data-disabled', 'true');
                        vOpt.classList.add('is-disabled');
                        vOpt.setAttribute('title', isSigned ? 'Le départ de ce véhicule a déjà été validé' : 'Un départ est déjà en cours pour ce véhicule');
                        if (statusSlot) {
                            statusSlot.innerHTML = `<span class="badge-pill u-text-xs" data-val="${badgeVal}">${badgeLabel}</span>`;
                        }
                    } else if (blockedBy) {
                        vOpt.setAttribute('data-disabled', 'true');
                        vOpt.classList.add('is-disabled');
                        vOpt.setAttribute('title', `Véhicule engagé sur le projet ${blockedBy}`);
                        if (statusSlot) {
                            statusSlot.innerHTML = `<span class="badge-pill u-text-xs" data-val="warning">Engagé</span>`;
                        }
                    } else {
                        vOpt.removeAttribute('data-disabled');
                        vOpt.classList.remove('is-disabled');
                        vOpt.removeAttribute('title');
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
            if (opt.dataset.disabled === 'true' || opt.classList.contains('is-disabled')) return;
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
;

/* ── js/src/admin/tables.js ── */
/**
 * tables.js — Recherche en temps réel, filtrage par URL (?q=) et tri dynamique des tables.
 */

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function initCheckoutsListSearch() {
    const checkoutSearchInput = document.getElementById('search-input');
    if (!checkoutSearchInput) return;

    const tbody = document.getElementById('checkouts-tbody') || document.getElementById('checkins-tbody');
    if (!tbody) return;

    const rows = tbody.querySelectorAll('tr[data-search]');
    const resultCount = document.getElementById('result-count');
    const noResults = document.getElementById('no-results');

    checkoutSearchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        let visibleCount = 0;

        rows.forEach(row => {
            const searchText = row.getAttribute('data-search') || '';
            if (searchText.includes(query)) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        if (resultCount) resultCount.innerText = visibleCount;
        if (noResults) noResults.style.display = visibleCount === 0 && rows.length > 0 ? 'block' : 'none';
        tbody.style.display = visibleCount === 0 && rows.length > 0 ? 'none' : '';
    });
}

function initCentralizedSearch() {
    const searchableRows = document.querySelectorAll('.searchable-row');
    if (searchableRows.length === 0) return;

    const searchInput = document.getElementById('searchInput') || document.getElementById('search-input');
    const resultCount = document.getElementById('result-count') || document.getElementById('visible-count');
    const noResults = document.getElementById('no-results') || document.getElementById('noResultsRow');

    const filterItems = (query) => {
        const q = query.toLowerCase().trim();
        let visibleCount = 0;
        searchableRows.forEach(row => {
            const searchText = (row.getAttribute('data-search') || '') + ' ' + row.textContent.toLowerCase();
            const matches = searchText.includes(q);
            row.style.display = matches ? '' : 'none';
            if (matches) visibleCount++;
        });

        if (resultCount) resultCount.innerText = visibleCount;
        if (noResults) noResults.style.display = (visibleCount === 0 && searchableRows.length > 0) ? '' : 'none';
    };

    // Gestion du paramètre URL 'q'
    const urlParams = new URLSearchParams(window.location.search);
    const qParam = urlParams.get('q');
    if (qParam) {
        filterItems(qParam);
    }

    if (searchInput) {
        if (qParam) searchInput.value = qParam;
        searchInput.addEventListener('input', e => {
            filterItems(e.target.value);
        });
    }
}

function initSortableColumns() {
    document.querySelectorAll('.admin-table th.sortable').forEach(th => {
        if (th._sortBound) return;
        th._sortBound = true;

        th.addEventListener('click', () => {
            const table = th.closest('table');
            if (!table) return;
            const tbody = table.querySelector('tbody');
            if (!tbody) return;
            const colIdx = parseInt(th.dataset.col, 10);
            const rows = Array.from(tbody.querySelectorAll('tr.searchable-row'));

            const isAsc = th.classList.contains('asc');
            table.querySelectorAll('th.sortable').forEach(h => h.classList.remove('asc', 'desc'));
            th.classList.add(isAsc ? 'desc' : 'asc');

            rows.sort((a, b) => {
                const aCell = a.children[colIdx];
                const bCell = b.children[colIdx];
                const aText = (aCell?.dataset.sort || aCell?.textContent || '').trim().toLowerCase();
                const bText = (bCell?.dataset.sort || bCell?.textContent || '').trim().toLowerCase();
                return isAsc ? bText.localeCompare(aText) : aText.localeCompare(bText);
            });

            rows.forEach(row => tbody.appendChild(row));
        });
    });
}

function initTables() {
    initCheckoutsListSearch();
    initCentralizedSearch();
    initSortableColumns();
}

window.initTables = initTables;
;

/* ── js/src/admin/charts.js ── */
/**
 * charts.js — Initialisation des graphiques Chart.js du tableau de bord.
 */

function initDashboardCharts() {
    const monthlyCanvas = document.getElementById('monthlyChart');
    if (monthlyCanvas && typeof Chart !== 'undefined' && !monthlyCanvas.dataset.initialized) {
        monthlyCanvas.dataset.initialized = 'true';

        fetch('/admin/api/stats')
            .then(response => response.json())
            .then(data => {
                new Chart(monthlyCanvas, {
                    type: 'bar',
                    data: {
                        labels: data.monthly_activity.labels,
                        datasets: [{
                            label: 'Nombre de checkouts',
                            data: data.monthly_activity.data,
                            backgroundColor: '#FFC845',
                            borderRadius: 4
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { display: false } },
                        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
                    }
                });

                const statusCanvas = document.getElementById('statusChart');
                if (statusCanvas) {
                    new Chart(statusCanvas, {
                        type: 'doughnut',
                        data: {
                            labels: data.status_distribution.labels,
                            datasets: [{
                                data: data.status_distribution.data,
                                backgroundColor: ['#28a745', '#f59e0b', '#dc3545', '#6c757d']
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: { legend: { position: 'bottom' } }
                        }
                    });
                }
            })
            .catch(error => console.error('Error fetching stats:', error));
    }
}

window.initDashboardCharts = initDashboardCharts;
;

/* ── js/src/admin/calendar.js ── */
/**
 * calendar.js — Initialisation et rendu personnalisé de FullCalendar
 * conforme au Design System de Belle Vitesse ERP.
 */

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function getEntityIconSvg(type) {
    if (type === 'checkout') {
        // Lucide 'truck'
        return '<svg class="fc-phase-icon fc-phase-icon--checkout" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18.5" r="2.5"/><circle cx="7" cy="18.5" r="2.5"/></svg>';
    }
    if (type === 'checkin') {
        // Lucide 'package-check'
        return '<svg class="fc-phase-icon fc-phase-icon--checkin" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 16 2 2 4-4"/><path d="M21 10V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l2-1.14"/><path d="m7.5 4.27 9 5.15"/><polyline points="3.29 7 12 12 20.71 7"/><line x1="12" x2="12" y1="22" y2="12"/></svg>';
    }
    // Lucide 'clapperboard' (projet / tournage)
    return '<svg class="fc-phase-icon fc-phase-icon--project" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.2 6 3 11l-.9-2.4 17.2-5z"/><path d="m6.2 5.3 3.1 3.9"/><path d="m12.4 3.4 3.1 4"/><path d="M3 11h18v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>';
}

// ── Gestion de la modale QR Code d'abonnement Calendrier ICS ──
function initCalendarQrModal() {
    const modal = document.getElementById('qrModal');
    if (!modal) return;

    const modalName = document.getElementById('qrModalName');
    const modalImg = document.getElementById('qrModalImg');
    const modalUrlInput = document.getElementById('qrModalUrlInput');
    const copyBtn = document.getElementById('qrModalCopyBtn');
    const webcalBtn = document.getElementById('qrModalWebcalBtn');
    const closeBtn = document.getElementById('qrModalCloseBtn');

    function closeModal() {
        modal.classList.remove('is-active');
    }

    if (closeBtn) {
        closeBtn.onclick = closeModal;
    }

    modal.onclick = function (e) {
        if (e.target === modal) {
            closeModal();
        }
    };

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal.classList.contains('is-active')) {
            closeModal();
        }
    });

    if (copyBtn && modalUrlInput) {
        copyBtn.onclick = function () {
            if (!modalUrlInput.value) return;
            navigator.clipboard.writeText(modalUrlInput.value).then(() => {
                const originalHtml = copyBtn.innerHTML;
                copyBtn.innerHTML = '<span>✅ Copié !</span>';
                setTimeout(() => {
                    copyBtn.innerHTML = originalHtml;
                    if (typeof lucide !== 'undefined' && lucide.createIcons) {
                        lucide.createIcons({ root: copyBtn });
                    }
                }, 1500);
            }).catch(() => {
                modalUrlInput.select();
                document.execCommand('copy');
            });
        };
    }

    document.querySelectorAll('.cal-qr-trigger').forEach(trigger => {
        trigger.onclick = function (e) {
            e.preventDefault();
            e.stopPropagation();

            if (modalName) modalName.textContent = trigger.dataset.name || '';
            if (modalImg && trigger.dataset.qr) {
                modalImg.src = trigger.dataset.qr;
            }
            if (modalUrlInput) {
                modalUrlInput.value = trigger.dataset.url || '';
            }
            if (webcalBtn) {
                webcalBtn.href = trigger.dataset.url || trigger.dataset.webcal || '#';
            }
            modal.classList.add('is-active');

            if (typeof lucide !== 'undefined' && lucide.createIcons) {
                lucide.createIcons({ root: modal });
            }
        };
    });
}

function initCalendar() {
    initCalendarQrModal();

    const calendarEl = document.getElementById('calendar');
    if (calendarEl && typeof FullCalendar !== 'undefined' && !calendarEl.dataset.initialized) {
        calendarEl.dataset.initialized = 'true';

        const calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridWeek',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,dayGridWeek,dayGridDay'
            },
            locale: 'fr',
            eventOrder: "order,start",
            allDayText: 'Toute la journée',
            firstDay: 1,
            buttonText: {
                today: "Aujourd'hui",
                month: 'Mois',
                week: 'Semaine',
                day: 'Jour'
            },
            events: '/admin/api/events',
            eventContent: function (arg) {
                // Squelette de base : la ligne de continuité et le conteneur de badges
                return {
                    html: `
                        <div class="fc-unified-track">
                            <div class="fc-unified-track__line"></div>
                            <div class="fc-unified-track__badges"></div>
                        </div>
                    `
                };
            },
            eventDidMount: function (info) {
                const el = info.el;
                const props = info.event.extendedProps || {};
                const projectName = props.projectName || info.event.title;
                const production = props.production || '';
                const depDate = props.departureDate;
                const shootStart = props.shootStartDate;
                const shootEnd = props.shootEndDate || shootStart;
                const retDate = props.returnDate;

                // Infobulle native complète
                function formatDateFr(dStr) {
                    if (!dStr) return '';
                    const parts = dStr.split('-');
                    return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : dStr;
                }

                const tips = [`Projet : ${projectName}${production ? ' (' + production + ')' : ''}`];
                if (depDate) tips.push(`Départ : ${formatDateFr(depDate)}`);
                if (props.dateMode === 'punctual' && Array.isArray(props.shootDates) && props.shootDates.length > 0) {
                    const immobStr = props.isImmobilized ? 'Immobilisé' : 'Relâché';
                    tips.push(`Tournage ponctuel : ${props.shootDates.map(formatDateFr).join(', ')} (${immobStr})`);
                } else if (shootStart) {
                    const shootEndStr = shootEnd && shootEnd !== shootStart ? ` au ${formatDateFr(shootEnd)}` : '';
                    tips.push(`Tournage : du ${formatDateFr(shootStart)}${shootEndStr}`);
                }
                if (retDate) tips.push(`Retour : ${formatDateFr(retDate)}`);
                el.setAttribute('title', tips.join(' • '));

                // ── Positionnement millimétré des jalons sur leurs cases respectives ──
                const badgesContainer = el.querySelector('.fc-unified-track__badges');
                if (!badgesContainer) return;

                const tr = el.closest('tr');
                if (!tr) return;

                const dayCells = Array.from(tr.querySelectorAll('td.fc-daygrid-day[data-date]'));
                const rowDates = dayCells.map(td => td.getAttribute('data-date'));
                if (rowDates.length === 0) return;

                const harness = el.closest('.fc-daygrid-event-harness');
                let segDates = [];

                if (harness && harness.style.gridColumn) {
                    const parts = harness.style.gridColumn.split('/').map(s => parseInt(s.trim(), 10));
                    if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
                        segDates = rowDates.slice(parts[0] - 1, parts[1] - 1);
                    }
                }

                // Fallback de détection géométrique si gridColumn n'est pas explicite
                if (segDates.length === 0) {
                    const elRect = el.getBoundingClientRect();
                    dayCells.forEach(td => {
                        const tdRect = td.getBoundingClientRect();
                        if (tdRect.right > elRect.left + 2 && tdRect.left < elRect.right - 2) {
                            segDates.push(td.getAttribute('data-date'));
                        }
                    });
                }

                if (segDates.length === 0) {
                    // Dernier repli : affiche le projet sur toute la longueur
                    badgesContainer.innerHTML = `
                        <span class="fc-phase-badge fc-phase-badge--project" style="left:0; width:100%;">
                            <span class="fc-phase-badge__icon">${getEntityIconSvg('project')}</span>
                            <span class="fc-phase-badge__title">${escapeHtml(projectName)}</span>
                        </span>
                    `;
                    return;
                }

                const totalCols = segDates.length;
                const truckSvg = getEntityIconSvg('checkout');
                const clapperSvg = getEntityIconSvg('project');
                const checkinSvg = getEntityIconSvg('checkin');

                let badgesHtml = '';

                // 1. JALON DÉPART (Vert)
                if (depDate) {
                    const depIdx = segDates.indexOf(depDate);
                    const depCoincides = (props.dateMode === 'punctual' && Array.isArray(props.shootDates))
                        ? props.shootDates.includes(depDate)
                        : (depDate === shootStart);
                    if (depIdx !== -1 && !depCoincides) {
                        const left = (depIdx / totalCols) * 100;
                        const width = (1 / totalCols) * 100;
                        badgesHtml += `
                            <span class="fc-phase-badge fc-phase-badge--checkout"
                                  style="left: calc(${left}% + 1px); width: calc(${width}% - 2px);"
                                  title="Départ : ${escapeHtml(depDate)}">
                                ${truckSvg}
                                <span class="fc-phase-badge__label">Départ</span>
                            </span>
                        `;
                    }
                }

                // 2. JALON TOURNAGE (Ambre)
                if (props.dateMode === 'punctual' && Array.isArray(props.shootDates) && props.shootDates.length > 0) {
                    // Regrouper les jours de tournage consécutifs sur la ligne affichée pour ne former qu'une seule entité
                    const shootChunks = [];
                    let curShootChunk = [];

                    segDates.forEach((segD, colIdx) => {
                        if (props.shootDates.includes(segD)) {
                            curShootChunk.push({ colIdx: colIdx, date: segD });
                        } else {
                            if (curShootChunk.length > 0) {
                                shootChunks.push([...curShootChunk]);
                                curShootChunk = [];
                            }
                        }
                    });
                    if (curShootChunk.length > 0) {
                        shootChunks.push(curShootChunk);
                    }

                    shootChunks.forEach((chunk) => {
                        const startCol = chunk[0].colIdx;
                        const count = chunk.length;
                        const left = (startCol / totalCols) * 100;
                        const width = (count / totalCols) * 100;

                        const firstDate = chunk[0].date;
                        const lastDate = chunk[count - 1].date;

                        let shootPrefix = '';
                        if (depDate === firstDate) {
                            shootPrefix = `<span class="fc-phase-coincide fc-phase-coincide--checkout" title="Départ : ${escapeHtml(depDate)}">${truckSvg}</span>`;
                        }

                        let shootSuffix = '';
                        if (retDate === lastDate) {
                            shootSuffix = `<span class="fc-phase-coincide fc-phase-coincide--checkin" title="Retour : ${escapeHtml(retDate)}">${checkinSvg}</span>`;
                        }

                        const rangeLabel = (count > 1)
                            ? `du ${formatDateFr(firstDate)} au ${formatDateFr(lastDate)}`
                            : formatDateFr(firstDate);

                        badgesHtml += `
                            <span class="fc-phase-badge fc-phase-badge--project"
                                  style="left: calc(${left}% + 1px); width: calc(${width}% - 2px);"
                                  title="Tournage : ${escapeHtml(rangeLabel)}">
                                ${shootPrefix}
                                <span class="fc-phase-badge__icon">${clapperSvg}</span>
                                <span class="fc-phase-badge__title">${escapeHtml(projectName)}</span>
                                ${production ? `<span class="fc-phase-badge__prod">${escapeHtml(production)}</span>` : ''}
                                ${shootSuffix}
                            </span>
                        `;
                    });
                } else if (shootStart && shootEnd) {
                    const shootIndices = [];
                    segDates.forEach((d, idx) => {
                        if (d >= shootStart && d <= shootEnd) {
                            shootIndices.push(idx);
                        }
                    });

                    if (shootIndices.length > 0) {
                        const startIdx = shootIndices[0];
                        const count = shootIndices.length;
                        const left = (startIdx / totalCols) * 100;
                        const width = (count / totalCols) * 100;

                        const isFirstShootDay = (segDates[startIdx] === shootStart);
                        const isLastShootDay = (segDates[startIdx + count - 1] === shootEnd);

                        let shootPrefix = '';
                        if (depDate === shootStart && isFirstShootDay) {
                            shootPrefix = `<span class="fc-phase-coincide fc-phase-coincide--checkout" title="Départ : ${escapeHtml(depDate)}">${truckSvg}</span>`;
                        }

                        let shootSuffix = '';
                        if (retDate === shootEnd && isLastShootDay) {
                            shootSuffix = `<span class="fc-phase-coincide fc-phase-coincide--checkin" title="Retour : ${escapeHtml(retDate)}">${checkinSvg}</span>`;
                        }

                        let shootTitle = escapeHtml(projectName);
                        if (!isFirstShootDay) {
                            shootTitle += ' <span class="fc-phase-badge__suite">(suite)</span>';
                        }

                        badgesHtml += `
                            <span class="fc-phase-badge fc-phase-badge--project"
                                  style="left: calc(${left}% + 1px); width: calc(${width}% - 2px);">
                                ${shootPrefix}
                                <span class="fc-phase-badge__icon">${clapperSvg}</span>
                                <span class="fc-phase-badge__title">${shootTitle}</span>
                                ${production ? `<span class="fc-phase-badge__prod">${escapeHtml(production)}</span>` : ''}
                                ${shootSuffix}
                            </span>
                        `;
                    }
                } else if (!shootStart && !depDate && !retDate) {
                    // Projet sans dates spécifiques : occupe la cellule entière
                    badgesHtml += `
                        <span class="fc-phase-badge fc-phase-badge--project" style="left:0; width:100%;">
                            <span class="fc-phase-badge__icon">${clapperSvg}</span>
                            <span class="fc-phase-badge__title">${escapeHtml(projectName)}</span>
                        </span>
                    `;
                }

                // 2.bis. INTERVALLES INTER-DATES IMMOBILISÉS (🔒 Immobilisé sur place)
                const lockSvg = '<svg class="fc-phase-icon fc-phase-icon--immob" xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>';

                if (props.dateMode === 'punctual' && Array.isArray(props.intervals) && props.intervals.length > 0) {
                    props.intervals.forEach((inter) => {
                        // On n'affiche que les intervalles immobilisés (le relâchement étant la norme par défaut, on évite de surcharger)
                        if (!inter.is_immobilized || !Array.isArray(inter.days) || inter.days.length === 0) return;

                        // Regrouper les jours de cet intervalle consécutifs dans la tranche affichée segDates
                        const chunks = [];
                        let curChunk = [];

                        segDates.forEach((segD, colIdx) => {
                            if (inter.days.includes(segD)) {
                                curChunk.push({ colIdx: colIdx, date: segD });
                            } else {
                                if (curChunk.length > 0) {
                                    chunks.push([...curChunk]);
                                    curChunk = [];
                                }
                            }
                        });
                        if (curChunk.length > 0) {
                            chunks.push(curChunk);
                        }

                        chunks.forEach((chunk) => {
                            const startCol = chunk[0].colIdx;
                            const count = chunk.length;
                            const left = (startCol / totalCols) * 100;
                            const width = (count / totalCols) * 100;

                            const startDateFr = formatDateFr(chunk[0].date);
                            const endDateFr = formatDateFr(chunk[count - 1].date);
                            const rangeLabel = (count > 1) ? `du ${startDateFr} au ${endDateFr}` : `le ${startDateFr}`;

                            const interTitle = `Immobilisé sur place : ${rangeLabel}`;
                            const interLabel = `Immobilisé${count > 1 ? ` (${count}j)` : ''}`;

                            badgesHtml += `
                                <span class="fc-phase-badge fc-phase-badge--interval fc-phase-badge--interval-immob"
                                      style="left: calc(${left}% + 1px); width: calc(${width}% - 2px);"
                                      title="${escapeHtml(interTitle)}">
                                    <span class="fc-phase-badge__icon">${lockSvg}</span>
                                    <span class="fc-phase-badge__label">${escapeHtml(interLabel)}</span>
                                </span>
                            `;
                        });
                    });
                }

                // 3. JALON RETOUR (Bleu)
                if (retDate) {
                    const retIdx = segDates.indexOf(retDate);
                    const retCoincides = (props.dateMode === 'punctual' && Array.isArray(props.shootDates))
                        ? props.shootDates.includes(retDate)
                        : (retDate === shootEnd);
                    if (retIdx !== -1 && !retCoincides) {
                        const left = (retIdx / totalCols) * 100;
                        const width = (1 / totalCols) * 100;
                        badgesHtml += `
                            <span class="fc-phase-badge fc-phase-badge--checkin"
                                  style="left: calc(${left}% + 1px); width: calc(${width}% - 2px);"
                                  title="Retour : ${escapeHtml(retDate)}">
                                ${checkinSvg}
                                <span class="fc-phase-badge__label">Retour</span>
                            </span>
                        `;
                    }
                }

                badgesContainer.innerHTML = badgesHtml;
            },
            eventClick: function (info) {
                if (info.event.url) {
                    info.jsEvent.preventDefault();
                    window.location.href = info.event.url;
                }
            },
            height: 'auto',
            contentHeight: 650
        });

        calendar.render();

        // ── Gestion des filtres interactifs par type d'événement ──
        const filterBtns = document.querySelectorAll('#calendarFilters .calendar-filter-btn');
        if (filterBtns.length > 0) {
            filterBtns.forEach(btn => {
                btn.addEventListener('click', function () {
                    const filter = this.dataset.filter || 'all';
                    calendarEl.dataset.filter = filter;

                    filterBtns.forEach(b => {
                        b.classList.remove('active', 'admin-btn-primary');
                        b.classList.add('admin-btn-quaternary');
                    });
                    this.classList.add('active', 'admin-btn-primary');
                    this.classList.remove('admin-btn-quaternary');
                });
            });
        }
    }
}

window.initCalendarQrModal = initCalendarQrModal;
window.initCalendar = initCalendar;
;

/* ── js/src/admin/project.js ── */
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

    document.addEventListener('click', (e) => {
        // Bouton Modifier
        const editBtn = e.target.closest('[data-action="edit-report"]');
        if (editBtn) {
            const reportId = editBtn.getAttribute('data-report-id');
            const viewEl = document.getElementById(`reportView-${reportId}`);
            const editEl = document.getElementById(`reportEdit-${reportId}`);
            if (viewEl && editEl) {
                viewEl.classList.add('is-hidden');
                editEl.classList.remove('is-hidden');
                const textarea = editEl.querySelector('textarea');
                if (textarea) {
                    textarea.focus();
                    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
                }
            }
            return;
        }

        // Bouton Annuler
        const cancelBtn = e.target.closest('[data-action="cancel-edit"]');
        if (cancelBtn) {
            const reportId = cancelBtn.getAttribute('data-report-id');
            const viewEl = document.getElementById(`reportView-${reportId}`);
            const editEl = document.getElementById(`reportEdit-${reportId}`);
            if (viewEl && editEl) {
                editEl.classList.add('is-hidden');
                viewEl.classList.remove('is-hidden');
            }
            return;
        }
    });

    // Raccourci Escape pour annuler l'édition en cours
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const activeEditForm = document.querySelector('.project-report-edit-form:not(.is-hidden)');
            if (activeEditForm) {
                const reportId = activeEditForm.id.replace('reportEdit-', '');
                const viewEl = document.getElementById(`reportView-${reportId}`);
                if (viewEl) {
                    activeEditForm.classList.add('is-hidden');
                    viewEl.classList.remove('is-hidden');
                }
            }
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
                        <div class="empty-state">
                            <div class="empty-state-icon">
                                <i data-lucide="clipboard-pen"></i>
                            </div>
                            <div class="empty-state-title">Aucune note n'a encore été enregistrée</div>
                            <div class="empty-state-desc">Ajoutez les consignes spécifiques de ce tournage.</div>
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

function initProjectInteractions() {
    initProjectFormHighlight();
    initProjectDateValidation();
    initVehiclesModal();
    initProjectNotionSlashEditor();
    initProjectReportsCollapsible();
    initProjectReportsEdit();
    initProjectNotesEdit();
}

window.initProjectInteractions = initProjectInteractions;
;

/* ── js/src/admin/cmdk.js ── */
/**
 * cmdk.js — Palette de commande rapide (Cmd + K / Ctrl + K).
 */

let _cmdkCurrentResults = [];
let _cmdkSelectedIndex = 0;
let _cmdkDebounceTimer = null;

function _cmdkEscapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function _cmdkGetIconSvg(icon) {
    switch (icon) {
        case 'folder':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>';
        case 'building':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect><line x1="9" y1="22" x2="9" y2="18"></line><line x1="15" y1="22" x2="15" y2="18"></line><line x1="9" y1="6" x2="9.01" y2="6"></line><line x1="15" y1="6" x2="15.01" y2="6"></line><line x1="9" y1="10" x2="9.01" y2="10"></line><line x1="15" y1="10" x2="15.01" y2="10"></line><line x1="9" y1="14" x2="9.01" y2="14"></line><line x1="15" y1="14" x2="15.01" y2="14"></line></svg>';
        case 'truck':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>';
        case 'calendar':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>';
        case 'user':
        case 'users':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
        case 'plus':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>';
        case 'mail':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>';
        case 'archive':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line></svg>';
        case 'clipboard':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path><rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect></svg>';
        case 'tag':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>';
        case 'settings':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>';
        case 'alert':
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>';
        default:
            return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';
    }
}

function openCmdK() {
    const overlay = document.getElementById('cmdkOverlay');
    const input = document.getElementById('cmdkInput');
    if (!overlay || !input) return;
    overlay.classList.add('active');
    overlay.setAttribute('aria-hidden', 'false');
    input.value = '';
    _cmdkCurrentResults = [];
    _cmdkSelectedIndex = 0;
    fetchCmdKResults('');
    setTimeout(() => input.focus(), 50);
}

function closeCmdK() {
    const overlay = document.getElementById('cmdkOverlay');
    const input = document.getElementById('cmdkInput');
    if (!overlay) return;
    overlay.classList.remove('active');
    overlay.setAttribute('aria-hidden', 'true');
    if (input) input.blur();
}

window.openCmdK = openCmdK;
window.closeCmdK = closeCmdK;

function fetchCmdKResults(q) {
    const resultsContainer = document.getElementById('cmdkResults');
    if (!resultsContainer) return;
    const url = `/admin/api/search?q=${encodeURIComponent(q)}`;
    fetch(url)
        .then(res => res.json())
        .then(data => {
            _cmdkCurrentResults = data.results || [];
            _cmdkSelectedIndex = 0;
            renderCmdKResults();
        })
        .catch(err => {
            console.error('Erreur recherche Cmd+K:', err);
        });
}

function renderCmdKResults() {
    const resultsContainer = document.getElementById('cmdkResults');
    if (!resultsContainer) return;

    if (_cmdkCurrentResults.length === 0) {
        resultsContainer.innerHTML = '<div class="admin-cmdk-empty">Aucun résultat trouvé.</div>';
        return;
    }

    resultsContainer.innerHTML = _cmdkCurrentResults.map((item, idx) => {
        const badgeClass = `admin-cmdk-badge-${(item.category || '').toLowerCase()}`;
        return `
            <a href="${item.url}" class="admin-cmdk-item ${idx === _cmdkSelectedIndex ? 'selected' : ''}" data-index="${idx}">
                <div class="admin-cmdk-item-left">
                    <div class="admin-cmdk-item-icon">
                        ${_cmdkGetIconSvg(item.icon)}
                    </div>
                    <div class="admin-cmdk-item-text">
                        <span class="admin-cmdk-item-title">${_cmdkEscapeHtml(item.title)}</span>
                        <span class="admin-cmdk-item-sub">${_cmdkEscapeHtml(item.subtitle)}</span>
                    </div>
                </div>
                <span class="admin-cmdk-badge ${badgeClass}">${_cmdkEscapeHtml(item.category)}</span>
            </a>
        `;
    }).join('');

    resultsContainer.querySelectorAll('.admin-cmdk-item').forEach(el => {
        el.addEventListener('mouseenter', () => {
            _cmdkSelectedIndex = parseInt(el.dataset.index, 10);
            updateCmdKSelection();
        });
    });
}

function updateCmdKSelection() {
    const resultsContainer = document.getElementById('cmdkResults');
    if (!resultsContainer) return;
    const items = resultsContainer.querySelectorAll('.admin-cmdk-item');
    items.forEach((item, idx) => {
        if (idx === _cmdkSelectedIndex) {
            item.classList.add('selected');
            item.scrollIntoView({ block: 'nearest' });
        } else {
            item.classList.remove('selected');
        }
    });
}

function initCmdK() {
    const overlay = document.getElementById('cmdkOverlay');
    const input = document.getElementById('cmdkInput');
    const trigger = document.getElementById('cmdkTrigger');
    const closeBtn = document.getElementById('cmdkCloseBtn');

    if (!overlay || !input) return;

    if (trigger && !trigger._cmdkBound) {
        trigger._cmdkBound = true;
        trigger.addEventListener('click', (e) => {
            e.preventDefault();
            openCmdK();
        });
    }

    if (closeBtn && !closeBtn._cmdkBound) {
        closeBtn._cmdkBound = true;
        closeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            closeCmdK();
        });
    }

    if (!overlay._cmdkBound) {
        overlay._cmdkBound = true;
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeCmdK();
        });
    }

    if (!input._cmdkBound) {
        input._cmdkBound = true;
        input.addEventListener('input', () => {
            clearTimeout(_cmdkDebounceTimer);
            _cmdkDebounceTimer = setTimeout(() => {
                const query = input.value.trim();
                fetchCmdKResults(query);
            }, 150);
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (_cmdkCurrentResults.length > 0) {
                    _cmdkSelectedIndex = (_cmdkSelectedIndex + 1) % _cmdkCurrentResults.length;
                    updateCmdKSelection();
                }
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (_cmdkCurrentResults.length > 0) {
                    _cmdkSelectedIndex = (_cmdkSelectedIndex - 1 + _cmdkCurrentResults.length) % _cmdkCurrentResults.length;
                    updateCmdKSelection();
                }
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (_cmdkCurrentResults.length > 0 && _cmdkCurrentResults[_cmdkSelectedIndex]) {
                    window.location.href = _cmdkCurrentResults[_cmdkSelectedIndex].url;
                }
            }
        });
    }
}

// Raccourci clavier global Cmd+K / Ctrl+K et Escape
if (!window._cmdkKeydownAttached) {
    window._cmdkKeydownAttached = true;
    document.addEventListener('keydown', (e) => {
        const isK = (e.key && e.key.toLowerCase() === 'k') || e.code === 'KeyK';
        if ((e.metaKey || e.ctrlKey) && isK) {
            e.preventDefault();
            const o = document.getElementById('cmdkOverlay');
            if (o && o.classList.contains('active')) {
                closeCmdK();
            } else {
                openCmdK();
            }
        } else if (e.key === 'Escape') {
            const o = document.getElementById('cmdkOverlay');
            if (o && o.classList.contains('active')) {
                e.preventDefault();
                closeCmdK();
            }
        }
    });
}

window.initCmdK = initCmdK;
;

/* ── js/src/admin/inspections.js ── */
/**
 * inspections.js — Contrôleur des formulaires de départ et retour (Check-in & Check-out).
 */

// Registre des annotations et photos pour les contrôles (Check-in & Check-out)
const inspectionPhotoRegistry = window.inspectionPhotoRegistry || {};
window.inspectionPhotoRegistry = inspectionPhotoRegistry;

function updatePhotoLabel(input) {
    const preview = document.querySelector(`.photo-preview[data-for="${input.name}"]`);
    if (!preview) return;
    preview.innerHTML = '';

    // Initialise le registre pour ce champ
    inspectionPhotoRegistry[input.name] = [];

    if (input.files && input.files.length > 0) {
        Array.from(input.files).forEach((file, index) => {
            const photoState = {
                originalFile: file,
                currentFile: file,
                baseImage: file,
                dataUrl: null,
                annotations: [],
                isAnnotated: false
            };
            inspectionPhotoRegistry[input.name][index] = photoState;

            const reader = new FileReader();
            reader.onload = function (e) {
                photoState.dataUrl = e.target.result;

                const wrapper = document.createElement('div');
                wrapper.className = 'photo-preview-item';
                wrapper.title = "Cliquer pour visualiser ou annoter cette photo";

                const img = document.createElement('img');
                img.src = e.target.result;
                img.className = 'photo-preview-img';
                wrapper.appendChild(img);

                // Champ caché pour transmettre les données annotées fiables en base64 au backend
                const hiddenInput = document.createElement('input');
                hiddenInput.type = 'hidden';
                hiddenInput.name = `${input.name}_annotated_${index}`;
                hiddenInput.value = '';
                wrapper.appendChild(hiddenInput);

                let btn = null;
                if (typeof window.openPhotoAnnotator === 'function') {
                    btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'annotator-edit-badge';
                    btn.title = "Annoter cette photo (cercle, flèche, texte)";
                    btn.innerHTML = '<i data-lucide="pencil"></i> Annoter';
                    wrapper.appendChild(btn);
                }

                function openAnnotatorForThisPhoto(ev) {
                    if (ev) {
                        ev.preventDefault();
                        ev.stopPropagation();
                    }
                    if (typeof window.openPhotoAnnotator !== 'function') return;

                    window.openPhotoAnnotator(
                        photoState.currentFile,
                        function (annotatedFile, dataUrl, annotations) {
                            photoState.currentFile = annotatedFile;
                            photoState.dataUrl = dataUrl;
                            photoState.annotations = annotations || [];
                            photoState.isAnnotated = true;

                            img.src = dataUrl;
                            hiddenInput.value = dataUrl;

                            if (btn) {
                                btn.classList.add('is-annotated');
                                btn.innerHTML = '<i data-lucide="check"></i> Annotée';
                                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                                    window.lucide.createIcons();
                                }
                            }

                            if (typeof window.replaceFileInInput === 'function') {
                                window.replaceFileInInput(input, index, annotatedFile);
                            }
                        },
                        {
                            annotations: photoState.annotations,
                            baseImage: photoState.baseImage
                        }
                    );
                }

                if (btn) {
                    btn.onclick = openAnnotatorForThisPhoto;
                }
                wrapper.onclick = openAnnotatorForThisPhoto;

                preview.appendChild(wrapper);

                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
            };
            reader.readAsDataURL(file);
        });
    }
}
window.updatePhotoLabel = updatePhotoLabel;

function initInspectionForm(checkpointsConfig) {
    const vehicleInput = document.querySelector('input[name="vehicle_id"]');
    const form = document.getElementById('inspectionForm');
    const submitBtn = form ? form.querySelector('button[type="submit"]') : null;

    function updateCheckpoints() {
        if (!vehicleInput) return;

        if (!vehicleInput.value) {
            // Masquer tous les points de contrôle si aucun véhicule sélectionné
            document.querySelectorAll('.checkpoint-field').forEach(fieldEl => {
                fieldEl.style.display = 'none';
            });
            document.querySelectorAll('.checkpoint-group').forEach(groupEl => {
                groupEl.style.display = 'none';
            });
            return;
        }

        // Déterminer la configuration des points de contrôle pour le véhicule sélectionné
        let configToUse = [];
        const vid = vehicleInput.value;
        if (vid && checkpointsConfig && checkpointsConfig[vid]) {
            configToUse = checkpointsConfig[vid];
        }

        // Afficher ou masquer chaque point de contrôle selon la configuration
        document.querySelectorAll('.checkpoint-field').forEach(fieldEl => {
            const key = fieldEl.dataset.key;
            const detailEl = fieldEl.querySelector('.checkpoint-detail');
            const configItem = configToUse.find(cp => cp.key === key);

            if (configItem) {
                fieldEl.style.display = '';
                if (detailEl && configItem.detail) {
                    detailEl.innerText = configItem.detail;
                }
            } else {
                fieldEl.style.display = 'none';
            }
        });

        // Masquer les groupes de points de contrôle devenus vides
        document.querySelectorAll('.checkpoint-group').forEach(groupEl => {
            const fields = groupEl.querySelectorAll('.checkpoint-field');
            let hasVisibleField = false;
            fields.forEach(f => {
                if (f.style.display !== 'none') hasVisibleField = true;
            });
            groupEl.style.display = hasVisibleField ? '' : 'none';
        });

        if (typeof window.initVehiclesModal === 'function') {
            window.initVehiclesModal();
        }
        if (typeof lucide !== 'undefined' && lucide.createIcons) {
            lucide.createIcons();
        }
    }

    // Écouter le changement de véhicule et initialiser l'affichage
    if (vehicleInput) {
        vehicleInput.addEventListener('change', updateCheckpoints);
        updateCheckpoints();
    }

    // Validation et soumission du formulaire
    if (form) {
        form.addEventListener('submit', (e) => {
            const pInput = form.querySelector('input[name="project_id"]');
            const vInput = form.querySelector('input[name="vehicle_id"]');
            const cInput = form.querySelector('input[name="controller_id"]');

            if (submitBtn && (submitBtn.disabled || submitBtn.classList.contains('is-disabled'))) {
                e.preventDefault();
                return false;
            }

            // Sécurité : interdire la soumission si un retour est déjà en cours ou validé
            const vOpt = document.querySelector(`#vehicleOptions .rich-select-option[data-id="${vInput?.value}"]`);
            if (vOpt && vOpt.hasAttribute('data-checkin-statuses') && pInput?.value) {
                try {
                    const checkinStatuses = JSON.parse(vOpt.dataset.checkinStatuses || '{}');
                    const existing = checkinStatuses[pInput.value];
                    if (existing) {
                        e.preventDefault();
                        const code = (typeof existing === 'object' && existing.code) ? existing.code : (typeof existing === 'object' && existing.id ? `BVCI-#${existing.id}` : '');
                        const msg = `Erreur lors de la création : un retour est déjà en cours (${code || 'BVCI'})`;
                        if (typeof window.showFlash === 'function') {
                            window.showFlash(msg, 'warning');
                        } else {
                            alert(msg);
                        }
                        return false;
                    }
                } catch (err) {
                    console.error("Erreur vérification checkinStatus:", err);
                }
            }

            if (pInput && !pInput.value) {
                e.preventDefault();
                if (typeof window.showFlash === 'function') {
                    window.showFlash("Veuillez sélectionner un projet avant d'enregistrer.", "warning");
                } else {
                    alert("Veuillez sélectionner un projet avant d'enregistrer.");
                }
                const pSelect = document.getElementById('projectSelect');
                if (pSelect) {
                    pSelect.classList.add('open');
                    pSelect.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    const pSearch = document.getElementById('projectSearch');
                    if (pSearch) setTimeout(() => pSearch.focus(), 100);
                }
                return false;
            }

            if (vInput && !vInput.value) {
                e.preventDefault();
                if (typeof window.showFlash === 'function') {
                    window.showFlash("Veuillez sélectionner le véhicule à contrôler.", "warning");
                } else {
                    alert("Veuillez sélectionner le véhicule à contrôler.");
                }
                const vSelect = document.getElementById('vehicleSelect');
                if (vSelect) {
                    vSelect.classList.add('open');
                    vSelect.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    const vSearch = document.getElementById('vehicleSearch');
                    if (vSearch) setTimeout(() => vSearch.focus(), 100);
                }
                return false;
            }

            if (cInput && !cInput.value) {
                e.preventDefault();
                if (typeof window.showFlash === 'function') {
                    window.showFlash("Veuillez désigner le responsable du contrôle.", "warning");
                } else {
                    alert("Veuillez désigner le responsable du contrôle.");
                }
                return false;
            }

            // Vérification si confirmation requise pour retour exceptionnel sans départ validé
            const forceAction = document.getElementById('forceCheckinAction');
            const forceCheckbox = document.getElementById('forceCheckinCheckbox');
            if (forceAction && !forceAction.classList.contains('u-d-none') && forceCheckbox && !forceCheckbox.checked) {
                e.preventDefault();
                if (typeof window.showFlash === 'function') {
                    window.showFlash("Veuillez cocher la case de confirmation pour enregistrer ce retour exceptionnel.", "warning");
                } else {
                    alert("Veuillez cocher la case de confirmation pour enregistrer ce retour exceptionnel.");
                }
                forceCheckbox.focus();
                return false;
            }

            // Désactivation différée pour bloquer la double soumission
            setTimeout(() => {
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.textContent = "Enregistrement en cours...";
                }
            }, 10);
        });
    }

    // Exécution initiale au chargement
    updateCheckpoints();
}

window.initInspectionForm = initInspectionForm;

function initInspectionDetail() {
    const sealBtn = document.getElementById('sealCheckoutBtn') || document.getElementById('sealCheckinBtn');
    const container = document.getElementById('inspectionDetailLayout') || document.querySelector('[data-inspection-type]');
    if (!sealBtn && !container) return;

    const recordId = (container && container.dataset.inspectionId) ? container.dataset.inspectionId : (sealBtn ? sealBtn.dataset.inspectionId : '');
    const inspectionType = (container && container.dataset.inspectionType) ? container.dataset.inspectionType : (document.getElementById('sealCheckoutBtn') ? 'checkouts' : 'checkins');
    const currentStatusId = container ? (container.dataset.statusId || '') : (sealBtn ? (sealBtn.dataset.statusId || '') : '');
    const csrfToken = document.querySelector('input[name="csrf_token"]')?.value;

    if (sealBtn && recordId && !sealBtn.dataset.bound) {
        sealBtn.dataset.bound = 'true';
        sealBtn.addEventListener('click', function () {
            const label = inspectionType === 'checkouts' ? 'checkout' : 'checkin';
            if (!confirm(`Êtes-vous sûr de vouloir sceller ce ${label} ? Cette action est irréversible.`)) return;

            sealBtn.disabled = true;
            sealBtn.classList.add('btn-disabled');
            sealBtn.innerText = 'Scellage en cours...';

            fetch(`/admin/api/${inspectionType}/${recordId}/status`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify({ status: "pending" })
            })
                .then(r => r.json())
                .then(res => {
                    if (res.status_id === "pending") {
                        window.location.reload();
                    } else {
                        console.error("Erreur serveur lors de la mise à jour :", res);
                        sealBtn.disabled = false;
                        sealBtn.classList.remove('btn-disabled');
                        sealBtn.innerText = `Sceller ce ${label}`;
                        alert("Erreur: " + (res.error || "Mise à jour échouée."));
                    }
                })
                .catch(err => {
                    console.error("Error setting inspection status:", err);
                    sealBtn.disabled = false;
                    sealBtn.classList.remove('btn-disabled');
                    sealBtn.innerText = `Sceller ce ${label}`;
                    alert("Erreur de connexion lors de la mise à jour.");
                });
        });
    }

    // Polling si statut pending (idempotent)
    if (currentStatusId === "pending" && recordId && container && !container.dataset.pollingBound) {
        container.dataset.pollingBound = 'true';
        setInterval(() => {
            fetch(`/admin/api/${inspectionType}/${recordId}/status`)
                .then(r => r.json())
                .then(res => {
                    if (res.status_id && res.status_id !== currentStatusId) {
                        window.location.reload();
                    }
                })
                .catch(err => console.error("Error fetching inspection status:", err));
        }, 3000);
    }
}
window.initInspectionDetail = initInspectionDetail;
;

/* ── js/src/admin/photo-annotator.js ── */
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
;

/* ── js/src/admin/ios-bridge.js ── */
/**
 * ios-bridge.js — Passerelle de communication entre l'Admin Belle Vitesse et l'application iPadOS Native (Swift / WKWebView).
 */

(function () {
    'use strict';

    const hasWebKitBridge = !!(
        window.webkit &&
        window.webkit.messageHandlers &&
        window.webkit.messageHandlers.bvBridge
    );

    const iosBridge = {
        isNativeApp: hasWebKitBridge,

        /**
         * Envoie un message sécurisé au conteneur natif Swift.
         * @param {string} action - L'action à déclencher (ex: 'haptic', 'sessionState', 'openExternal')
         * @param {object} payload - Données associées
         */
        postMessage: function (action, payload) {
            if (!this.isNativeApp) return;
            try {
                window.webkit.messageHandlers.bvBridge.postMessage({
                    action: action,
                    payload: payload || {}
                });
            } catch (err) {
                console.warn('[BV iPad Bridge] Échec d’envoi de message :', err);
            }
        },

        /**
         * Déclenche un retour haptique sur l'iPad (si compatible).
         * @param {'light'|'medium'|'heavy'|'success'|'warning'|'error'|'selection'} type
         */
        triggerHaptic: function (type) {
            this.postMessage('haptic', { type: type || 'selection' });
        },

        /**
         * Notifie l'application native d'un état d'authentification ou d'une page chargée.
         */
        notifyReady: function () {
            this.postMessage('pageReady', {
                path: window.location.pathname,
                title: document.title
            });
        }
    };

    window.bvIpadBridge = iosBridge;

    // Déclencheurs haptiques automatiques sur les interactions réussies
    document.addEventListener('DOMContentLoaded', function () {
        if (iosBridge.isNativeApp) {
            document.documentElement.classList.add('is-bv-ipad-native');
            iosBridge.notifyReady();

            // Retours haptiques sur les messages Flash (succès / alerte)
            const successFlash = document.querySelector('.flash-success');
            if (successFlash) {
                iosBridge.triggerHaptic('success');
            }
            const errorFlash = document.querySelector('.flash-error, .flash-danger');
            if (errorFlash) {
                iosBridge.triggerHaptic('error');
            }
        }
    });
})();
;

/* ── js/src/admin/waiver-search.js ── */
/**
 * waiver-search.js — Recherche autocomplétée de projet pour les formulaires de décharge
 * Filtre les projets disponibles dès 2 caractères tapés avec navigation clavier et sélection enrichie.
 */
(function () {
    'use strict';

    function initWaiverSearch() {
        var dataScript = document.getElementById('projectsData');
        var hiddenInput = document.getElementById('selectedProjectId');
        var searchInput = document.getElementById('projectSearchInput');
        var clearBtn = document.getElementById('clearSearchBtn');
        var dropdown = document.getElementById('waiverDropdown');
        var resultsList = document.getElementById('waiverResultsList');
        var resultsCount = document.getElementById('resultsCount');
        var searchContainer = document.getElementById('waiverSearchContainer');
        var selectedCard = document.getElementById('waiverSelectedCard');
        var selectedName = document.getElementById('selectedProjectName');
        var selectedProd = document.getElementById('selectedProjectProd');
        var selectedDates = document.getElementById('selectedProjectDates');
        var selectedPilot = document.getElementById('selectedProjectPilot');
        var changeBtn = document.getElementById('changeProjectBtn');
        var submitBtn = document.getElementById('submitWaiverBtn');
        var helperText = document.getElementById('searchHelperText');

        if (!dataScript || !hiddenInput || !searchInput || !dropdown) {
            return;
        }

        var projects = [];
        try {
            projects = JSON.parse(dataScript.textContent || '[]');
        } catch (e) {
            console.error('Erreur de parsing des données projets:', e);
            return;
        }

        var highlightedIndex = -1;
        var currentFiltered = [];

        function normalizeStr(str) {
            return (str || '')
                .toString()
                .toLowerCase()
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '')
                .trim();
        }

        function escapeHtml(str) {
            var div = document.createElement('div');
            div.textContent = str || '';
            return div.innerHTML;
        }

        function selectProject(proj) {
            if (!proj) return;
            hiddenInput.value = proj.id;
            selectedName.textContent = proj.name;
            selectedProd.textContent = proj.production || 'Sans production';

            var datesSpan = selectedDates.querySelector('span');
            if (datesSpan) {
                datesSpan.textContent = proj.dates || 'Dates non définies';
            }

            if (selectedPilot) {
                var person = proj.pilot || proj.contact;
                if (person) {
                    var personSpan = selectedPilot.querySelector('span');
                    if (personSpan) personSpan.textContent = person;
                    selectedPilot.classList.remove('u-d-none');
                } else {
                    selectedPilot.classList.add('u-d-none');
                }
            }

            searchContainer.classList.add('u-d-none');
            selectedCard.classList.remove('u-d-none');
            dropdown.classList.add('u-d-none');

            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.classList.remove('is-disabled');
            }

            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }

        function unselectProject() {
            hiddenInput.value = '';
            selectedCard.classList.add('u-d-none');
            searchContainer.classList.remove('u-d-none');

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.classList.add('is-disabled');
            }

            searchInput.value = '';
            clearBtn.classList.add('u-d-none');
            dropdown.classList.add('u-d-none');
            highlightedIndex = -1;
            currentFiltered = [];

            if (helperText) {
                helperText.classList.remove('u-d-none');
            }

            setTimeout(function () {
                searchInput.focus();
            }, 50);
        }

        function renderDropdown(items, query) {
            resultsList.innerHTML = '';
            currentFiltered = items;
            highlightedIndex = -1;

            if (items.length === 0) {
                var emptyDiv = document.createElement('div');
                emptyDiv.className = 'waiver-results-empty';
                emptyDiv.innerHTML = 'Aucun projet trouvé pour « <strong>' + escapeHtml(query) + '</strong> »';
                resultsList.appendChild(emptyDiv);
                if (resultsCount) resultsCount.textContent = '0';
            } else {
                if (resultsCount) resultsCount.textContent = items.length.toString();

                items.forEach(function (proj, idx) {
                    var itemEl = document.createElement('div');
                    itemEl.className = 'waiver-search-item';
                    itemEl.dataset.id = proj.id;
                    itemEl.dataset.index = idx;
                    itemEl.setAttribute('role', 'option');

                    var personInfo = proj.pilot || proj.contact;
                    var personHtml = personInfo ? '<span class="waiver-item-meta-entry"><i data-lucide="user"></i> ' + escapeHtml(personInfo) + '</span>' : '';

                    itemEl.innerHTML =
                        '<div class="waiver-item-top">' +
                            '<span class="waiver-item-name">' + escapeHtml(proj.name) + '</span>' +
                            '<span class="badge-pill u-text-xs" data-val="neutral">' + escapeHtml(proj.production) + '</span>' +
                        '</div>' +
                        '<div class="waiver-item-meta">' +
                            '<span class="waiver-item-meta-entry">' +
                                '<i data-lucide="calendar"></i> ' + escapeHtml(proj.dates) +
                            '</span>' +
                            personHtml +
                        '</div>';

                    itemEl.addEventListener('click', function () {
                        selectProject(proj);
                    });

                    resultsList.appendChild(itemEl);
                });
            }

            dropdown.classList.remove('u-d-none');

            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }

        function updateHighlight() {
            var itemEls = resultsList.querySelectorAll('.waiver-search-item');
            itemEls.forEach(function (el, idx) {
                if (idx === highlightedIndex) {
                    el.classList.add('is-highlighted');
                    el.scrollIntoView({ block: 'nearest' });
                } else {
                    el.classList.remove('is-highlighted');
                }
            });
        }

        // Événement de saisie dans le champ de recherche
        searchInput.addEventListener('input', function () {
            var rawVal = searchInput.value;
            var q = normalizeStr(rawVal);

            clearBtn.classList.toggle('u-d-none', rawVal.length === 0);

            // Commence la recherche uniquement à partir de 2 caractères
            if (q.length < 2) {
                dropdown.classList.add('u-d-none');
                currentFiltered = [];
                highlightedIndex = -1;
                if (helperText) helperText.classList.remove('u-d-none');
                return;
            }

            if (helperText) helperText.classList.add('u-d-none');

            var filtered = projects.filter(function (p) {
                var searchTarget = normalizeStr(p.search || (p.name + ' ' + p.production + ' ' + (p.pilot || p.contact || '') + ' ' + p.dates));
                return searchTarget.includes(q);
            });

            renderDropdown(filtered, rawVal);
        });

        // Bouton d'effacement de la recherche
        clearBtn.addEventListener('click', function () {
            searchInput.value = '';
            clearBtn.classList.add('u-d-none');
            dropdown.classList.add('u-d-none');
            currentFiltered = [];
            highlightedIndex = -1;
            if (helperText) helperText.classList.remove('u-d-none');
            searchInput.focus();
        });

        // Navigation clavier (Flèches Haut/Bas, Entrée, Échap)
        searchInput.addEventListener('keydown', function (e) {
            if (dropdown.classList.contains('u-d-none') || currentFiltered.length === 0) {
                if (e.key === 'Escape') {
                    dropdown.classList.add('u-d-none');
                }
                return;
            }

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                highlightedIndex = (highlightedIndex + 1) % currentFiltered.length;
                updateHighlight();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                highlightedIndex = (highlightedIndex - 1 + currentFiltered.length) % currentFiltered.length;
                updateHighlight();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (highlightedIndex >= 0 && highlightedIndex < currentFiltered.length) {
                    selectProject(currentFiltered[highlightedIndex]);
                } else if (currentFiltered.length === 1) {
                    selectProject(currentFiltered[0]);
                }
            } else if (e.key === 'Escape') {
                dropdown.classList.add('u-d-none');
            }
        });

        // Fermeture du dropdown lors d'un clic en dehors
        document.addEventListener('click', function (e) {
            if (!searchContainer.contains(e.target)) {
                dropdown.classList.add('u-d-none');
            }
        });

        // Bouton Changer de projet
        if (changeBtn) {
            changeBtn.addEventListener('click', function () {
                unselectProject();
            });
        }

        // Pré-sélection au chargement si project_id est fourni (ex: ?project_id=123)
        var initialId = hiddenInput.value;
        if (initialId) {
            var initialProj = projects.find(function (p) {
                return p.id.toString() === initialId.toString();
            });
            if (initialProj) {
                selectProject(initialProj);
            }
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWaiverSearch);
    } else {
        initWaiverSearch();
    }
})();
;

/* ── js/src/admin/incident-form.js ── */
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

    const incidentPhotoRegistry = {};

    function previewFiles(input, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';
        incidentPhotoRegistry[input.name || containerId] = [];

        if (input.files) {
            Array.from(input.files).forEach((file, index) => {
                if (file.type.startsWith('image/')) {
                    const photoState = {
                        originalFile: file,
                        currentFile: file,
                        baseImage: file,
                        dataUrl: null,
                        annotations: [],
                        isAnnotated: false
                    };
                    incidentPhotoRegistry[input.name || containerId][index] = photoState;

                    const reader = new FileReader();
                    reader.onload = function (e) {
                        photoState.dataUrl = e.target.result;

                        const wrapper = document.createElement('div');
                        wrapper.className = 'photo-preview-item';
                        wrapper.title = "Cliquer pour visualiser ou annoter cette photo";

                        const img = document.createElement('img');
                        img.src = e.target.result;
                        img.className = 'photo-preview-img';
                        wrapper.appendChild(img);

                        const hiddenInput = document.createElement('input');
                        hiddenInput.type = 'hidden';
                        hiddenInput.name = `${input.name || 'photos'}_annotated_${index}`;
                        hiddenInput.value = '';
                        wrapper.appendChild(hiddenInput);

                        let btn = null;
                        if (typeof window.openPhotoAnnotator === 'function') {
                            btn = document.createElement('button');
                            btn.type = 'button';
                            btn.className = 'annotator-edit-badge';
                            btn.title = "Annoter cette photo (cercle, flèche, texte)";
                            btn.innerHTML = '<i data-lucide="pencil"></i> Annoter';
                            wrapper.appendChild(btn);
                        }

                        function openAnnotatorForPhoto(ev) {
                            if (ev) {
                                ev.preventDefault();
                                ev.stopPropagation();
                            }
                            if (typeof window.openPhotoAnnotator !== 'function') return;

                            window.openPhotoAnnotator(
                                photoState.currentFile,
                                function (annotatedFile, dataUrl, annotations) {
                                    photoState.currentFile = annotatedFile;
                                    photoState.dataUrl = dataUrl;
                                    photoState.annotations = annotations || [];
                                    photoState.isAnnotated = true;

                                    img.src = dataUrl;
                                    hiddenInput.value = dataUrl;

                                    if (btn) {
                                        btn.classList.add('is-annotated');
                                        btn.innerHTML = '<i data-lucide="check"></i> Annotée';
                                        if (window.lucide && typeof window.lucide.createIcons === 'function') {
                                            window.lucide.createIcons();
                                        }
                                    }

                                    if (typeof window.replaceFileInInput === 'function') {
                                        window.replaceFileInInput(input, index, annotatedFile);
                                    }
                                },
                                {
                                    annotations: photoState.annotations,
                                    baseImage: photoState.baseImage
                                }
                            );
                        }

                        if (btn) {
                            btn.onclick = openAnnotatorForPhoto;
                        }
                        wrapper.onclick = openAnnotatorForPhoto;

                        container.appendChild(wrapper);

                        if (window.lucide && typeof window.lucide.createIcons === 'function') {
                            window.lucide.createIcons();
                        }
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
;

/* ── js/src/admin/incident-detail.js ── */
/**
 * incident-detail.js — Contrôleur de la vue détaillée d'incident.
 * Gère :
 * - Les modales de signature électronique (BV et Production)
 * - Les canvas manuscrits BelleVitesseSignaturePad
 * - Le changement rapide de statut (résolution / clôture / transition directe)
 * - Les raccourcis clavier et fermeture des overlays
 */

(function () {
    const pads = {};

    function getOrCreatePad(canvasId, clearBtnId) {
        if (pads[canvasId]) return pads[canvasId];
        if (typeof window.BelleVitesseSignaturePad !== 'function') {
            console.warn("BelleVitesseSignaturePad non disponible.");
            return null;
        }
        const padObj = new window.BelleVitesseSignaturePad(canvasId, {
            clearBtnId: clearBtnId,
            padOptions: {
                backgroundColor: 'rgba(248, 250, 252, 0)',
                penColor: '#0f172a'
            }
        });
        pads[canvasId] = padObj;
        return padObj;
    }

    function openIncidentModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.add('is-open');

        if (modalId === 'modalBvSign') {
            const padObj = getOrCreatePad('bvCanvas', 'clearBvCanvas');
            setTimeout(() => padObj && padObj.resize(), 50);
        } else if (modalId === 'modalProdSign') {
            const padObj = getOrCreatePad('prodCanvas', 'clearProdCanvas');
            setTimeout(() => padObj && padObj.resize(), 50);
        }
    }
    window.openIncidentModal = openIncidentModal;

    function closeIncidentModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('is-open');
        }
    }
    window.closeIncidentModal = closeIncidentModal;

    function quickStatusChange(newStatus) {
        if (!newStatus) return;
        const detailView = document.getElementById('incidentDetailView');
        const statusUrl = detailView ? detailView.dataset.statusUrl : '';
        if (!statusUrl) {
            console.error("URL d'action de statut d'incident manquante (data-status-url).");
            return;
        }

        const csrfToken = detailView ? detailView.dataset.csrfToken : (document.querySelector('input[name="csrf_token"]')?.value || '');

        const form = document.createElement('form');
        form.method = 'POST';
        form.action = statusUrl;

        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrf_token';
        csrfInput.value = csrfToken;
        form.appendChild(csrfInput);

        const statusInput = document.createElement('input');
        statusInput.type = 'hidden';
        statusInput.name = 'status';
        statusInput.value = newStatus;
        form.appendChild(statusInput);

        document.body.appendChild(form);
        form.submit();
    }
    window.quickStatusChange = quickStatusChange;

    function quickStatusSelect(newStatus) {
        if (newStatus === 'resolu' || newStatus === 'cloture') {
            const select = document.getElementById('quickResolveStatusSelect');
            if (select) select.value = newStatus;
            openIncidentModal('modalQuickResolve');
        } else {
            quickStatusChange(newStatus);
        }
    }
    window.quickStatusSelect = quickStatusSelect;

    function bindSignatureForm(formId, canvasId, dataInputId, alertMsg, loadingText) {
        const form = document.getElementById(formId);
        if (!form) return;
        let isSubmitting = false;

        form.addEventListener('submit', function (e) {
            if (isSubmitting) {
                e.preventDefault();
                return false;
            }
            const padObj = pads[canvasId];
            if (!padObj || !padObj.pad || padObj.pad.isEmpty()) {
                e.preventDefault();
                alert(alertMsg);
                return false;
            }
            const input = document.getElementById(dataInputId);
            if (input) input.value = padObj.pad.toDataURL('image/png');
            isSubmitting = true;
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = loadingText;
            }
        });
    }

    function initIncidentDetail() {
        const detailView = document.getElementById('incidentDetailView');
        if (!detailView) return;

        // Fermeture des modales : clic overlay ou touche Échap
        document.querySelectorAll('.incident-modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', function (e) {
                if (e.target === this) closeIncidentModal(this.id);
            });
        });

        window.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                document.querySelectorAll('.incident-modal-overlay').forEach(m => closeIncidentModal(m.id));
            }
        });

        bindSignatureForm('formBvSign', 'bvCanvas', 'bvSignatureData', 'Veuillez apposer votre visa manuscrit avant de valider.', 'Enregistrement en cours...');
        bindSignatureForm('formProdSign', 'prodCanvas', 'prodSignatureData', 'Veuillez recueillir la signature manuscrite avant de valider.', 'Scellement en cours...');
    }
    window.initIncidentDetail = initIncidentDetail;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initIncidentDetail);
    } else {
        initIncidentDetail();
    }
})();
;

/* ── js/src/admin/project-form.js ── */
/**
 * project-form.js — Contrôleur dynamique du formulaire de création et édition de projet.
 * Gère :
 * - L'initialisation du DatePicker Timeline unifié (ProjectTimelineDatePicker)
 * - Les sélecteurs enrichis Select2 pour les productions et contacts
 * - Les modales AJAX d'ajout rapide (Production & Contacts)
 * - La validation front-end avant soumission
 * - La détection en temps réel des conflits de réservation matériels (véhicules / têtes)
 */

(function () {
    function initProjectForm() {
        if (typeof window.jQuery === 'undefined') return;
        const $ = window.jQuery;

        const $mainForm = $('#projectMainForm');
        const $pickerContainer = $('#projectDatePickerContainer');
        if (!$mainForm.length && !$pickerContainer.length) return;

        // 1. Initialisation du DatePicker Timeline unifié pour les projets
        if ($pickerContainer.length && typeof window.ProjectTimelineDatePicker === 'function') {
            new window.ProjectTimelineDatePicker({
                container: '#projectDatePickerContainer',
                inputDepartureId: 'departure_date_input',
                inputShootStartId: 'shoot_start_input',
                inputShootEndId: 'shoot_end_input',
                inputReturnId: 'return_date_input'
            });
        }

        // 2. Select2 pour les sélecteurs de production et contacts
        if ($.fn.select2) {
            $('.searchable-select').select2({
                width: '100%',
                placeholder: function () {
                    return $(this).data('placeholder') || '';
                }
            });
        }

        // 3. Bascule d'état visuel sur les cartes à cocher
        $('.project-checkbox-card input[type="checkbox"]').on('change', function () {
            $(this).closest('.project-checkbox-card').toggleClass('selected', this.checked);
        });

        // 4. Modale Production Rapide
        function openProductionModal() {
            $('#modalProdName').val('');
            $('#modalProdAddress').val('');
            $('#modalProdMail').val('');
            $('#modalProdPhone').val('');
            $('#quickProductionModal').css('display', 'flex');
            setTimeout(function () {
                $('#modalProdName').focus();
            }, 100);
        }

        function closeProductionModal() {
            $('#quickProductionModal').css('display', 'none');
        }

        $('#quickAddProductionBtn').on('click', function () {
            openProductionModal();
        });

        $('#closeProductionModalBtn, #cancelProductionModalBtn').on('click', function () {
            closeProductionModal();
        });

        $('#quickProductionModal').on('click', function (e) {
            if (e.target === this) {
                closeProductionModal();
            }
        });

        $('#quickProductionForm').on('submit', function (e) {
            e.preventDefault();

            const prodName = $('#modalProdName').val().trim();
            const prodAddress = $('#modalProdAddress').val().trim();
            const prodMail = $('#modalProdMail').val().trim();
            const prodPhone = $('#modalProdPhone').val().trim();

            if (!prodName) {
                alert("Le nom de la production est requis.");
                return;
            }

            const csrfToken = $('input[name="csrf_token"]').val();
            const $submitBtn = $('#submitProductionModalBtn');
            $submitBtn.prop('disabled', true).text('Création...');

            $.ajax({
                url: "/admin/api/productions/quick",
                type: "POST",
                contentType: "application/json",
                headers: {
                    "X-CSRFToken": csrfToken
                },
                data: JSON.stringify({
                    name: prodName,
                    address: prodAddress || null,
                    mail: prodMail || null,
                    phone: prodPhone || null
                }),
                success: function (response) {
                    $submitBtn.prop('disabled', false).text('Créer la production');
                    if (response && response.id) {
                        const $select = $('#productionSelect');
                        if ($select.find("option[value='" + response.id + "']").length === 0) {
                            const newOption = new Option(response.name, response.id, true, true);
                            $select.append(newOption);
                        } else {
                            $select.val(response.id);
                        }
                        $select.trigger('change');

                        // Mettre à jour aussi dans la modale de contact
                        const $modalProd = $('#modalContactProduction');
                        if ($modalProd.find("option[value='" + response.id + "']").length === 0) {
                            $modalProd.append(new Option(response.name, response.id));
                        }

                        closeProductionModal();
                    } else {
                        alert("Une erreur est survenue lors de la création de la production.");
                    }
                },
                error: function (xhr) {
                    $submitBtn.prop('disabled', false).text('Créer la production');
                    const errorMsg = xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : "Erreur serveur";
                    alert("Impossible de créer la production : " + errorMsg);
                }
            });
        });

        // 5. Modale Contact Rapide
        $('.quick-add-contact-btn').on('click', function () {
            const targetSelectName = $(this).data('target');
            const defaultJob = $(this).data('job') || '';

            $('#modalTargetSelect').val(targetSelectName);
            $('#modalContactFirstName').val('');
            $('#modalContactLastName').val('');
            $('#modalContactMail').val('');
            $('#modalContactPhone').val('');
            $('#modalContactProduction').val('');

            if (defaultJob) {
                $('#modalContactJob').val(defaultJob);
            } else {
                $('#modalContactJob').val('');
            }

            $('#quickContactModal').css('display', 'flex');
            setTimeout(function () {
                $('#modalContactFirstName').focus();
            }, 100);
        });

        function closeContactModal() {
            $('#quickContactModal').css('display', 'none');
        }

        $('#closeContactModalBtn, #cancelContactModalBtn').on('click', function () {
            closeContactModal();
        });

        $('#quickContactModal').on('click', function (e) {
            if (e.target === this) {
                closeContactModal();
            }
        });

        $(document).on('keydown', function (e) {
            if (e.key === 'Escape') {
                if ($('#quickProductionModal').is(':visible')) {
                    closeProductionModal();
                } else if ($('#quickContactModal').is(':visible')) {
                    closeContactModal();
                }
            }
        });

        $('#quickContactForm').on('submit', function (e) {
            e.preventDefault();

            const firstName = $('#modalContactFirstName').val().trim();
            const lastName = $('#modalContactLastName').val().trim();
            const jobTitle = $('#modalContactJob').val();
            const mail = $('#modalContactMail').val().trim();
            const phone = $('#modalContactPhone').val().trim();
            const productionId = $('#modalContactProduction').val();
            const targetSelectName = $('#modalTargetSelect').val();

            if (!firstName || !lastName) {
                alert("Le prénom et le nom sont requis.");
                return;
            }

            const csrfToken = $('input[name="csrf_token"]').val();
            const $submitBtn = $('#submitContactModalBtn');
            $submitBtn.prop('disabled', true).text('Création...');

            $.ajax({
                url: "/admin/api/contacts/quick",
                type: "POST",
                contentType: "application/json",
                headers: {
                    "X-CSRFToken": csrfToken
                },
                data: JSON.stringify({
                    first_name: firstName,
                    last_name: lastName,
                    job_title: jobTitle,
                    mail: mail,
                    phone: phone,
                    production_id: productionId || null
                }),
                success: function (response) {
                    $submitBtn.prop('disabled', false).text('Créer le contact');
                    if (response && response.id) {
                        const contactSelectNames = [
                            'production_contact_id',
                            'dop_contact_id',
                            'pilot_contact_id',
                            'first_ac_contact_id',
                            'key_grip_contact_id'
                        ];

                        contactSelectNames.forEach(function (name) {
                            const $sel = $('select[name="' + name + '"]');
                            if ($sel.length) {
                                const isTarget = (name === targetSelectName);
                                if ($sel.find("option[value='" + response.id + "']").length === 0) {
                                    const newOpt = new Option(response.name, response.id, isTarget, isTarget);
                                    $sel.append(newOpt);
                                }
                                if (isTarget) {
                                    $sel.val(response.id);
                                }
                                $sel.trigger('change');
                            }
                        });

                        closeContactModal();
                    } else {
                        alert("Une erreur est survenue lors de la création du contact.");
                    }
                },
                error: function (xhr) {
                    $submitBtn.prop('disabled', false).text('Créer le contact');
                    const errorMsg = xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : "Erreur serveur";
                    alert("Impossible de créer le contact : " + errorMsg);
                }
            });
        });

        // 6. Validation front-end de la production requise
        $('form:not(#quickContactForm):not(#quickProductionForm)').on('submit', function (e) {
            if (document.activeElement && document.activeElement.getAttribute('formaction') && document.activeElement.getAttribute('formaction').includes('/delete')) {
                return;
            }

            const productionSelect = $('#productionSelect');
            if (productionSelect.length && !productionSelect.val()) {
                e.preventDefault();
                alert('Veuillez sélectionner une production.');
                if (productionSelect.data('select2')) {
                    productionSelect.select2('open');
                } else {
                    productionSelect.focus();
                }
            }
        });

        // 7. Détection en temps réel des conflits de réservation
        let conflictCheckTimer = null;
        const currentProjectId = ($mainForm.length && $mainForm.data('projectId')) ? String($mainForm.data('projectId')) : ($('#current_project_id').val() || '');

        function checkBookingConflicts() {
            clearTimeout(conflictCheckTimer);
            conflictCheckTimer = setTimeout(function () {
                const startDate = $('#departure_date_input').val() || $('#shoot_start_input').val();
                const endDate = $('#return_date_input').val() || $('#shoot_end_input').val() || startDate;
                const dateMode = $('#date_mode_input').val() || 'continuous';
                const isImmobilized = $('#is_immobilized_between_input').val() !== 'false';
                const shootDates = $('#shoot_dates_input').val() || '[]';

                const selectedVehicles = [];
                $('input[name="vehicle_ids"]:checked').each(function () {
                    selectedVehicles.push($(this).val());
                });

                const selectedHeads = [];
                $('input[name="head_ids"]:checked').each(function () {
                    selectedHeads.push($(this).val());
                });

                if (!startDate || (selectedVehicles.length === 0 && selectedHeads.length === 0)) {
                    $('#bookingConflictsAlert').slideUp(200);
                    $('.project-checkbox-card').removeClass('has-conflict');
                    $('.conflict-placeholder').empty();
                    return;
                }

                let interShootStatuses = [];
                const interStatusesVal = $('#inter_shoot_statuses_input').val();
                if (interStatusesVal) {
                    try {
                        interShootStatuses = JSON.parse(interStatusesVal);
                    } catch (e) {}
                }

                const csrfToken = $('input[name="csrf_token"]').val();

                $.ajax({
                    url: "/admin/api/projects/check-conflicts",
                    type: "POST",
                    contentType: "application/json",
                    headers: {
                        "X-CSRFToken": csrfToken
                    },
                    data: JSON.stringify({
                        start_date: startDate,
                        end_date: endDate,
                        date_mode: dateMode,
                        is_immobilized_between: isImmobilized,
                        shoot_dates: shootDates,
                        inter_shoot_statuses: interShootStatuses,
                        vehicle_ids: selectedVehicles,
                        head_ids: selectedHeads,
                        project_id: currentProjectId || null
                    }),
                    success: function (res) {
                        if (!res || !res.data) return;
                        const data = res.data;

                        $('.project-checkbox-card').removeClass('has-conflict');
                        $('.conflict-placeholder').empty();

                        if (data.has_conflicts) {
                            $('#bookingConflictsSummary').text(
                                data.total_conflicts + " conflit(s) détecté(s) pour les dates sélectionnées :"
                            );

                            const $list = $('#bookingConflictsDetailsList').empty();
                            data.conflicts_list.forEach(function (c) {
                                const itemLabel = (c.item_type === 'vehicle' ? '🏎️ ' : '🎥 ') + c.item_name;
                                $list.append(
                                    $('<li>').html(
                                        '<strong>' + itemLabel + '</strong> déjà réservé sur <em>' + c.project_name + '</em> (' + c.production + '), ' + c.period_label
                                    )
                                );

                                const $card = $('.project-checkbox-card[data-item-id="' + c.item_id + '"]');
                                $card.addClass('has-conflict');
                                $card.find('.conflict-placeholder').html(
                                    '<span class="conflict-badge" title="Déjà réservé par ' + c.production + ' (' + c.period_label + ')">⚠️ ' + c.project_name + '</span>'
                                );
                            });

                            $('#bookingConflictsAlert').slideDown(250);
                        } else {
                            $('#bookingConflictsAlert').slideUp(200);
                        }
                    },
                    error: function (err) {
                        console.warn("Vérification des conflits indisponible :", err);
                    }
                });
            }, 300);
        }

        $('input[name="vehicle_ids"], input[name="head_ids"]').on('change', checkBookingConflicts);
        $('#departure_date_input, #shoot_start_input, #shoot_end_input, #return_date_input, #date_mode_input, #is_immobilized_between_input, #shoot_dates_input, #inter_shoot_statuses_input').on('change', checkBookingConflicts);

        // Observer les inputs cachés modifiés par ProjectTimelineDatePicker
        if (window.MutationObserver) {
            const dateObserver = new MutationObserver(checkBookingConflicts);
            [
                'departure_date_input',
                'shoot_start_input',
                'shoot_end_input',
                'return_date_input',
                'date_mode_input',
                'is_immobilized_between_input',
                'shoot_dates_input',
                'inter_shoot_statuses_input'
            ].forEach(function (id) {
                const el = document.getElementById(id);
                if (el) {
                    dateObserver.observe(el, { attributes: true, attributeFilter: ['value'] });
                }
            });
        }

        // Vérification initiale si on est en mode édition
        if (currentProjectId) {
            setTimeout(checkBookingConflicts, 400);
        }
    }
    window.initProjectForm = initProjectForm;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initProjectForm);
    } else {
        initProjectForm();
    }
})();
;

/* ── js/src/admin/checkpoints.js ── */
/**
 * checkpoints.js — Gestion interactive des points de contrôle (Checkpoints)
 * Administration Belle Vitesse.
 * - Formulaire de création/édition : activation/désactivation et vidage dynamique du champ unité
 * - Liste des points de contrôle : recherche, filtres par catégorie, modale de consignes spécifiques
 */

document.addEventListener('DOMContentLoaded', function () {
    initCheckpointForm();
    initCheckpointsList();
});

/**
 * Initialise le comportement dynamique du formulaire de point de contrôle.
 * Désactive et vide le champ unité si le type d'évaluation n'est pas "value" (Mesure / Valeur saisie).
 */
function initCheckpointForm() {
    const typeSelect = document.getElementById('checkpoint_type');
    const unitInput = document.getElementById('checkpoint_unit');
    const unitLabel = document.getElementById('checkpoint_unit_label');
    const unitHint = document.getElementById('checkpoint_unit_hint');

    if (!typeSelect || !unitInput) return;

    function updateUnitState() {
        const isValue = typeSelect.value === 'value';
        if (isValue) {
            unitInput.disabled = false;
            if (unitLabel) unitLabel.classList.remove('u-text-muted');
            if (unitHint) unitHint.textContent = 'Affichée à côté de la valeur saisie.';
        } else {
            unitInput.value = '';
            unitInput.disabled = true;
            if (unitLabel) unitLabel.classList.add('u-text-muted');
            if (unitHint) unitHint.textContent = 'Non applicable pour une évaluation par statut.';
        }
    }

    typeSelect.addEventListener('change', updateUnitState);
    updateUnitState();
}

/**
 * Initialise la recherche, les filtres et la modale de consigne sur la page de liste des checkpoints.
 */
function initCheckpointsList() {
    const tbody = document.getElementById('checkpointsTableBody');
    if (!tbody) return;

    const searchInput = document.getElementById('searchInput') || document.getElementById('checkpointSearch') || document.getElementById('checkpointSearchInput');
    const filterPills = document.querySelectorAll('#checkpoint-filter-pills .filter-pill, .category-filter-pill');
    const noResultsRow = document.getElementById('checkpoint-no-results') || document.getElementById('noResultsRow');
    const visibleCountEl = document.getElementById('checkpoint-visible-count') || document.getElementById('visibleCheckpointsCount');

    const rows = tbody.querySelectorAll('.checkpoint-row');
    let activeCategory = 'all';
    let searchQuery = '';

    function normalizeStr(str) {
        return (str || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .trim();
    }

    function filterRows() {
        let count = 0;
        const normQuery = normalizeStr(searchQuery);
        const normActiveCategory = normalizeStr(activeCategory);
        const visiblePerCategory = {};

        rows.forEach(function (row) {
            const cat = normalizeStr(row.getAttribute('data-category') || '');
            const searchData = normalizeStr(row.getAttribute('data-search') || '');

            const matchesCategory = (normActiveCategory === 'all' || cat === normActiveCategory);
            const matchesSearch = !normQuery || searchData.indexOf(normQuery) !== -1;
            const show = matchesCategory && matchesSearch;

            row.classList.toggle('u-d-none', !show);
            if (show) {
                count++;
                visiblePerCategory[cat] = (visiblePerCategory[cat] || 0) + 1;
            }
        });

        const catHeaders = tbody.querySelectorAll('.checkpoint-category-header');
        catHeaders.forEach(function (header) {
            const cat = normalizeStr(header.getAttribute('data-category') || '');
            const hasVisibleRows = (visiblePerCategory[cat] || 0) > 0;
            const matchesCategoryFilter = (normActiveCategory === 'all' || cat === normActiveCategory);
            const showHeader = hasVisibleRows && matchesCategoryFilter;
            header.classList.toggle('u-d-none', !showHeader);
            if (showHeader) {
                const countSpan = header.querySelector('.checkpoint-cat-count');
                if (countSpan) {
                    countSpan.textContent = visiblePerCategory[cat] || 0;
                }
            }
        });

        if (visibleCountEl) visibleCountEl.textContent = count;
        if (noResultsRow) noResultsRow.classList.toggle('u-d-none', count > 0);
    }

    if (searchInput) {
        searchInput.addEventListener('input', function (e) {
            searchQuery = e.target.value;
            filterRows();
        });
    }

    filterPills.forEach(function (btn) {
        btn.addEventListener('click', function () {
            filterPills.forEach(function (b) {
                b.classList.remove('active', 'admin-btn-primary');
                b.classList.add('admin-btn-quaternary');
            });
            btn.classList.add('active', 'admin-btn-primary');
            btn.classList.remove('admin-btn-quaternary');
            activeCategory = btn.getAttribute('data-category');
            filterRows();
        });
    });

    // ── Gestion de la Modale de Consigne Spécifique ──
    const modal = document.getElementById('checkpointIndicationModal');
    const modalVehicle = document.getElementById('modalVehicleName');
    const modalCheckpoint = document.getElementById('modalCheckpointLabel');
    const modalIndication = document.getElementById('modalIndicationText');
    const closeModalBtn = document.getElementById('closeIndicationModal');
    const closeModalFooterBtn = document.getElementById('closeIndicationModalBtn');

    function openModal(vehicle, checkpoint, indication) {
        if (!modal) return;
        if (modalVehicle) modalVehicle.textContent = '🏎️ ' + vehicle;
        if (modalCheckpoint) modalCheckpoint.textContent = checkpoint;
        if (modalIndication) modalIndication.textContent = indication;
        modal.classList.add('open');
        document.body.classList.add('u-overflow-hidden');
    }

    function closeModal() {
        if (!modal) return;
        modal.classList.remove('open');
        document.body.classList.remove('u-overflow-hidden');
    }

    document.addEventListener('click', function (e) {
        const trigger = e.target.closest('.checkpoint-spec-trigger');
        if (trigger) {
            e.preventDefault();
            e.stopPropagation();
            openModal(
                trigger.getAttribute('data-vehicle') || '',
                trigger.getAttribute('data-checkpoint') || '',
                trigger.getAttribute('data-indication') || ''
            );
            return;
        }

        if (e.target === modal || e.target === closeModalBtn || e.target === closeModalFooterBtn || e.target.closest('#closeIndicationModal')) {
            closeModal();
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal && modal.classList.contains('open')) {
            closeModal();
        }
    });
}
;

/* ── js/src/admin.js ── */
/**
 * admin.js — Orchestrateur central JavaScript pour l'administration Belle Vitesse.
 * Coordonne l'initialisation des modules spécialisés (navigation, flash, selects,
 * tables, graphiques, calendrier, formulaires projets & inspections, Cmd+K).
 *
 * Compatible Swup.js : init() est ré-exécuté après chaque transition de contenu.
 */

function init() {
    if (typeof window.initFlash === 'function') window.initFlash();
    if (typeof window.initSelects === 'function') window.initSelects();
    if (typeof window.initTables === 'function') window.initTables();
    if (typeof window.initDashboardCharts === 'function') window.initDashboardCharts();
    if (typeof window.initCalendar === 'function') window.initCalendar();
    if (typeof window.initProjectInteractions === 'function') window.initProjectInteractions();
    if (typeof window.initCmdK === 'function') window.initCmdK();
    if (typeof window.initIncidentForm === 'function') window.initIncidentForm();
    if (typeof window.initIncidentDetail === 'function') window.initIncidentDetail();
    if (typeof window.initProjectForm === 'function') window.initProjectForm();
    if (typeof window.initInspectionDetail === 'function') window.initInspectionDetail();
}

window.init = init;

// Déclenchement automatique au chargement du DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// Support Swup : réinitialisation après chaque remplacement de contenu
document.addEventListener('swup:contentReplaced', init);
;
