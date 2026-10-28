/**
 * vehicle-configs.js — Gestion Ajax de la configuration des points de contrôle par véhicule.
 */

function initVehicleConfigs() {
    const saveButtons = document.querySelectorAll('.save-vehicle-btn');
    if (!saveButtons.length) return;

    saveButtons.forEach(btn => {
        if (btn._hasVehicleConfigListener) return;
        btn._hasVehicleConfigListener = true;

        btn.addEventListener('click', function () {
            const vehicleId = this.dataset.vehicle;
            const checkboxes = document.querySelectorAll(`.checkpoint-toggle[data-vehicle="${vehicleId}"]`);

            const enabledKeys = [];
            checkboxes.forEach(cb => {
                if (cb.checked) enabledKeys.push(cb.dataset.key);
            });

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
                || document.querySelector('input[name="csrf_token"]')?.value
                || '';

            btn.disabled = true;
            btn.innerText = '...';

            fetch('/admin/api/vehicle-configs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    vehicle_id: vehicleId,
                    enabled_keys: enabledKeys
                })
            })
                .then(r => r.json())
                .then(res => {
                    if (res.success) {
                        btn.innerText = "C'est fait !";
                        btn.classList.add('admin-btn-success-state');
                        setTimeout(() => {
                            btn.disabled = false;
                            btn.innerText = 'Enregistrer';
                            btn.classList.remove('admin-btn-success-state');
                        }, 2000);
                    } else {
                        alert('Erreur: ' + (res.error || 'Impossible d\'enregistrer'));
                        btn.disabled = false;
                        btn.innerText = 'Enregistrer';
                    }
                })
                .catch(err => {
                    console.error(err);
                    alert('Erreur de connexion');
                    btn.disabled = false;
                    btn.innerText = 'Enregistrer';
                });
        });
    });
}

window.initVehicleConfigs = initVehicleConfigs;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVehicleConfigs);
} else {
    initVehicleConfigs();
}
document.addEventListener('swup:contentReplaced', initVehicleConfigs);

