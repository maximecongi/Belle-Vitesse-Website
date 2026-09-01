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

        const updateVehicleOptions = (opt) => {
            if (!opt) return;

            // Enable vehicle select
            const vSelectEl = document.getElementById('vehicleSelect');
            if (vSelectEl) {
                vSelectEl.style.opacity = '';
                vSelectEl.style.pointerEvents = '';
                vSelectEl.removeAttribute('data-disabled');
            }

            // Filter vehicle options based on project's linked vehicles
            const vehiclesStr = opt.dataset.vehicles || '';
            const allowedVehicles = vehiclesStr ? vehiclesStr.split(',') : [];
            const vOptions = document.querySelectorAll('#vehicleOptions .rich-select-option');
            const vInput = document.querySelector('#vehicleSelect input[name="vehicle_id"]');

            if (vOptions.length) {
                vOptions.forEach(vOpt => {
                    if (!vOpt.dataset.id) {
                        vOpt.style.display = '';
                    } else if (allowedVehicles.length === 0) {
                        vOpt.style.display = '';
                    } else {
                        vOpt.style.display = allowedVehicles.includes(vOpt.dataset.id) ? '' : 'none';
                    }
                });

                if (vInput && allowedVehicles.length > 0 && vInput.value && !allowedVehicles.includes(vInput.value)) {
                    vInput.value = '';
                    const vLabel = document.getElementById('vehicleLabel');
                    if (vLabel) vLabel.textContent = '— Sélectionner un véhicule —';
                    vInput.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }

            pInput.dispatchEvent(new Event('change', { bubbles: true }));

            const selectedProjectId = pInput.value;
            const vOptionsForStatus = document.querySelectorAll('#vehicleOptions .rich-select-option');
            if (vOptionsForStatus && selectedProjectId) {
                const statusMap = {
                    'signed': 'Signé',
                    'pending': 'À signer',
                    'in_progress': 'En cours',
                    'validated': 'Validé',
                    'to_sign': 'À signer'
                };
                vOptionsForStatus.forEach(opt => {
                    const checkoutStatuses = JSON.parse(opt.dataset.checkoutStatuses || '{}');
                    const checkinStatuses = JSON.parse(opt.dataset.checkinStatuses || '{}');

                    const checkoutStatus = checkoutStatuses[selectedProjectId];
                    const checkinStatus = checkinStatuses[selectedProjectId];

                    const badgeEl = opt.querySelector('.vehicle-status-badge');

                    if (opt.hasAttribute('data-checkin-statuses')) {
                        const isCheckoutSigned = (checkoutStatus === 'signed' || checkoutStatus === 'validated');
                        if (checkinStatus) {
                            opt.dataset.disabled = "true";
                            if (badgeEl) {
                                badgeEl.textContent = statusMap[checkinStatus] || checkinStatus;
                                badgeEl.style.background = "var(--input-bg)";
                                badgeEl.style.color = "var(--text-color)";
                            }
                        } else if (!isCheckoutSigned) {
                            opt.dataset.disabled = "true";
                            if (badgeEl) {
                                badgeEl.textContent = "Départ non signé";
                                badgeEl.style.background = "#eee";
                                badgeEl.style.color = "#999";
                            }
                        } else {
                            opt.removeAttribute('data-disabled');
                            if (badgeEl) {
                                badgeEl.textContent = "À contrôler";
                                badgeEl.style.background = "var(--brand-blue)";
                                badgeEl.style.color = "white";
                            }
                        }
                    } else if (opt.hasAttribute('data-checkout-statuses')) {
                        const blockedByProject = opt.dataset.blockedBy;
                        if (checkoutStatus) {
                            opt.dataset.disabled = "true";
                            if (badgeEl) {
                                badgeEl.textContent = statusMap[checkoutStatus] || checkoutStatus;
                                badgeEl.style.background = "var(--input-bg)";
                                badgeEl.style.color = "var(--text-color)";
                            }
                        } else if (blockedByProject) {
                            opt.dataset.disabled = "true";
                            if (badgeEl) {
                                badgeEl.textContent = "Retour non signé : " + blockedByProject;
                                badgeEl.style.background = "#fee2e2";
                                badgeEl.style.color = "#dc2626";
                            }
                        } else {
                            opt.removeAttribute('data-disabled');
                            if (badgeEl) {
                                badgeEl.textContent = "À contrôler";
                                badgeEl.style.background = "var(--brand-blue)";
                                badgeEl.style.color = "white";
                            }
                        }
                    }
                });
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
        }
    }


    // ─────────────────────────────────────────────
    // 3b. Rich vehicle select (checkout form)
    // ─────────────────────────────────────────────
    const vSelect = document.getElementById('vehicleSelect');
    if (vSelect) {
        const vTrigger = document.getElementById('vehicleTrigger');
        const vInput = vSelect.querySelector('input[name="vehicle_id"]');
        const vLabel = document.getElementById('vehicleLabel');
        const vSearch = document.getElementById('vehicleSearch');
        const vOptions = document.querySelectorAll('#vehicleOptions .rich-select-option');

        vTrigger.addEventListener('click', () => {
            document.querySelectorAll('.badge-select.open').forEach(s => s.classList.remove('open'));
            document.querySelectorAll('.rich-select.open').forEach(s => {
                if (s !== vSelect) s.classList.remove('open');
            });
            vSelect.classList.toggle('open');
            if (vSelect.classList.contains('open')) {
                vSearch.value = '';
                const selectedProject = document.querySelector(
                    '#projectOptions .rich-select-option[data-id="' +
                    (document.querySelector('#projectSelect input[name="project_id"]')?.value || '') +
                    '"]'
                );
                const vehiclesStr = selectedProject?.dataset.vehicles || '';
                const allowed = vehiclesStr ? vehiclesStr.split(',') : [];
                vOptions.forEach(o => {
                    if (!o.dataset.id || allowed.length === 0) {
                        o.style.display = '';
                    } else {
                        o.style.display = allowed.includes(o.dataset.id) ? '' : 'none';
                    }
                });
                setTimeout(() => vSearch.focus(), 50);
            }
        });

        vSearch.addEventListener('input', () => {
            const q = vSearch.value.toLowerCase();
            vOptions.forEach(opt => {
                const text = (opt.dataset.search || opt.dataset.name || '').toLowerCase();
                opt.style.display = text.includes(q) ? '' : 'none';
            });
        });

        vOptions.forEach(opt => {
            opt.addEventListener('click', () => {
                if (opt.dataset.disabled === 'true') return;
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
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        const rows = document.querySelectorAll('.searchable-row');

        const filterItems = (query) => {
            const q = query.toLowerCase().trim();
            rows.forEach(row => {
                const searchText = (row.getAttribute('data-search') || '') + ' ' + row.textContent.toLowerCase();
                row.style.display = searchText.includes(q) ? '' : 'none';
            });
        };

        // Handle URL parameter 'q' on load
        const urlParams = new URLSearchParams(window.location.search);
        const qParam = urlParams.get('q');
        if (qParam) {
            searchInput.value = qParam;
            filterItems(qParam);
        }

        // Handle real-time input
        searchInput.addEventListener('input', e => {
            filterItems(e.target.value);
        });
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
}


// ─────────────────────────────────────────────
// Déclenchement
// ─────────────────────────────────────────────

// Premier chargement
document.addEventListener('DOMContentLoaded', init);
