/**
 * inspections.js — Contrôleur des formulaires de départ et retour (Check-in & Check-out).
 */

// Registre des annotations et photos pour les contrôles (Check-in & Check-out)
const inspectionPhotoRegistry = window.inspectionPhotoRegistry || {};
window.inspectionPhotoRegistry = inspectionPhotoRegistry;

async function updatePhotoLabel(input) {
    const preview = document.querySelector(`.photo-preview[data-for="${input.name}"]`);
    if (!preview) return;

    // Compression et optimisation préalable si des fichiers sont sélectionnés
    if (input.files && input.files.length > 0 && typeof window.compressFileInput === 'function' && input.dataset.compressed !== 'true') {
        preview.innerHTML = '<div class="u-text-xs u-text-muted u-p-1"><span class="image-compress-spinner"></span> Optimisation des photos en cours…</div>';
        await window.compressFileInput(input);
    }
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
