/**
 * inspection-autosave.js — Sauvegarde automatique locale (IndexedDB + DataTransfer)
 * et résilience hors-ligne pour les formulaires d'inspection (Check-out & Check-in).
 *
 * Utilise la macro et le composant unifié .admin-banner du Design System Belle Vitesse.
 */

(function () {
    'use strict';

    const FORM_ID = 'inspectionForm';

    function getForm() {
        return document.getElementById(FORM_ID);
    }

    /**
     * Calcule une clé de stockage contextuelle évitant toute collision entre véhicules/projets.
     */
    function getInspectionStorageKey(form) {
        const path = window.location.pathname || '';
        const mode = path.includes('/checkin') ? 'checkin' : 'checkout';
        const isEdit = path.includes('/edit');

        if (isEdit) {
            const m = path.match(/\/(\d+)\/edit/);
            const id = m ? m[1] : 'unknown';
            return `inspection:${mode}:edit:${id}`;
        }

        // Création (/new) : scoper par projet et véhicule
        const pInput = form ? form.querySelector('[name="project_id"]') : null;
        const vInput = form ? form.querySelector('[name="vehicle_id"]') : null;
        const urlParams = new URLSearchParams(window.location.search);

        const pId = (pInput && pInput.value) ? pInput.value : (urlParams.get('project_id') || '0');
        const vId = (vInput && vInput.value) ? vInput.value : (urlParams.get('vehicle_id') || '0');

        return `inspection:${mode}:new:${pId}:${vId}`;
    }

    /**
     * Extrait les champs scalaires et les fichiers du formulaire.
     */
    function serializeInspectionForm(form) {
        const fields = {};
        const files = {};
        const elements = form.elements;

        for (let i = 0; i < elements.length; i++) {
            const el = elements[i];
            const name = el.name;

            // Ignorer les champs sans nom, les tokens CSRF, les mots de passe et les chaînes base64 annotées
            if (!name || name === 'csrf_token' || el.type === 'password' || name.includes('_annotated_')) {
                continue;
            }

            if (el.type === 'file') {
                if (el.files && el.files.length > 0) {
                    files[name] = Array.from(el.files).map(f => ({
                        name: f.name,
                        type: f.type || 'image/jpeg',
                        size: f.size,
                        lastModified: f.lastModified,
                        blob: f
                    }));
                }
            } else if (el.type === 'checkbox') {
                fields[name] = el.checked;
            } else if (el.type === 'radio') {
                if (el.checked) {
                    fields[name] = el.value;
                }
            } else {
                fields[name] = el.value;
            }
        }

        // Sauvegarder les métadonnées d'annotations de photos si existantes
        const registry = window.inspectionPhotoRegistry || {};
        const annotationMeta = {};
        Object.keys(registry).forEach(fieldName => {
            if (Array.isArray(registry[fieldName])) {
                annotationMeta[fieldName] = registry[fieldName].map((item, idx) => ({
                    index: idx,
                    isAnnotated: Boolean(item && item.isAnnotated),
                    annotations: (item && item.annotations) ? item.annotations : []
                }));
            }
        });

        const pId = form.querySelector('[name="project_id"]')?.value || '';
        const vId = form.querySelector('[name="vehicle_id"]')?.value || '';

        return {
            formType: window.location.pathname.includes('/checkin') ? 'checkin' : 'checkout',
            pathname: window.location.pathname,
            projectId: pId,
            vehicleId: vId,
            fields: fields,
            files: files,
            metadata: {
                annotations: annotationMeta
            }
        };
    }

    /**
     * Restaure les données du brouillon dans le formulaire.
     */
    async function restoreInspectionDraft(form, draft) {
        if (!form || !draft) return;
        const fields = draft.fields || {};
        const files = draft.files || {};

            // 1. Restauration ordonnée des champs scalaires (Projet en premier, puis Véhicule, puis checkpoints)
            const sortedKeys = Object.keys(fields).sort((a, b) => {
                if (a === 'project_id') return -1;
                if (b === 'project_id') return 1;
                if (a === 'vehicle_id') return -1;
                if (b === 'vehicle_id') return 1;
                return 0;
            });

            sortedKeys.forEach(name => {
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

                        // Mise à jour visuelle des sélecteurs de points de contrôle (.badge-select)
                        const parentBadge = el.closest('.badge-select');
                        if (parentBadge) {
                            if (typeof window.syncBadgeSelectUI === 'function') {
                                window.syncBadgeSelectUI(parentBadge, val);
                            } else {
                                const trigger = parentBadge.querySelector('.badge-select-trigger');
                                const pill = trigger ? trigger.querySelector('.badge-pill') : null;
                                const matchingOpt = parentBadge.querySelector(`.badge-select-option[data-value="${val}"]`);
                                if (pill) {
                                    if (matchingOpt) {
                                        const optPill = matchingOpt.querySelector('.badge-pill');
                                        if (optPill) {
                                            pill.innerHTML = optPill.innerHTML;
                                        } else {
                                            pill.textContent = matchingOpt.textContent.trim();
                                        }
                                    } else {
                                        pill.textContent = val;
                                    }
                                    pill.setAttribute('data-val', val);
                                    pill.dataset.val = val;
                                }
                            }
                        }

                        // Mise à jour visuelle des sélecteurs riches (.rich-select : Projet, Véhicule, Contrôleur)
                        const parentRich = el.closest('.rich-select');
                        if (parentRich) {
                            const triggerLabel = parentRich.querySelector('.badge-select-trigger span:first-child');
                            const selectedBtn = parentRich.querySelector(`.rich-select-option[data-id="${val}"]`);
                            if (triggerLabel && selectedBtn) {
                                const nameAttr = selectedBtn.getAttribute('data-name');
                                const thumb = selectedBtn.getAttribute('data-thumb');
                                if (thumb) {
                                    triggerLabel.innerHTML = `<span class="u-flex u-align-center u-gap-1"><img src="${thumb}" class="vehicle-small-thumbnail"> ${nameAttr}</span>`;
                                } else if (nameAttr) {
                                    triggerLabel.textContent = nameAttr;
                                }
                            }
                        }
                    });
                }

                // Si le projet vient d'être restauré, déclencher immédiatement la mise à jour des véhicules disponibles
                if (name === 'project_id' && val && window.updateVehicleOptions) {
                    const projectOpt = document.querySelector(`#projectOptions .rich-select-option[data-id="${val}"]`);
                    if (projectOpt) {
                        window.updateVehicleOptions(projectOpt);
                    }
                }
            });

                // 2. Synchronisation globale des icônes Lucide et de l'alerte d'état véhicule
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
                if (typeof window.updateVehicleContextAlert === 'function') {
                    window.updateVehicleContextAlert();
                }

                // 3. Restauration des fichiers photos via DataTransfer
                if (window.DataTransfer && files && Object.keys(files).length > 0) {
                    for (const fieldName of Object.keys(files)) {
                        const fileList = files[fieldName];
                        if (!Array.isArray(fileList) || fileList.length === 0) continue;

                        const input = form.querySelector(`input[type="file"][name="${fieldName}"]`);
                        if (!input) continue;

                        try {
                            const dt = new DataTransfer();
                            fileList.forEach(item => {
                                if (item.blob) {
                                    const f = new File([item.blob], item.name || 'photo.jpg', {
                                        type: item.type || 'image/jpeg',
                                        lastModified: item.lastModified || Date.now()
                                    });
                                    dt.items.add(f);
                                }
                            });

                            if (dt.files.length > 0) {
                                input.files = dt.files;
                                // Déclencher le recalcul des prévisualisations et du registre
                                if (typeof window.updatePhotoLabel === 'function') {
                                    await window.updatePhotoLabel(input);
                                } else {
                                    input.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                            }
                        } catch (fileErr) {
                            console.warn(`⚠️ Impossible de réinjecter les fichiers pour ${fieldName} :`, fileErr);
                        }
                    }
                }

                // 4. Déclencher un événement personnalisé signalant la restauration
                form.dispatchEvent(new CustomEvent('inspection-draft-restored', {
                    bubbles: true,
                    detail: { draft: draft }
                }));
            }

            /**
             * Affiche la bannière de détection de brouillon via createAdminBanner.
             */
            function showAutosaveBanner(form, draft, storageKey) {
                const existing = form.querySelector('.admin-banner, .inspection-autosave-banner');
                if (existing) existing.remove();

                const store = window.BvDraftStore;
                const formattedDate = store ? store.formatTimeAgo(draft.timestamp) : 'récemment';

                // Compter les champs et les photos
                const fieldCount = Object.keys(draft.fields || {}).filter(k => {
                    const v = draft.fields[k];
                    return v !== '' && v !== false && v !== null;
                }).length;

                let photoCount = 0;
                if (draft.files) {
                    Object.keys(draft.files).forEach(k => {
                        photoCount += (draft.files[k] || []).length;
                    });
                }

                let detailsMeta = `${fieldCount} champ${fieldCount > 1 ? 's' : ''} complété${fieldCount > 1 ? 's' : ''}`;
                if (photoCount > 0) {
                    detailsMeta += ` • <span class="draft-photos-badge">📷 ${photoCount} photo${photoCount > 1 ? 's' : ''}</span>`;
                }

                const actionsHtml = `
            <button type="button" class="admin-btn admin-btn-sm admin-btn-primary" id="btnRestoreAutosave">
                <i data-lucide="rotate-ccw"></i> Restaurer la saisie
            </button>
            <button type="button" class="admin-btn admin-btn-sm admin-btn-secondary" id="btnDiscardAutosave">
                Ignorer
            </button>
        `;

                let banner;
                if (typeof window.createAdminBanner === 'function') {
                    banner = window.createAdminBanner({
                        variant: 'warning',
                        icon: 'history',
                        id: 'autosaveBanner',
                        title: 'Brouillon local non validé détecté',
                        desc: `Saisie conservée (${formattedDate}) — ${detailsMeta}. Souhaitez-vous la restaurer ?`,
                        actionsHtml: actionsHtml
                    });
                } else {
                    banner = document.createElement('div');
                    banner.className = 'admin-banner admin-banner--warning inspection-autosave-banner u-mb-4';
                    banner.id = 'autosaveBanner';
                    banner.innerHTML = `
                <div class="admin-banner-content">
                    <span class="admin-banner-icon"><i data-lucide="history"></i></span>
                    <div class="admin-banner-text">
                        <strong class="admin-banner-title">Brouillon local non validé détecté</strong>
                        <div class="admin-banner-desc">Saisie conservée (${formattedDate}) — ${detailsMeta}. Souhaitez-vous la restaurer ?</div>
                    </div>
                </div>
                <div class="admin-banner-actions">${actionsHtml}</div>
            `;
                }

                form.insertBefore(banner, form.firstChild);

                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }

                const btnRestore = banner.querySelector('#btnRestoreAutosave');
                const btnDiscard = banner.querySelector('#btnDiscardAutosave');

                if (btnRestore) {
                    btnRestore.addEventListener('click', async function () {
                        btnRestore.disabled = true;
                        btnRestore.innerHTML = '<span class="image-compress-spinner"></span> Restauration…';
                        await restoreInspectionDraft(form, draft);

                        let restoredBanner;
                        if (typeof window.createAdminBanner === 'function') {
                            restoredBanner = window.createAdminBanner({
                                variant: 'success',
                                icon: 'circle-check',
                                id: 'autosaveBanner',
                                title: 'Données et photos du brouillon restaurées avec succès'
                            });
                        } else {
                            restoredBanner = document.createElement('div');
                            restoredBanner.className = 'admin-banner admin-banner--success inspection-autosave-banner is-restored u-mb-4';
                            restoredBanner.id = 'autosaveBanner';
                            restoredBanner.innerHTML = `
                        <div class="admin-banner-content">
                            <span class="admin-banner-icon"><i data-lucide="circle-check"></i></span>
                            <div class="admin-banner-text">
                                <strong class="admin-banner-title">Données et photos du brouillon restaurées avec succès</strong>
                            </div>
                        </div>
                    `;
                        }

                        banner.replaceWith(restoredBanner);

                        if (window.lucide && typeof window.lucide.createIcons === 'function') {
                            window.lucide.createIcons();
                        }
                        setTimeout(() => {
                            restoredBanner.remove();
                        }, 3500);
                    });
                }

                if (btnDiscard) {
                    btnDiscard.addEventListener('click', async function () {
                        if (await window.adminConfirm('Supprimer définitivement ce brouillon local ?', { label: 'Supprimer le brouillon' })) {
                            if (store) {
                                await store.deleteDraft(storageKey);
                            }
                            banner.remove();
                        }
                    });
                }
            }

            /**
             * Initialise le contrôleur d'autosave sur le formulaire d'inspection.
             */
            async function initInspectionAutosave() {
                const form = getForm();
                if (!form) return;

                const store = window.BvDraftStore;
                if (!store) {
                    console.warn('⚠️ BvDraftStore non disponible');
                    return;
                }

                // Nettoyer d'anciens brouillons legacy localStorage pour libérer le quota
                try {
                    Object.keys(localStorage).forEach(k => {
                        if (k.startsWith('bv_autosave_')) {
                            localStorage.removeItem(k);
                        }
                    });
                } catch (e) { }

                // Vérifier si une soumission précédente a réussi pour nettoyer le brouillon
                const pendingKey = sessionStorage.getItem('bv_pending_inspection_key');
                if (pendingKey) {
                    await store.deleteDraft(pendingKey);
                    sessionStorage.removeItem('bv_pending_inspection_key');
                }

                let currentKey = getInspectionStorageKey(form);

                // Recherche d'un brouillon existant
                const existingDraft = await store.loadDraft(currentKey);
                if (existingDraft && existingDraft.fields && Object.keys(existingDraft.fields).length > 0) {
                    showAutosaveBanner(form, existingDraft, currentKey);
                }

                // Sauvegarde automatique avec debounce de 400ms
                let debounceTimer = null;
                function triggerSave() {
                    clearTimeout(debounceTimer);
                    debounceTimer = setTimeout(async () => {
                        const key = getInspectionStorageKey(form);
                        const payload = serializeInspectionForm(form);

                        // Ne pas encombrer la base si le formulaire est vide
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
                        let alertBox = form.querySelector('#offlineSubmitAlert');
                        if (!alertBox) {
                            if (typeof window.createAdminBanner === 'function') {
                                alertBox = window.createAdminBanner({
                                    variant: 'danger',
                                    icon: 'wifi-off',
                                    id: 'offlineSubmitAlert',
                                    title: '📡 Connexion Internet indisponible sur le plateau',
                                    desc: 'L\'envoi est mis en attente. Toutes vos données et vos photos restent sauvegardées en sécurité dans ce navigateur. Vous pourrez valider le formulaire dès le retour de la connexion réseau.'
                                });
                            } else {
                                alertBox = document.createElement('div');
                                alertBox.id = 'offlineSubmitAlert';
                                alertBox.className = 'admin-banner admin-banner--danger draft-offline-alert u-mb-4';
                                alertBox.innerHTML = `
                            <div class="admin-banner-content">
                                <span class="admin-banner-icon"><i data-lucide="wifi-off"></i></span>
                                <div class="admin-banner-text">
                                    <strong class="admin-banner-title">📡 Connexion Internet indisponible sur le plateau</strong>
                                    <div class="admin-banner-desc">
                                        L'envoi est mis en attente. Toutes vos données et vos photos restent sauvegardées en sécurité dans ce navigateur. Vous pourrez valider le formulaire dès le retour de la connexion réseau.
                                    </div>
                                </div>
                            </div>
                        `;
                            }
                            form.insertBefore(alertBox, form.firstChild);
                        }
                        if (window.lucide && typeof window.lucide.createIcons === 'function') {
                            window.lucide.createIcons();
                        }
                        alertBox.scrollIntoView({ behavior: 'smooth', block: 'start' });
                        return false;
                    }

                    // En ligne : marquer la clé en attente de validation serveur réussie
                    const finalKey = getInspectionStorageKey(form);
                    sessionStorage.setItem('bv_pending_inspection_key', finalKey);
                });
            }

            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', initInspectionAutosave);
            } else {
                initInspectionAutosave();
            }
        })();
