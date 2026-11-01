/**
 * incident-autosave.js — Sauvegarde automatique locale (IndexedDB + DataTransfer)
 * et résilience hors-ligne pour le formulaire de déclaration et d'édition d'incident.
 *
 * Évite la perte des données de saisie (circonstances, mesures, équipements, photos et devis)
 * en cas de coupure 4G sur le tournage ou rechargement involontaire de la page.
 */

(function () {
    'use strict';

    const FORM_ID = 'incidentForm';

    function getForm() {
        return document.getElementById(FORM_ID);
    }

    /**
     * Calcule la clé de stockage unique et contextuelle du formulaire d'incident.
     */
    function getIncidentStorageKey(form) {
        const path = window.location.pathname || '';
        const isEdit = path.includes('/edit');

        if (isEdit) {
            const m = path.match(/\/(\d+)\/edit/);
            const id = m ? m[1] : 'unknown';
            return `incident:edit:${id}`;
        }

        // Création (/new) : scoper par projet et véhicule sélectionné
        const pInput = form ? form.querySelector('[name="project_id"]') : null;
        const vInput = form ? form.querySelector('[name="vehicle_id"]') : null;
        const urlParams = new URLSearchParams(window.location.search);

        const pId = (pInput && pInput.value) ? pInput.value : (urlParams.get('project_id') || '0');
        const vId = (vInput && vInput.value) ? vInput.value : (urlParams.get('vehicle_id') || '0');

        return `incident:new:${pId}:${vId}`;
    }

    /**
     * Sérialise l'état complet du formulaire d'incident (texte, équipements, photos et documents).
     */
    function serializeIncidentForm(form) {
        const fields = {};
        const files = {};
        const elements = form.elements;

        for (let i = 0; i < elements.length; i++) {
            const el = elements[i];
            const name = el.name;

            // Ignorer les tokens CSRF, les mots de passe et les chaînes base64 annotées
            if (!name || name === 'csrf_token' || el.type === 'password' || name.includes('_annotated_')) {
                continue;
            }

            if (el.type === 'file') {
                if (el.files && el.files.length > 0) {
                    files[name] = Array.from(el.files).map(f => ({
                        name: f.name,
                        type: f.type || 'application/octet-stream',
                        size: f.size,
                        lastModified: f.lastModified,
                        blob: f
                    }));
                }
            } else if (el.type === 'checkbox') {
                // Pour les checkboxes à valeurs multiples (ex: remove_photos)
                if (form.querySelectorAll(`[name="${name}"]`).length > 1) {
                    if (!fields[name]) fields[name] = [];
                    if (el.checked) fields[name].push(el.value);
                } else {
                    fields[name] = el.checked;
                }
            } else if (el.type === 'radio') {
                if (el.checked) {
                    fields[name] = el.value;
                }
            } else {
                fields[name] = el.value;
            }
        }

        // Capturer les équipements cochés dans le multiselect
        const checkedVehicles = Array.from(document.querySelectorAll('#vehicleItemsList input[type="checkbox"]:checked')).map(cb => cb.value);
        const checkedHeads = Array.from(document.querySelectorAll('#headItemsList input[type="checkbox"]:checked')).map(cb => cb.value);
        const customItems = typeof window.getCustomEquipment === 'function' ? window.getCustomEquipment() : [];

        const pId = form.querySelector('[name="project_id"]')?.value || '';
        const vId = form.querySelector('[name="vehicle_id"]')?.value || '';

        return {
            formType: 'incident',
            pathname: window.location.pathname,
            projectId: pId,
            vehicleId: vId,
            fields: fields,
            files: files,
            metadata: {
                checkedVehicles: checkedVehicles,
                checkedHeads: checkedHeads,
                customEquipment: customItems
            }
        };
    }

    /**
     * Restaure les données du brouillon dans le formulaire d'incident.
     */
    async function restoreIncidentDraft(form, draft) {
        if (!form || !draft) return;
        const fields = draft.fields || {};
        const files = draft.files || {};
        const meta = draft.metadata || {};

        // 1. Restauration des champs scalaires
        Object.keys(fields).forEach(name => {
            const val = fields[name];
            const elements = form.querySelectorAll(`[name="${name}"]`);
            if (elements.length === 0) return;

            if (elements.length === 1 && elements[0].type === 'checkbox') {
                elements[0].checked = Boolean(val);
                elements[0].dispatchEvent(new Event('change', { bubbles: true }));
            } else if (elements[0].type === 'radio') {
                elements.forEach(radio => {
                    if (radio.value === String(val)) {
                        radio.checked = true;
                        radio.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                });
            } else {
                elements.forEach(el => {
                    el.value = val;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                });
            }
        });

        // 2. Mettre à jour les pilules visuelles de statut, gravité et impact
        if (typeof window.updateIncidentStatusPill === 'function') window.updateIncidentStatusPill();
        if (typeof window.updateIncidentSeverityPill === 'function') window.updateIncidentSeverityPill();
        if (typeof window.updateIncidentImpactPill === 'function') window.updateIncidentImpactPill();

        // 3. Recharger les équipements du projet sélectionné
        const projectId = fields.project_id || (form.querySelector('[name="project_id"]') ? form.querySelector('[name="project_id"]').value : '');
        if (projectId && typeof window.updateProjectEquipment === 'function') {
            window.updateProjectEquipment(projectId);
        }

        // 4. Réhydrater les équipements cochés et personnalisés
        if (Array.isArray(meta.customEquipment) && typeof window.addCustomEquipment === 'function') {
            meta.customEquipment.forEach(item => {
                window.addCustomEquipment(item);
            });
        }

        if (Array.isArray(meta.checkedVehicles)) {
            meta.checkedVehicles.forEach(val => {
                const cb = document.querySelector(`#vehicleItemsList input[value="${val}"]`);
                if (cb) cb.checked = true;
            });
        }

        if (Array.isArray(meta.checkedHeads)) {
            meta.checkedHeads.forEach(val => {
                const cb = document.querySelector(`#headItemsList input[value="${val}"]`);
                if (cb) cb.checked = true;
            });
        }

        if (typeof window.syncSelectedEquipment === 'function') {
            window.syncSelectedEquipment();
        }

        // 5. Restauration des fichiers photos et documents via DataTransfer
        if (window.DataTransfer && files && Object.keys(files).length > 0) {
            // Photos des dégâts
            if (Array.isArray(files.photos) && files.photos.length > 0) {
                const inputPhotos = form.querySelector('input[type="file"][name="photos"]');
                if (inputPhotos) {
                    try {
                        const dt = new DataTransfer();
                        files.photos.forEach(item => {
                            if (item.blob) {
                                const f = new File([item.blob], item.name || 'dommage.jpg', {
                                    type: item.type || 'image/jpeg',
                                    lastModified: item.lastModified || Date.now()
                                });
                                dt.items.add(f);
                            }
                        });
                        inputPhotos.files = dt.files;
                        if (typeof window.previewFiles === 'function') {
                            window.previewFiles(inputPhotos, 'photos-preview');
                        } else {
                            inputPhotos.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    } catch (err) {
                        console.warn('⚠️ Erreur réinjection photos incident :', err);
                    }
                }
            }

            // Documents scannés / devis
            if (Array.isArray(files.documents) && files.documents.length > 0) {
                const inputDocs = form.querySelector('input[type="file"][name="documents"]');
                if (inputDocs) {
                    try {
                        const dt = new DataTransfer();
                        files.documents.forEach(item => {
                            if (item.blob) {
                                const f = new File([item.blob], item.name || 'document.pdf', {
                                    type: item.type || 'application/pdf',
                                    lastModified: item.lastModified || Date.now()
                                });
                                dt.items.add(f);
                            }
                        });
                        inputDocs.files = dt.files;
                        if (typeof window.previewDocs === 'function') {
                            window.previewDocs(inputDocs, 'docs-preview');
                        } else {
                            inputDocs.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    } catch (err) {
                        console.warn('⚠️ Erreur réinjection documents incident :', err);
                    }
                }
            }
        }

        // 6. Signalement personnalisé
        form.dispatchEvent(new CustomEvent('incident-draft-restored', {
            bubbles: true,
            detail: { draft: draft }
        }));
    }

    /**
     * Affiche la bannière d'autosave enrichie pour le formulaire d'incident.
     */
    function showIncidentAutosaveBanner(form, draft, storageKey) {
        const existing = form.querySelector('.inspection-autosave-banner');
        if (existing) existing.remove();

        const banner = document.createElement('div');
        banner.className = 'inspection-autosave-banner u-mb-4';
        banner.id = 'incidentAutosaveBanner';

        const store = window.BvDraftStore;
        const formattedDate = store ? store.formatTimeAgo(draft.timestamp) : 'récemment';

        const fieldCount = Object.keys(draft.fields || {}).filter(k => {
            const v = draft.fields[k];
            return v !== '' && v !== false && v !== null;
        }).length;

        const photoCount = Array.isArray(draft.files?.photos) ? draft.files.photos.length : 0;
        const docCount = Array.isArray(draft.files?.documents) ? draft.files.documents.length : 0;

        let detailsMeta = `${fieldCount} champ${fieldCount > 1 ? 's' : ''} complété${fieldCount > 1 ? 's' : ''}`;
        if (photoCount > 0) {
            detailsMeta += ` • <span class="draft-photos-badge">📷 ${photoCount} photo${photoCount > 1 ? 's' : ''}</span>`;
        }
        if (docCount > 0) {
            detailsMeta += ` • <span class="draft-docs-badge">📄 ${docCount} document${docCount > 1 ? 's' : ''}</span>`;
        }

        banner.innerHTML = `
            <div class="inspection-autosave-content">
                <span class="inspection-autosave-icon"><i data-lucide="history"></i></span>
                <div class="inspection-autosave-text">
                    <strong class="inspection-autosave-title">Brouillon de constat d'incident détecté</strong>
                    <div class="inspection-autosave-desc">
                        Saisie conservée (${formattedDate}) — ${detailsMeta}. Souhaitez-vous la restaurer ?
                    </div>
                </div>
            </div>
            <div class="inspection-autosave-actions">
                <button type="button" class="admin-btn admin-btn-sm admin-btn-primary" id="btnRestoreIncidentAutosave">
                    <i data-lucide="rotate-ccw"></i> Restaurer la saisie
                </button>
                <button type="button" class="admin-btn admin-btn-sm admin-btn-secondary" id="btnDiscardIncidentAutosave">
                    Ignorer
                </button>
            </div>
        `;

        form.insertBefore(banner, form.firstChild);

        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }

        const btnRestore = banner.querySelector('#btnRestoreIncidentAutosave');
        const btnDiscard = banner.querySelector('#btnDiscardIncidentAutosave');

        if (btnRestore) {
            btnRestore.addEventListener('click', async function () {
                btnRestore.disabled = true;
                btnRestore.innerHTML = '<span class="image-compress-spinner"></span> Restauration…';
                await restoreIncidentDraft(form, draft);

                banner.className = 'inspection-autosave-banner is-restored u-mb-4';
                banner.innerHTML = `
                    <div class="inspection-autosave-content">
                        <span class="inspection-autosave-icon"><i data-lucide="circle-check"></i></span>
                        <div class="inspection-autosave-text">
                            <strong class="inspection-autosave-title">Données, photos et pièces jointes du constat restaurées avec succès</strong>
                        </div>
                    </div>
                `;
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
                setTimeout(() => {
                    banner.remove();
                }, 3500);
            });
        }

        if (btnDiscard) {
            btnDiscard.addEventListener('click', async function () {
                if (confirm('Voulez-vous vraiment supprimer définitivement ce brouillon de constat ?')) {
                    if (store) {
                        await store.deleteDraft(storageKey);
                    }
                    banner.remove();
                }
            });
        }
    }

    /**
     * Initialisation du contrôleur d'autosave sur le formulaire d'incident.
     */
    async function initIncidentAutosave() {
        const form = getForm();
        if (!form) return;

        const store = window.BvDraftStore;
        if (!store) {
            console.warn('⚠️ BvDraftStore non disponible pour les incidents');
            return;
        }

        // Nettoyer si la soumission précédente a réussi
        const pendingKey = sessionStorage.getItem('bv_pending_incident_key');
        if (pendingKey) {
            await store.deleteDraft(pendingKey);
            sessionStorage.removeItem('bv_pending_incident_key');
        }

        const currentKey = getIncidentStorageKey(form);

        // Recherche d'un brouillon existant
        const existingDraft = await store.loadDraft(currentKey);
        if (existingDraft && existingDraft.fields && Object.keys(existingDraft.fields).length > 0) {
            showIncidentAutosaveBanner(form, existingDraft, currentKey);
        }

        // Sauvegarde automatique avec debounce de 400ms
        let debounceTimer = null;
        function triggerSave() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(async () => {
                const key = getIncidentStorageKey(form);
                const payload = serializeIncidentForm(form);

                const hasData = Object.keys(payload.fields).some(k => {
                    const val = payload.fields[k];
                    return val !== '' && val !== false && val !== null;
                }) || Object.keys(payload.files).length > 0;

                if (hasData) {
                    await store.saveDraft(key, payload);
                }
            }, 400);
        }

        form.addEventListener('input', triggerSave);
        form.addEventListener('change', triggerSave);

        // Garde-fou soumission réseau & résilience hors-ligne
        form.addEventListener('submit', function (e) {
            const isOnline = store.isOnline();

            if (!isOnline) {
                e.preventDefault();
                let alertBox = form.querySelector('#offlineIncidentSubmitAlert');
                if (!alertBox) {
                    alertBox = document.createElement('div');
                    alertBox.id = 'offlineIncidentSubmitAlert';
                    alertBox.className = 'inspection-autosave-banner draft-offline-alert u-mb-4';
                    form.insertBefore(alertBox, form.firstChild);
                }
                alertBox.innerHTML = `
                    <div class="inspection-autosave-content">
                        <span class="inspection-autosave-icon"><i data-lucide="wifi-off"></i></span>
                        <div class="inspection-autosave-text">
                            <strong class="inspection-autosave-title">📡 Connexion Internet indisponible sur le plateau</strong>
                            <div class="inspection-autosave-desc">
                                L'envoi est mis en attente. Toutes les informations, photos des dégâts et pièces jointes restent sauvegardées en sécurité dans ce navigateur. Vous pourrez valider le constat dès le retour du réseau.
                            </div>
                        </div>
                    </div>
                `;
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
                alertBox.scrollIntoView({ behavior: 'smooth', block: 'start' });
                return false;
            }

            // En ligne : marquer la clé en attente de confirmation
            const finalKey = getIncidentStorageKey(form);
            sessionStorage.setItem('bv_pending_incident_key', finalKey);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initIncidentAutosave);
    } else {
        initIncidentAutosave();
    }
})();

