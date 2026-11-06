/**
 * sign-risk-assessment.js — Contrôleur public pour la signature de l'Analyse des Risques (BVRS).
 * 
 * Fonctionnalités :
 * - Capture et scellement de la signature électronique via SignaturePad
 * - Validation fluide des champs obligatoires (nom, prénom, e-mail, rôle, engagements)
 * - Soumission asynchrone sécurisée sans friction
 * - Feedback unifié et actualisation automatique de l'état scellé
 */

function initRiskAssessmentSign() {
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

    let signaturePad = null;
    if (typeof BelleVitesseSignaturePad !== 'undefined') {
        signaturePad = new BelleVitesseSignaturePad('risk-signature-canvas', {
            clearBtnId: 'risk-btn-clear',
        });
    }

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

    if (radioFreelance && radioCompany) {
        radioFreelance.addEventListener('change', updateCompanyFields);
        radioCompany.addEventListener('change', updateCompanyFields);
        updateCompanyFields();
    }

    const btnSign = document.getElementById('risk-btn-sign');
    const feedbackBox = document.getElementById('feedback');

    function showFeedback(msg, isError) {
        if (!feedbackBox) return;
        feedbackBox.textContent = msg;
        feedbackBox.className = 'feedback-box ' + (isError ? 'feedback-box--error' : 'feedback-box--success');
        feedbackBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    if (btnSign) {
        btnSign.addEventListener('click', async function (e) {
            e.preventDefault();

            if (!signaturePad || signaturePad.isEmpty()) {
                showFeedback('Veuillez apposer votre signature manuscrite dans le cadre prévu.', true);
                return;
            }

            const ackCheckbox = document.getElementById('ack_risk_assessment');
            if (ackCheckbox && !ackCheckbox.checked) {
                showFeedback("Veuillez cocher la case attestant de la prise de connaissance de l'analyse des risques.", true);
                return;
            }

            const firstNameInput = document.getElementById('risk_signer_first_name');
            const lastNameInput = document.getElementById('risk_signer_last_name');
            const emailInput = document.getElementById('risk_signer_email');

            const firstName = firstNameInput ? firstNameInput.value.trim() : '';
            const lastName = lastNameInput ? lastNameInput.value.trim() : '';
            const email = emailInput ? emailInput.value.trim() : '';

            if (!firstName || !lastName) {
                showFeedback('Veuillez renseigner votre prénom et votre nom.', true);
                return;
            }

            if (!email || !email.includes('@')) {
                showFeedback('Veuillez renseigner une adresse e-mail valide.', true);
                return;
            }

            const isCompany = radioCompany && radioCompany.checked;
            const companyName = isCompany ? (document.getElementById('risk_company_name') ? document.getElementById('risk_company_name').value.trim() : '') : '';
            const companyAddress = isCompany ? (document.getElementById('risk_company_address') ? document.getElementById('risk_company_address').value.trim() : '') : '';

            const phone = document.getElementById('risk_signer_phone') ? document.getElementById('risk_signer_phone').value.trim() : '';
            const role = roleSelect ? roleSelect.value : 'production';
            const roleCustom = (role === 'other' && document.getElementById('risk_signer_role_custom')) ? document.getElementById('risk_signer_role_custom').value.trim() : '';

            btnSign.disabled = true;
            btnSign.textContent = 'Scellement en cours...';

            const payload = {
                signature: signaturePad.toDataURL(),
                first_name: firstName,
                last_name: lastName,
                email: email,
                phone: phone,
                role: role,
                role_custom: roleCustom,
                entity_type: isCompany ? 'company' : 'freelance',
                company_name: companyName,
                company_address: companyAddress,
                ack_risk_assessment: true,
            };

            const csrfToken = document.getElementById('csrf_token') ? document.getElementById('csrf_token').value : '';

            try {
                const response = await fetch(window.location.pathname, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                    },
                    body: JSON.stringify(payload),
                });

                const result = await response.json();
                if (response.ok && result.success) {
                    showFeedback('Votre engagement a été signé et scellé avec succès ! Rechargement...', false);
                    setTimeout(function () {
                        window.location.reload();
                    }, 1200);
                } else {
                    showFeedback(result.error || "Une erreur est survenue lors de l'enregistrement de votre signature.", true);
                    btnSign.disabled = false;
                    btnSign.textContent = 'Signer le document';
                }
            } catch (err) {
                showFeedback('Erreur réseau. Veuillez vérifier votre connexion et réessayer.', true);
                btnSign.disabled = false;
                btnSign.textContent = 'Signer le document';
            }
        });
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRiskAssessmentSign);
} else {
    initRiskAssessmentSign();
}

