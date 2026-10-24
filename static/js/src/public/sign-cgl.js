/**
 * sign-cgl.js — Contrôleur public pour la signature des Conditions Générales de Location (CGL).
 * 
 * Fonctionnalités :
 * - Synchronisation en temps réel des champs légaux dans le texte contractuel
 * - Autocomplétion d'adresse via l'API adresse.data.gouv.fr
 * - Capture et scellement de la signature électronique via SignaturePad
 * - Validation des conditions obligatoires et soumission asynchrone sécurisée
 */

document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('cgl-form');
    if (!form) return;

    // ── 1. Synchronisation temps réel des mentions légales ─────────────────────
    const fieldsToSync = [
        { inputId: 'cgl_production_name', textId: 'cgl_text_production_name', defaultText: '…' },
        { inputId: 'cgl_representative', textId: 'cgl_text_representative', defaultText: '…' },
        { inputId: 'cgl_address', textId: 'cgl_text_address', defaultText: '…' },
        { inputId: 'cgl_siret', textId: 'cgl_text_siret', defaultText: '…' },
        { inputId: 'cgl_vat_number', textId: 'cgl_text_vat', defaultText: '…' },
        // Synchronisation Annexe 2
        { inputId: 'cgl_production_name', textId: 'cgl_text_annexe2_production_name', defaultText: '…' },
        { inputId: 'cgl_legal_form', textId: 'cgl_text_annexe2_legal_form', defaultText: '—' },
        { inputId: 'cgl_siret', textId: 'cgl_text_annexe2_siret', defaultText: '—' },
        { inputId: 'cgl_vat_number', textId: 'cgl_text_annexe2_vat', defaultText: '—' },
        { inputId: 'cgl_representative', textId: 'cgl_text_annexe2_representative', defaultText: '—' },
        { inputId: 'cgl_representative', textId: 'cgl_text_annexe2_sign_name', defaultText: '—' },
        { inputId: 'cgl_representative_role', textId: 'cgl_text_annexe2_role', defaultText: 'Représentant légal' },
        { inputId: 'cgl_representative_role', textId: 'cgl_text_annexe2_sign_role', defaultText: 'Représentant légal' },
        { inputId: 'cgl_address', textId: 'cgl_text_annexe2_address', defaultText: '—' },
        { inputId: 'cgl_phone', textId: 'cgl_text_annexe2_phone', defaultText: '—' },
        { inputId: 'cgl_email', textId: 'cgl_text_annexe2_email', defaultText: '—' },
        { inputId: 'cgl_city', textId: 'cgl_text_annexe2_city', defaultText: 'Paris' },
    ];

    function updateCglContractText() {
        fieldsToSync.forEach(function (item) {
            const inputEl = document.getElementById(item.inputId);
            const textEl = document.getElementById(item.textId);
            if (inputEl && textEl) {
                const val = inputEl.value.trim();
                textEl.textContent = val || item.defaultText;
            }
        });
    }

    fieldsToSync.forEach(function (item) {
        const inputEl = document.getElementById(item.inputId);
        if (inputEl) {
            inputEl.addEventListener('input', updateCglContractText);
        }
    });
    updateCglContractText();

    // ── 2. Autocomplétion d'adresse ──────────────────────────────────────────
    const addressInput = document.getElementById('cgl_address');
    const suggestionsContainer = document.getElementById('cgl_address_suggestions');
    let lastSelectedAddress = '';

    if (addressInput && suggestionsContainer) {
        addressInput.addEventListener('input', async function () {
            const query = addressInput.value.trim();
            if (query === lastSelectedAddress || query.length < 3) {
                suggestionsContainer.classList.add('u-d-none');
                suggestionsContainer.innerHTML = '';
                return;
            }
            try {
                const res = await fetch('https://api-adresse.data.gouv.fr/search/?q=' + encodeURIComponent(query) + '&limit=5');
                const data = await res.json();
                if (data.features && data.features.length > 0) {
                    suggestionsContainer.innerHTML = '';
                    data.features.forEach(function (feature) {
                        const div = document.createElement('div');
                        div.className = 'suggestion-item';
                        div.textContent = feature.properties.label;
                        div.addEventListener('click', function () {
                            lastSelectedAddress = feature.properties.label;
                            addressInput.value = feature.properties.label;
                            suggestionsContainer.classList.add('u-d-none');
                            suggestionsContainer.innerHTML = '';
                            updateCglContractText();
                        });
                        suggestionsContainer.appendChild(div);
                    });
                    suggestionsContainer.classList.remove('u-d-none');
                } else {
                    suggestionsContainer.classList.add('u-d-none');
                    suggestionsContainer.innerHTML = '';
                }
            } catch (err) {
                console.error('Erreur API adresse:', err);
            }
        });

        document.addEventListener('click', function (e) {
            if (!addressInput.contains(e.target) && !suggestionsContainer.contains(e.target)) {
                suggestionsContainer.classList.add('u-d-none');
            }
        });
    }

    // ── 3. Contrôleur SignaturePad ───────────────────────────────────────────
    let signaturePad = null;
    if (typeof BelleVitesseSignaturePad !== 'undefined') {
        signaturePad = new BelleVitesseSignaturePad('cgl-signature-canvas', {
            clearBtnId: 'cgl-btn-clear',
        });
    }

    // ── 4. Bouton de soumission et scellement ─────────────────────────────────
    const btnSign = document.getElementById('cgl-btn-sign');
    if (!btnSign) return;

    btnSign.addEventListener('click', async function (e) {
        e.preventDefault();
        if (typeof hideFeedback === 'function') hideFeedback();

        // Vérification des champs requis
        const requiredFieldIds = [
            'cgl_production_name',
            'cgl_legal_form',
            'cgl_representative',
            'cgl_representative_role',
            'cgl_siret',
            'cgl_address',
            'cgl_phone',
            'cgl_email',
            'cgl_city',
            'cgl_insurance_company',
            'cgl_insurance_policy'
        ];
        let hasMissing = false;

        requiredFieldIds.forEach(function (id) {
            const el = document.getElementById(id);
            if (!el || !el.value.trim()) {
                hasMissing = true;
                if (el) el.classList.add('is-invalid');
            } else {
                if (el) el.classList.remove('is-invalid');
            }
        });

        if (hasMissing) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez renseigner toutes les informations obligatoires de la production et de son assurance.', 'error');
            }
            return;
        }

        // Vérification de la case d'acceptation
        const acceptTerms = document.getElementById('cgl_accept_terms');
        if (!acceptTerms || !acceptTerms.checked) {
            if (typeof showFeedback === 'function') {
                showFeedback('Vous devez déclarer avoir pris connaissance et accepter les CGL et l\'Annexe 2.', 'error');
            }
            return;
        }

        // Vérification de la signature
        if (!signaturePad || signaturePad.isEmpty()) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez apposer votre signature manuscrite dans le cadre prévu.', 'error');
            }
            return;
        }

        // Préparation du FormData
        const formData = new FormData(form);
        // Correspondance des champs pour le modèle Waiver backend
        formData.set('production_name', document.getElementById('cgl_production_name').value.trim());
        formData.set('representative', document.getElementById('cgl_representative').value.trim());
        formData.set('siret', document.getElementById('cgl_siret').value.trim());
        formData.set('address', document.getElementById('cgl_address').value.trim());
        const vatEl = document.getElementById('cgl_vat_number');
        if (vatEl) formData.set('vat_number', vatEl.value.trim());

        const roleEl = document.getElementById('cgl_representative_role');
        if (roleEl) formData.set('representative_role', roleEl.value.trim());
        const legalFormEl = document.getElementById('cgl_legal_form');
        if (legalFormEl) formData.set('legal_form', legalFormEl.value.trim());
        const phoneEl = document.getElementById('cgl_phone');
        if (phoneEl) formData.set('phone', phoneEl.value.trim());
        const emailEl = document.getElementById('cgl_email');
        if (emailEl) formData.set('email', emailEl.value.trim());
        const cityEl = document.getElementById('cgl_city');
        if (cityEl) formData.set('city', cityEl.value.trim());
        const insCoEl = document.getElementById('cgl_insurance_company');
        if (insCoEl) formData.set('insurance_company', insCoEl.value.trim());
        const insPolEl = document.getElementById('cgl_insurance_policy');
        if (insPolEl) formData.set('insurance_policy', insPolEl.value.trim());

        const insFileEl = document.getElementById('cgl_insurance_file');
        if (insFileEl && insFileEl.files && insFileEl.files[0]) {
            formData.set('production_insurance', insFileEl.files[0]);
        }

        formData.set('signature_data', signaturePad.toDataURL('image/png'));

        // Récupération du token CSRF
        const csrfInput = document.getElementById('csrf_token') || form.querySelector('input[name="csrf_token"]');
        const csrfToken = csrfInput ? csrfInput.value : '';

        btnSign.disabled = true;
        const originalHtml = btnSign.innerHTML;
        btnSign.innerHTML = '<i data-lucide="loader-2" class="u-spin"></i> <span>Scellement électronique en cours…</span>';
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }

        try {
            const response = await fetch(window.location.href, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                },
                body: formData,
            });

            let result = null;
            try {
                result = await response.json();
            } catch (parseErr) {
                console.warn('Réponse non-JSON reçue:', parseErr);
            }

            if (response.ok && result && result.success) {
                if (typeof showFeedback === 'function') {
                    showFeedback('<i data-lucide="circle-check-big"></i> CGL signées et scellées avec succès. Vous recevrez le document certifié par e-mail.', 'success');
                }
                btnSign.innerHTML = '<i data-lucide="circle-check-big"></i> <span>Document signé ✓</span>';
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
                if (signaturePad && signaturePad.canvas) {
                    signaturePad.canvas.classList.add('u-pointer-none');
                }
                setTimeout(function () {
                    window.location.reload();
                }, 2500);
            } else {
                const errMsg = (result && (result.error || result.message)) || ('Erreur lors de la signature (code ' + response.status + ').');
                if (typeof showFeedback === 'function') {
                    showFeedback(errMsg, 'error');
                }
                btnSign.disabled = false;
                btnSign.innerHTML = originalHtml;
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
            }
        } catch (err) {
            console.error('Erreur réseau CGL:', err);
            if (typeof showFeedback === 'function') {
                showFeedback('Erreur de connexion. Veuillez vérifier votre accès internet et réessayer.', 'error');
            }
            btnSign.disabled = false;
            btnSign.innerHTML = originalHtml;
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }
    });

    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
});
