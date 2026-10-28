/**
 * sign-pilot-waiver.js — Contrôleur public pour la signature de l'Attestation Pilote (Annexe 3 aux CGL - BVPA).
 * 
 * Fonctionnalités harmonisées avec sign-cgl.js et sign-safety-rules.js :
 * - Capture et scellement de la signature électronique via SignaturePad
 * - Validation fluide des champs obligatoires (nom, prénom, e-mail, rôle, engagements sur l'honneur)
 * - Soumission asynchrone sécurisée sans friction
 * - Feedback unifié et actualisation automatique de l'état scellé
 */

document.addEventListener('DOMContentLoaded', function () {
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

    const form = document.getElementById('pilot-waiver-form');
    if (!form) return;

    // ── 1. Initialisation du SignaturePad ──────────────────────────────────
    let signaturePad = null;
    if (typeof BelleVitesseSignaturePad !== 'undefined') {
        signaturePad = new BelleVitesseSignaturePad('pilot-signature-canvas', {
            clearBtnId: 'pilot-btn-clear',
        });
    }

    // ── 2. Gestion de l'affichage du champ "Fonction personnalisée" ───────
    const roleSelect = document.getElementById('pilot_signer_role');
    const roleCustomGroup = document.getElementById('pilot_role_custom_group');
    if (roleSelect && roleCustomGroup) {
        roleSelect.addEventListener('change', function () {
            if (roleSelect.value === 'other') {
                roleCustomGroup.classList.remove('u-d-none');
            } else {
                roleCustomGroup.classList.add('u-d-none');
            }
        });
    }

    // ── 3. Bouton de soumission et signature ──────────────────────────────
    const btnSign = document.getElementById('pilot-btn-sign');
    if (!btnSign) return;

    btnSign.addEventListener('click', async function (e) {
        e.preventDefault();
        if (typeof hideFeedback === 'function') hideFeedback();

        // A. Validation des coordonnées du pilote
        const firstNameInput = document.getElementById('pilot_first_name');
        const lastNameInput = document.getElementById('pilot_last_name');
        const emailInput = document.getElementById('pilot_email');

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
                showFeedback('Veuillez renseigner une adresse e-mail valide pour recevoir votre exemplaire certifié.', 'error');
            }
            if (emailInput) {
                emailInput.classList.add('is-invalid');
                emailInput.focus();
            }
            return;
        }

        if (emailInput) emailInput.classList.remove('is-invalid');

        // B. Validation de l'engagement global sur l'honneur
        const ackEngagement = document.getElementById('ack_pilot_engagement');
        if (ackEngagement && !ackEngagement.checked) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez attester sur l\'honneur de vos déclarations et engagements en cochant la case requise.', 'error');
            }
            ackEngagement.focus();
            return;
        }

        // C. Validation de la signature manuscrite
        if (!signaturePad || signaturePad.isEmpty()) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez apposer votre signature manuscrite dans le cadre prévu.', 'error');
            }
            const canvas = document.getElementById('pilot-signature-canvas');
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
                    showFeedback('<i data-lucide="circle-check-big"></i> Attestation signée et scellée avec succès. Vous recevrez une copie certifiée par e-mail.', 'success');
                }
                btnSign.innerHTML = '<i data-lucide="circle-check-big"></i> <span>Attestation signée ✓</span>';
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
            console.error('Erreur réseau signature BVPA:', err);
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
