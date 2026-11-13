/**
 * sign-cgl.js — Contrôleur public pour la signature des Conditions Générales de Location (CGL).
 * 
 * Fonctionnalités :
 * - Aperçu PDF live du contrat (zones saisies surlignées, cliquables vers le champ)
 * - Autocomplétion d'adresse via l'API adresse.data.gouv.fr
 * - Capture et scellement de la signature électronique via SignaturePad
 * - Validation des conditions obligatoires et soumission asynchrone sécurisée
 */

function initCglSign() {
    // ── Décompte et redirection si document déjà signé ─────────────────────
    const redirectCounterEl = document.getElementById('redirect-counter');
    if (redirectCounterEl) {
        let timeLeft = 10;
        const countdownTimer = setInterval(function () {
            timeLeft -= 1;
            if (timeLeft <= 0) {
                clearInterval(countdownTimer);
                window.location.href = '/';
            } else {
                redirectCounterEl.textContent = timeLeft;
            }
        }, 1000);
        return;
    }

    const form = document.getElementById('cgl-form');
    if (!form) return;

    // ── 1. Construction du FormData (noms attendus par le backend) ─────────────
    // Partagé entre l'aperçu PDF live et la soumission finale.
    const backendFieldMap = {
        production_name: 'cgl_production_name',
        representative: 'cgl_representative',
        siret: 'cgl_siret',
        address: 'cgl_address',
        vat_number: 'cgl_vat_number',
        representative_role: 'cgl_representative_role',
        legal_form: 'cgl_legal_form',
        phone: 'cgl_phone',
        email: 'cgl_email',
        city: 'cgl_city',
        order_ref: 'cgl_order_ref',
        insurance_company: 'cgl_insurance_company',
        insurance_policy: 'cgl_insurance_policy',
    };

    function buildCglFormData(includeFile) {
        const formData = new FormData(form);
        Object.keys(backendFieldMap).forEach(function (key) {
            const el = document.getElementById(backendFieldMap[key]);
            if (el) formData.set(key, el.value.trim());
        });
        const legalCountryEl = document.getElementById('cgl_legal_country');
        if (legalCountryEl) {
            let countryVal = legalCountryEl.value.trim();
            if (legalCountryEl.tagName === 'SELECT' && legalCountryEl.selectedIndex >= 0) {
                const opt = legalCountryEl.options[legalCountryEl.selectedIndex];
                if (opt && opt.value) countryVal = opt.text.trim();
            }
            formData.set('legal_country', countryVal);
        }
        if (!includeFile) {
            formData.delete('production_insurance');
        } else {
            const insFileEl = document.getElementById('cgl_insurance_file');
            if (insFileEl && insFileEl.files && insFileEl.files[0]) {
                formData.set('production_insurance', insFileEl.files[0]);
            }
        }
        return formData;
    }

    const countryInput = document.getElementById('cgl_legal_country');
    const identifierInput = document.getElementById('cgl_siret');
    const identifierLabel = document.getElementById('cgl_siret_label');
    const identifierRequired = document.getElementById('cgl_siret_required');

    function updateIdentifierRequirement() {
        if (!countryInput || !identifierInput) return;
        const isFrance = countryInput.value.trim().toUpperCase() === 'FR';
        identifierInput.required = isFrance;
        identifierInput.placeholder = isFrance ? '14 chiffres' : 'Facultatif';
        if (!isFrance) identifierInput.classList.remove('is-invalid');
        if (identifierLabel) identifierLabel.textContent = isFrance ? 'Numéro SIRET' : 'Numéro d’immatriculation';
        if (identifierRequired) {
            identifierRequired.textContent = isFrance ? '*' : '';
            identifierRequired.classList.toggle('u-d-none', !isFrance);
        }
    }

    if (countryInput) {
        const defaultCountry = (countryInput.getAttribute('data-default-country') || '').trim().toLowerCase();
        if (defaultCountry) {
            for (let i = 0; i < countryInput.options.length; i++) {
                const opt = countryInput.options[i];
                if (opt.value.toLowerCase() === defaultCountry || opt.text.toLowerCase() === defaultCountry) {
                    countryInput.selectedIndex = i;
                    break;
                }
            }
        }
        countryInput.addEventListener('change', updateIdentifierRequirement);
    }

    updateIdentifierRequirement();

    // Suppression automatique des espaces dans le SIRET / n° d'immatriculation
    // (saisie, collage, valeur pré-remplie), en préservant la position du curseur.
    function stripIdentifierSpaces() {
        if (!identifierInput) return;
        const raw = identifierInput.value;
        if (!/\s/.test(raw)) return;
        const caret = identifierInput.selectionStart;
        identifierInput.value = raw.replace(/\s+/g, '');
        if (caret !== null && document.activeElement === identifierInput) {
            const newCaret = raw.slice(0, caret).replace(/\s+/g, '').length;
            identifierInput.setSelectionRange(newCaret, newCaret);
        }
    }

    if (identifierInput) {
        identifierInput.addEventListener('input', stripIdentifierSpaces);
        stripIdentifierSpaces();
    }

    // ── Aperçu PDF live (vrai PDF, zones saisies surlignées et cliquables) ─────
    const previewRoot = document.getElementById('cgl-pdf-preview');
    if (previewRoot && typeof BelleVitessePdfFormPreview !== 'undefined') {
        BelleVitessePdfFormPreview.init({
            container: previewRoot,
            form: form,
            serialize: function () { return buildCglFormData(false); },
        });
    }

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
                            addressInput.dispatchEvent(new Event('change', { bubbles: true }));
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
            'cgl_legal_country',
            'cgl_representative',
            'cgl_representative_role',
            'cgl_address',
            'cgl_phone',
            'cgl_email',
            'cgl_city',
            'cgl_order_ref',
            'cgl_insurance_company',
            'cgl_insurance_policy'
        ];
        const countryForIdentifier = document.getElementById('cgl_legal_country');
        const isFrenchCompany = countryForIdentifier && countryForIdentifier.value.trim().toUpperCase() === 'FR';
        if (isFrenchCompany) requiredFieldIds.push('cgl_siret');
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

        // Vérification de la déclaration de pouvoir
        const signingAuthority = document.getElementById('cgl_signing_authority');
        if (!signingAuthority || !signingAuthority.checked) {
            if (typeof showFeedback === 'function') {
                showFeedback('Vous devez certifier sur l\'honneur disposer du pouvoir d\'engager la société.', 'error');
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
        const formData = buildCglFormData(true);
        formData.set('accepted_terms', '1');
        formData.set('has_signing_authority', '1');

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
                }, 800);
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
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCglSign);
} else {
    initCglSign();
}
