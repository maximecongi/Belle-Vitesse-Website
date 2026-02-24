/**
 * admin.js — Centralised JavaScript for the admin panel.
 * Loaded once via admin_base.html; each feature auto-detects
 * its DOM elements and only runs when they are present.
 */

document.addEventListener('DOMContentLoaded', () => {

    // ─────────────────────────────────────────────
    // 1. Auto-dismiss flash messages (admin_base)
    // ─────────────────────────────────────────────
    const flashes = document.querySelectorAll('.admin-flash-item');
    if (flashes.length) {
        setTimeout(() => {
            flashes.forEach(f => {
                f.style.opacity = '0';
                f.style.transform = 'translateX(100%)';
                f.style.transition = 'all 0.5s ease';
                setTimeout(() => f.remove(), 500);
            });
        }, 5000);
    }

    // ─────────────────────────────────────────────
    // 2. Badge selects (checkout form — état / sécurité)
    // ─────────────────────────────────────────────
    document.querySelectorAll('.badge-select').forEach(sel => {
        const trigger = sel.querySelector('.badge-select-trigger');
        const input = sel.querySelector('input');
        const pill = trigger.querySelector('.badge-pill');

        trigger.addEventListener('click', () => {
            // Close other dropdowns
            document.querySelectorAll('.badge-select.open').forEach(s => {
                if (s !== sel) s.classList.remove('open');
            });
            document.querySelectorAll('.rich-select.open').forEach(s => s.classList.remove('open'));
            sel.classList.toggle('open');
        });

        sel.querySelectorAll('.badge-select-option').forEach(opt => {
            opt.addEventListener('click', () => {
                const val = opt.dataset.value;
                input.value = val;
                pill.textContent = val;
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

        pOptions.forEach(opt => {
            opt.addEventListener('click', () => {
                if (opt.dataset.disabled === 'true') return;
                pInput.value = opt.dataset.id;
                pLabel.textContent = opt.dataset.name;
                pSelect.classList.remove('open');

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
                            // Always show "— Aucun —"
                            vOpt.style.display = '';
                        } else if (allowedVehicles.length === 0) {
                            // No filter → show all
                            vOpt.style.display = '';
                        } else {
                            vOpt.style.display = allowedVehicles.includes(vOpt.dataset.id) ? '' : 'none';
                        }
                    });

                    // Reset vehicle if current selection is not in the allowed list
                    if (vInput && allowedVehicles.length > 0 && !allowedVehicles.includes(vInput.value)) {
                        vInput.value = '';
                        const vLabel = document.getElementById('vehicleLabel');
                        if (vLabel) vLabel.textContent = '— Sélectionner un véhicule —';
                        vInput.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                } // End of if (vOptions)

                // Dispatch event to allow forms to update vehicle status pills per project
                pInput.dispatchEvent(new Event('change', { bubbles: true }));

                // Update vehicle option statuses based on the selected project
                const selectedProjectId = pInput.value;
                const vOptionsForStatus = document.querySelectorAll('#vehicleOptions .rich-select-option');
                if (vOptionsForStatus && selectedProjectId) {
                    vOptionsForStatus.forEach(opt => {
                        const checkoutStatuses = JSON.parse(opt.dataset.checkoutStatuses || '{}');
                        const checkinStatuses = JSON.parse(opt.dataset.checkinStatuses || '{}'); // Only present in checkin form

                        const checkoutStatus = checkoutStatuses[selectedProjectId];
                        const checkinStatus = checkinStatuses[selectedProjectId];

                        const badgeEl = opt.querySelector('.vehicle-status-badge');

                        // Checkin logic (if data-checkin-statuses is present, we are in checkin_form)
                        if (opt.hasAttribute('data-checkin-statuses')) {
                            const isCheckoutSigned = (checkoutStatus === 'Signé' || checkoutStatus === 'Validé');
                            if (checkinStatus) {
                                opt.dataset.disabled = "true";
                                if (badgeEl) {
                                    badgeEl.textContent = checkinStatus;
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
                        }
                        // Checkout logic
                        else if (opt.hasAttribute('data-checkout-statuses')) {
                            const blockedByProject = opt.dataset.blockedBy;

                            if (checkoutStatus) {
                                opt.dataset.disabled = "true";
                                if (badgeEl) {
                                    badgeEl.textContent = checkoutStatus;
                                    badgeEl.style.background = "var(--input-bg)";
                                    badgeEl.style.color = "var(--text-color)";
                                }
                            } else if (blockedByProject) {
                                opt.dataset.disabled = "true";
                                if (badgeEl) {
                                    badgeEl.textContent = "Check-in non signé : " + blockedByProject;
                                    badgeEl.style.background = "#fee2e2"; // Light red
                                    badgeEl.style.color = "#dc2626"; // Dark red
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
            });
        });
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
                // Re-apply project filter instead of showing all
                const selectedProject = document.querySelector('#projectOptions .rich-select-option[data-id="' + (document.querySelector('#projectSelect input[name="project_id"]')?.value || '') + '"]');
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

                // Dispatch event to allow dynamic forms to update checkpoints
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
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        const tbody = document.getElementById('checkouts-tbody') || document.getElementById('checkins-tbody');
        const rows = tbody.querySelectorAll('tr[data-search]');
        const resultCount = document.getElementById('result-count');
        const noResults = document.getElementById('no-results');

        searchInput.addEventListener('input', (e) => {
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
    // ─────────────────────────────────────────────
    const monthlyCanvas = document.getElementById('monthlyChart');
    if (monthlyCanvas && typeof Chart !== 'undefined') {
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

                new Chart(document.getElementById('statusChart'), {
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
            })
            .catch(error => console.error('Error fetching stats:', error));
    }

    // ─────────────────────────────────────────────
    // 6. FullCalendar init (dashboard & calendar pages)
    // ─────────────────────────────────────────────
    const calendarEl = document.getElementById('calendar');
    if (calendarEl && typeof FullCalendar !== 'undefined') {
        const calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek'
            },
            locale: 'fr',
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
    // 7. Vehicle checkbox highlight (project form)
    // ─────────────────────────────────────────────
    document.querySelectorAll('input[name="vehicle_ids"]').forEach(cb => {
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
    // Global: close all dropdowns on outside click
    // ─────────────────────────────────────────────
    document.addEventListener('click', e => {
        if (!e.target.closest('.badge-select') && !e.target.closest('.rich-select')) {
            document.querySelectorAll('.badge-select.open, .rich-select.open').forEach(s => s.classList.remove('open'));
        }
    });

});
