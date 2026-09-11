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
                if (iframe && !iframe.getAttribute('src') && iframe.dataset.src) {
                    iframe.setAttribute('src', iframe.dataset.src);
                }
                vehiclesModal.style.display = 'flex';
            });
        });

        if (closeVModalBtn && !closeVModalBtn._modalBound) {
            closeVModalBtn._modalBound = true;
            closeVModalBtn.addEventListener('click', () => {
                vehiclesModal.style.display = 'none';
            });
        }

        if (!vehiclesModal._backdropBound) {
            vehiclesModal._backdropBound = true;
            window.addEventListener('click', (event) => {
                if (event.target === vehiclesModal) {
                    vehiclesModal.style.display = 'none';
                }
            });
        }
    }
}

function initProjectInteractions() {
    initProjectFormHighlight();
    initProjectDateValidation();
    initVehiclesModal();
}

window.initProjectInteractions = initProjectInteractions;
