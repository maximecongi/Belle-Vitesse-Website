/**
 * admin.js — Centralised JavaScript for the admin panel.
 * Loaded once via admin_base.html; each feature auto-detects
 * its DOM elements and only runs when they are present.
 *
 * Compatible Swup.js : init() est rappelé après chaque navigation.
 * Les listeners sur `document` sont enregistrés une seule fois.
 */


// ─────────────────────────────────────────────
// Sidebar Nav Dropdowns (Local Storage Persistence)
// ─────────────────────────────────────────────

// Appliquer l'état sauvegardé dès que le script est lu (pour éviter le flash)
// Cette technique fonctionne pour Swup / render initial.
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
            // Pas de state stocké mais le HTML dit de l'ouvrir par défaut
            group.classList.add('open');
        }
    });
}
// Run immediately if DOM is there or wait for DOMContentLoaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', restoreNavState);
} else {
    restoreNavState();
}
// Swup support : refaire au case où tout le swup remplace l'aside 
document.addEventListener('swup:contentReplaced', restoreNavState);

document.addEventListener('click', e => {
    // Nav group trigger toggle
    const trigger = e.target.closest('.admin-nav-group-trigger');
    if (trigger) {
        const group = trigger.closest('.admin-nav-group');
        group.classList.toggle('open');

        const id = group.dataset.navGroup;
        if (id) {
            localStorage.setItem(`nav-group-${id}`, group.classList.contains('open') ? 'open' : 'closed');
        }
    }

    // Existing dropdown logic
    if (!e.target.closest('.badge-select') && !e.target.closest('.rich-select') && !e.target.closest('.admin-tooltip-container')) {
        document.querySelectorAll('.badge-select.open, .rich-select.open, .admin-tooltip-container.open')
            .forEach(s => s.classList.remove('open'));
    }

    // Tooltip toggle logic
    const tooltipTrigger = e.target.closest('.note-tooltip-trigger');
    if (tooltipTrigger) {
        const container = tooltipTrigger.closest('.admin-tooltip-container');
        const wasOpen = container.classList.contains('open');
        // Close all other tooltips first
        document.querySelectorAll('.admin-tooltip-container.open').forEach(c => c.classList.remove('open'));
        if (!wasOpen) {
            container.classList.add('open');
        }
    }
});

// Active nav link logic
function updateActiveNavLink() {
    const currentPath = window.location.pathname;
    let bestMatch = null;
    let maxLen = -1;

    const navItems = document.querySelectorAll('.admin-nav-item');
    navItems.forEach(link => {
        link.classList.remove('active');
        const href = link.getAttribute('href');
        if (!href || href === '#' || href === '') return;

        // Exact match is always priority
        if (href === currentPath) {
            bestMatch = link;
            maxLen = 999;
        } else if (currentPath.startsWith(href) && href !== '/admin/dashboard' && href !== '/admin') {
            // Prefix match: keep the longest one (e.g. /admin/projects/archives vs /admin/projects)
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

// Initial call
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', updateActiveNavLink);
} else {
    updateActiveNavLink();
}

// Swup support: update active link when content is replaced
document.addEventListener('swup:contentReplaced', updateActiveNavLink);
document.addEventListener('swup:transitionEnd', updateActiveNavLink);


// ─────────────────────────────────────────────
// init() — appelé à chaque chargement de page
// ─────────────────────────────────────────────

function init() {

    // ─────────────────────────────────────────────
    // 1. Flash messages management (admin_base)
    // ─────────────────────────────────────────────
    const flashes = document.querySelectorAll('.admin-flash-item');
    if (flashes.length) {
        setTimeout(() => {
            flashes.forEach(f => dismissFlash(f));
        }, 5000);
    }

    /**
     * Show a flash message (toast) dynamically.
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

        // Auto-dismiss after 5s
        setTimeout(() => {
            dismissFlash(flash);
        }, 5000);
    };

    function dismissFlash(f) {
        if (!f || !f.parentNode) return;
        f.style.opacity = '0';
        f.style.transform = 'translateX(100%)';
        f.style.transition = 'all 0.5s ease';
        setTimeout(() => f.remove(), 500);
    }


    // ─────────────────────────────────────────────
    // 2. Badge selects (checkout form — état / sécurité)
    // ─────────────────────────────────────────────
    document.querySelectorAll('.badge-select').forEach(sel => {
        const trigger = sel.querySelector('.badge-select-trigger');
        const input = sel.querySelector('input');
        const pill = trigger.querySelector('.badge-pill');

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
                pill.textContent = label;
                pill.dataset.val = val;
                sel.classList.remove('open');
            });
        });
    });


    // ─────────────────────────────────────────────
    // 3. Rich project select (checkout form)
    // ─────────────────────────────────────────────
    let updateVehicleOptions = null;
    const pSelect = document.getElementById('projectSelect');
    if (pSelect) {
        const pTrigger = document.getElementById('projectTrigger');
        const pInput = pSelect.querySelector('input[name="project_id"]');
        const pLabel = document.getElementById('projectLabel');
        const pSearch = document.getElementById('projectSearch');
        const pOptions = document.querySelectorAll('#projectOptions .rich-select-option');

        pTrigger.addEventListener('click', () => {
            document.querySelectorAll('.badge-select.open').forEach(s => s.classList.remove('open'));
            pSelect.classList.toggle('open');
            if (pSelect.classList.contains('open')) {
                pSearch.value = '';
                pOptions.forEach(o => o.style.display = '');
                setTimeout(() => pSearch.focus(), 50);
            }
        });

        pSearch.addEventListener('input', () => {
            const q = pSearch.value.toLowerCase();
            pOptions.forEach(opt => {
                const text = (opt.dataset.search || opt.dataset.name || '').toLowerCase();
                opt.style.display = text.includes(q) ? '' : 'none';
            });
        });

        updateVehicleOptions = (opt) => {
            if (!opt) return;

            // Enable vehicle select
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
                // Aucun projet sélectionné
                if (vOptions) vOptions.forEach(o => o.style.display = 'none');
                if (noVehNotice) noVehNotice.style.display = 'none';
                if (vInput && vInput.value) {
                    vInput.value = '';
                    if (vLabel) vLabel.textContent = '— Sélectionnez d\'abord un projet —';
                    vInput.dispatchEvent(new Event('change', { bubbles: true }));
                }
                return;
            }

            if (allowedVehicles.length === 0) {
                // Projet sans véhicule rattaché : masquer tous les véhicules et avertir
                if (vOptions) vOptions.forEach(o => o.style.display = 'none');
                if (noVehNotice) noVehNotice.style.display = 'block';
                if (vInput) {
                    vInput.value = '';
                    if (vLabel) vLabel.textContent = '— Aucun véhicule rattaché à ce projet —';
                    vInput.dispatchEvent(new Event('change', { bubbles: true }));
                }
                return;
            }

            if (noVehNotice) noVehNotice.style.display = 'none';

            // Afficher UNIQUEMENT les véhicules rattachés au projet, masquer strictement les autres
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
                        // Véhicule non rattaché au projet : masqué
                        vOpt.style.display = 'none';
                        return;
                    }

                    // Véhicule rattaché au projet : visible et sélectionnable
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
                pLabel.textContent = opt.dataset.name;
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


    // ─────────────────────────────────────────────
    // 3b. Rich vehicle select (checkout & checkin forms)
    // ─────────────────────────────────────────────
    const vSelect = document.getElementById('vehicleSelect');
    if (vSelect) {
        const vTrigger = document.getElementById('vehicleTrigger');
        const vInput = vSelect.querySelector('input[name="vehicle_id"]');
        const vLabel = document.getElementById('vehicleLabel');
        const vSearch = document.getElementById('vehicleSearch');
        const vOptions = document.querySelectorAll('#vehicleOptions .rich-select-option');

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
                if (thumb) {
                    vLabel.innerHTML = `<span style="display:flex;align-items:center;gap:0.5rem;">
                        <img src="${thumb}" style="width:28px;height:28px;border-radius:4px;object-fit:cover;">
                        ${opt.dataset.name}
                    </span>`;
                } else {
                    vLabel.textContent = opt.dataset.name;
                }
                vSelect.classList.remove('open');
                vInput.dispatchEvent(new Event('change', { bubbles: true }));
            });
        });
    }


    // ─────────────────────────────────────────────
    // 3c. Rich controller select (checkout form)
    // ─────────────────────────────────────────────
    const cSelect = document.getElementById('controllerSelect');
    if (cSelect) {
        const cTrigger = document.getElementById('controllerTrigger');
        const cInput = cSelect.querySelector('input[name="controller_id"]');
        const cLabel = document.getElementById('controllerLabel');
        const cOptions = document.querySelectorAll('#controllerOptions .rich-select-option');

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
                cLabel.textContent = opt.dataset.name;
                cSelect.classList.remove('open');
            });
        });
    }


    // ─────────────────────────────────────────────
    // 4. Checkouts list — search filter
    // ─────────────────────────────────────────────
    const checkoutSearchInput = document.getElementById('search-input');
    if (checkoutSearchInput) {
        const tbody = document.getElementById('checkouts-tbody') || document.getElementById('checkins-tbody');
        const rows = tbody.querySelectorAll('tr[data-search]');
        const resultCount = document.getElementById('result-count');
        const noResults = document.getElementById('no-results');

        checkoutSearchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            let visibleCount = 0;

            rows.forEach(row => {
                const searchText = row.getAttribute('data-search');
                if (searchText.includes(query)) {
                    row.style.display = '';
                    visibleCount++;
                } else {
                    row.style.display = 'none';
                }
            });

            resultCount.innerText = visibleCount;
            noResults.style.display = visibleCount === 0 && rows.length > 0 ? 'block' : 'none';
            tbody.style.display = visibleCount === 0 && rows.length > 0 ? 'none' : '';
        });
    }


    // ─────────────────────────────────────────────
    // 5. Checkouts list — Chart.js stats
    // Guard : évite de créer le chart plusieurs fois sur le même canvas
    // ─────────────────────────────────────────────
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


    // ─────────────────────────────────────────────
    // 6. FullCalendar init (dashboard & calendar pages)
    // Guard : évite de réinitialiser le calendrier s'il existe déjà
    // ─────────────────────────────────────────────
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
    }


    // ─────────────────────────────────────────────
    // 7. Vehicle & Head checkbox highlight (project form)
    // ─────────────────────────────────────────────
    document.querySelectorAll('input[name="vehicle_ids"], input[name="head_ids"]').forEach(cb => {
        cb.addEventListener('change', () => {
            const label = cb.closest('label');
            if (cb.checked) {
                label.style.background = '#f8f9fa';
                label.style.borderColor = '#858585';
            } else {
                label.style.background = '';
                label.style.borderColor = '#e5e7eb';
            }
        });
    });

    // ─────────────────────────────────────────────
    // 8. Project form — date validation
    // ─────────────────────────────────────────────
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

        // Initial run
        updateMinDates();
    }
    // ─────────────────────────────────────────────
    // 9. Centralized Search (handles q= URL param + data-search rows)
    // ─────────────────────────────────────────────
    const searchableRows = document.querySelectorAll('.searchable-row');
    if (searchableRows.length > 0) {
        const filterItems = (query) => {
            const q = query.toLowerCase().trim();
            searchableRows.forEach(row => {
                const searchText = (row.getAttribute('data-search') || '') + ' ' + row.textContent.toLowerCase();
                row.style.display = searchText.includes(q) ? '' : 'none';
            });
        };

        // Handle URL parameter 'q' on load
        const urlParams = new URLSearchParams(window.location.search);
        const qParam = urlParams.get('q');
        if (qParam) {
            filterItems(qParam);

            // Affichage dynamique du badge de filtre actif avec possibilité de réinitialisation
            const tableContainer = document.querySelector('.admin-table-container') || searchableRows[0].closest('table');
            if (tableContainer && !document.getElementById('activeFilterBanner')) {
                const banner = document.createElement('div');
                banner.id = 'activeFilterBanner';
                banner.className = 'admin-active-filter-bar';
                banner.innerHTML = `
                    <span>🔍 Filtre actif : <strong>"${escapeHtml(qParam)}"</strong></span>
                    <button type="button" class="admin-btn-clear-filter" id="clearFilterBtn">✕ Effacer le filtre</button>
                `;
                tableContainer.parentNode.insertBefore(banner, tableContainer);

                document.getElementById('clearFilterBtn')?.addEventListener('click', () => {
                    banner.remove();
                    searchableRows.forEach(r => r.style.display = '');
                    window.history.replaceState(null, '', window.location.pathname);
                });
            }
        }

        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            if (qParam) searchInput.value = qParam;
            searchInput.addEventListener('input', e => {
                filterItems(e.target.value);
            });
        }
    }

    // ─────────────────────────────────────────────
    // 10. Sortable table columns
    // ─────────────────────────────────────────────
    document.querySelectorAll('.admin-table th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const table = th.closest('table');
            const tbody = table.querySelector('tbody');
            const colIdx = parseInt(th.dataset.col);
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

    // ─────────────────────────────────────────────
    // 11. Modal protocoles freins et pneus
    // ─────────────────────────────────────────────
    const vehiclesModal = document.getElementById('vehiclesModal');
    const vTriggers = document.querySelectorAll('.vehicle-modal-trigger');
    const closeVModalBtn = document.getElementById('closeVehiclesModal');

    if (vehiclesModal && vTriggers.length > 0) {
        vTriggers.forEach(trigger => {
            trigger.addEventListener('click', (e) => {
                e.preventDefault();
                const iframe = vehiclesModal.querySelector('iframe');
                if (iframe && !iframe.getAttribute('src') && iframe.dataset.src) {
                    iframe.setAttribute('src', iframe.dataset.src);
                }
                vehiclesModal.style.display = 'flex';
            });
        });

        if (closeVModalBtn) {
            closeVModalBtn.addEventListener('click', () => {
                vehiclesModal.style.display = 'none';
            });
        }

        window.addEventListener('click', (event) => {
            if (event.target === vehiclesModal) {
                vehiclesModal.style.display = 'none';
            }
        });
    }

    // ─────────────────────────────────────────────
    // 12. Command Palette (Cmd + K)
    // ─────────────────────────────────────────────
    initCmdK();
}

/**
 * Utilitaire : Échappement HTML sécurisé.
 * @param {string} str
 * @returns {string}
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

/**
 * Retourne le SVG correspondant à une icône d'action/navigation.
 * @param {string} icon
 * @returns {string}
 */
function getIconSvg(icon) {
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

// ─────────────────────────────────────────────
// Command Palette (Cmd + K) — Autonome & Résilient
// ─────────────────────────────────────────────

let _cmdkCurrentResults = [];
let _cmdkSelectedIndex = 0;
let _cmdkDebounceTimer = null;

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

// Exposer sur window pour accessibilité globale
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
                        ${getIconSvg(item.icon)}
                    </div>
                    <div class="admin-cmdk-item-text">
                        <span class="admin-cmdk-item-title">${escapeHtml(item.title)}</span>
                        <span class="admin-cmdk-item-sub">${escapeHtml(item.subtitle)}</span>
                    </div>
                </div>
                <span class="admin-cmdk-badge ${badgeClass}">${escapeHtml(item.category)}</span>
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

// Enregistrement du raccourci clavier global Cmd+K / Ctrl+K et Escape (attaché au document immédiatement)
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

// ─────────────────────────────────────────────
// Contrôleur de formulaire d'inspection (Check-in & Check-out)
// ─────────────────────────────────────────────

function updatePhotoLabel(input) {
    const preview = document.querySelector(`.photo-preview[data-for="${input.name}"]`);
    if (!preview) return;
    preview.innerHTML = '';
    if (input.files.length > 0) {
        for (const file of input.files) {
            const reader = new FileReader();
            reader.onload = function (e) {
                const img = document.createElement('img');
                img.src = e.target.result;
                img.style.cssText = 'width: 70px; height: 70px; object-fit: cover; border-radius: 6px; border: 1px solid #e0e0e0;';
                preview.appendChild(img);
            };
            reader.readAsDataURL(file);
        }
    }
}
window.updatePhotoLabel = updatePhotoLabel;

function initInspectionForm(checkpointsConfig, defaultCheckpoints) {
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
        let configToUse = defaultCheckpoints || [];
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
    }

    // Écouter l'événement personnalisé de changement de véhicule émis par admin.js
    if (vehicleInput) {
        vehicleInput.addEventListener('change', updateCheckpoints);
    }

    // Validation et soumission du formulaire
    if (form) {
        form.addEventListener('submit', (e) => {
            const pInput = form.querySelector('input[name="project_id"]');
            const vInput = form.querySelector('input[name="vehicle_id"]');
            const cInput = form.querySelector('input[name="controller_id"]');

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

            // Désactivation différée pour bloquer la double soumission sans empêcher l'envoi du formulaire
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

// ─────────────────────────────────────────────
// Déclenchement
// ─────────────────────────────────────────────

// Initialisation globale robuste
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        init();
        initCmdK();
    });
} else {
    init();
    initCmdK();
}
