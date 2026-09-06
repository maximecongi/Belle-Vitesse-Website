/**
 * inspections.js — Contrôleur des formulaires de départ et retour (Check-in & Check-out).
 */

function updatePhotoLabel(input) {
    const preview = document.querySelector(`.photo-preview[data-for="${input.name}"]`);
    if (!preview) return;
    preview.innerHTML = '';
    if (input.files && input.files.length > 0) {
        Array.from(input.files).forEach((file, index) => {
            const reader = new FileReader();
            reader.onload = function (e) {
                const wrapper = document.createElement('div');
                wrapper.className = 'photo-preview-item';
                wrapper.style.cssText = 'position: relative; display: inline-block; margin: 4px;';

                const img = document.createElement('img');
                img.src = e.target.result;
                img.style.cssText = 'width: 76px; height: 76px; object-fit: cover; border-radius: 4px; border: 1px solid var(--grey-border, #e0e0e0); display: block;';
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

                preview.appendChild(wrapper);
            };
            reader.readAsDataURL(file);
        });
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

    // Écouter le changement de véhicule
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
