/**
 * sign-risk-assessment.js — Contrôleur public pour la signature de l'Analyse des Risques (BVRA).
 * 
 * Fonctionnalités harmonisées avec sign-safety-rules.js / sign-cgl.js :
 * - Capture et scellement de la signature électronique via SignaturePad
 * - Validation fluide des champs obligatoires (nom, prénom, e-mail, rôle, engagements)
 * - Soumission asynchrone sécurisée sans friction
 * - Feedback unifié et actualisation automatique de l'état scellé
 */

function initRiskAssessmentSign() {
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

    const form = document.getElementById('risk-assessment-form');
    if (!form) return;

    // ── 1. Initialisation du SignaturePad ──────────────────────────────────
    let signaturePad = null;
    if (typeof BelleVitesseSignaturePad !== 'undefined') {
        signaturePad = new BelleVitesseSignaturePad('risk-signature-canvas', {
            clearBtnId: 'risk-btn-clear',
        });
    }

    // ── 2. Gestion de l'affichage du champ "Rôle personnalisé" ────────────
    const roleSelect = document.getElementById('risk_signer_role');
    const roleCustomGroup = document.getElementById('risk_role_custom_group');
    if (roleSelect && roleCustomGroup) {
        roleSelect.addEventListener('change', function () {
            if (roleSelect.value === 'other') {
                roleCustomGroup.classList.remove('u-d-none');
            } else {
                roleCustomGroup.classList.add('u-d-none');
            }
        });
    }

    // ── 2b. Bascule Freelance / Société ────────────────────────────────────
    const radioFreelance = document.getElementById('risk_entity_type_freelance');
    const radioCompany = document.getElementById('risk_entity_type_company');
    const companyFieldsGroup = document.getElementById('risk_company_fields_group');

    function updateCompanyFields() {
        if (!companyFieldsGroup) return;
        if (radioCompany && radioCompany.checked) {
            companyFieldsGroup.classList.remove('u-d-none');
        } else {
            companyFieldsGroup.classList.add('u-d-none');
        }
    }

    if (radioFreelance) radioFreelance.addEventListener('change', updateCompanyFields);
    if (radioCompany) radioCompany.addEventListener('change', updateCompanyFields);

    // ── 3. Bouton de soumission et signature ──────────────────────────────
    const btnSign = document.getElementById('risk-btn-sign');
    if (!btnSign) return;

    btnSign.addEventListener('click', async function (e) {
        e.preventDefault();
        if (typeof hideFeedback === 'function') hideFeedback();

        // A. Validation des champs d'identité
        const firstNameInput = document.getElementById('risk_first_name');
        const lastNameInput = document.getElementById('risk_last_name');
        const emailInput = document.getElementById('risk_email');

        const firstName = firstNameInput ? firstNameInput.value.trim() : '';
        const lastName = lastNameInput ? lastNameInput.value.trim() : '';
        const email = emailInput ? emailInput.value.trim() : '';

        if (!firstName || !lastName) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez renseigner votre prénom et votre nom.', 'error');
            }
            if (!firstName && firstNameInput) {
                firstNameInput.classList.add('is-invalid');
                firstNameInput.focus();
            } else if (!lastName && lastNameInput) {
                lastNameInput.classList.add('is-invalid');
                lastNameInput.focus();
            }
            return;
        }

        if (firstNameInput) firstNameInput.classList.remove('is-invalid');
        if (lastNameInput) lastNameInput.classList.remove('is-invalid');

        if (!email || !email.includes('@')) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez renseigner une adresse e-mail valide pour recevoir votre exemplaire scellé.', 'error');
            }
            if (emailInput) {
                emailInput.classList.add('is-invalid');
                emailInput.focus();
            }
            return;
        }

        if (emailInput) emailInput.classList.remove('is-invalid');

        // A2. Validation si statut Société
        if (radioCompany && radioCompany.checked) {
            const companyNameInput = document.getElementById('risk_company_name');
            const companyAddressInput = document.getElementById('risk_company_address');
            const compName = companyNameInput ? companyNameInput.value.trim() : '';
            const compAddr = companyAddressInput ? companyAddressInput.value.trim() : '';

            if (!compName || !compAddr) {
                if (typeof showFeedback === 'function') {
                    showFeedback('Veuillez renseigner la raison sociale et l’adresse du siège social de votre société.', 'error');
                }
                if (!compName && companyNameInput) {
                    companyNameInput.classList.add('is-invalid');
                    companyNameInput.focus();
                } else if (!compAddr && companyAddressInput) {
                    companyAddressInput.classList.add('is-invalid');
                    companyAddressInput.focus();
                }
                return;
            }
            if (companyNameInput) companyNameInput.classList.remove('is-invalid');
            if (companyAddressInput) companyAddressInput.classList.remove('is-invalid');
        }

        // B. Validation des engagements obligatoires
        const ackRules = document.getElementById('ack_risk_assessment');

        if (ackRules && !ackRules.checked) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez confirmer avoir pris connaissance de l\'Analyse des Risques en cochant la case requise.', 'error');
            }
            ackRules.focus();
            return;
        }

        // C. Validation de la signature manuscrite
        if (!signaturePad || signaturePad.isEmpty()) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez apposer votre signature manuscrite dans le cadre prévu.', 'error');
            }
            const canvas = document.getElementById('risk-signature-canvas');
            if (canvas) canvas.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }

        // D. Préparation du FormData
        const formData = new FormData(form);
        const signatureData = signaturePad.toDataURL('image/png');
        formData.set('signature_data', signatureData);

        // Récupération du token CSRF
        const csrfInput = document.getElementById('csrf_token') || form.querySelector('input[name="csrf_token"]');
        const csrfToken = csrfInput ? csrfInput.value : '';

        // État de chargement
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
                    'X-Requested-With': 'XMLHttpRequest',
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
                    showFeedback('<i data-lucide="circle-check-big"></i> Engagement signé et scellé avec succès. Vous recevrez le document certifié par e-mail.', 'success');
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
            console.error('Erreur réseau signature BVRA:', err);
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
    document.addEventListener('DOMContentLoaded', initRiskAssessmentSign);
} else {
    initRiskAssessmentSign();
}
