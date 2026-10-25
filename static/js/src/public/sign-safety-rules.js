/**
 * sign-safety-rules.js — Contrôleur public pour la signature des Règles de Sécurité Universelles (BVSR).
 * 
 * Fonctionnalités harmonisées avec sign-cgl.js :
 * - Capture et scellement de la signature électronique via SignaturePad
 * - Validation fluide des champs obligatoires (nom, prénom, e-mail, rôle, engagements)
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

    const form = document.getElementById('safety-rules-form');
    if (!form) return;

    // ── 1. Initialisation du SignaturePad ──────────────────────────────────
    let signaturePad = null;
    if (typeof BelleVitesseSignaturePad !== 'undefined') {
        signaturePad = new BelleVitesseSignaturePad('safety-signature-canvas', {
            clearBtnId: 'safety-btn-clear',
        });
    }

    // ── 2. Gestion de l'affichage du champ "Rôle personnalisé" ────────────
    const roleSelect = document.getElementById('safety_signer_role');
    const roleCustomGroup = document.getElementById('safety_role_custom_group');
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
    const btnSign = document.getElementById('safety-btn-sign');
    if (!btnSign) return;

    btnSign.addEventListener('click', async function (e) {
        e.preventDefault();
        if (typeof hideFeedback === 'function') hideFeedback();

        // A. Validation des champs d'identité
        const firstNameInput = document.getElementById('safety_first_name');
        const lastNameInput = document.getElementById('safety_last_name');
        const emailInput = document.getElementById('safety_email');

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

        // B. Validation des engagements obligatoires
        const ackRules = document.getElementById('ack_rules');
        const ackAuthority = document.getElementById('ack_authority');

        if (ackRules && !ackRules.checked) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez confirmer avoir pris connaissance des règles de sécurité en cochant la case requise.', 'error');
            }
            ackRules.focus();
            return;
        }

        if (ackAuthority && !ackAuthority.checked) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez confirmer votre droit et devoir d’interruption (Stop Work Authority) en cochant la case requise.', 'error');
            }
            ackAuthority.focus();
            return;
        }

        // C. Validation de la signature manuscrite
        if (!signaturePad || signaturePad.isEmpty()) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez apposer votre signature manuscrite dans le cadre prévu.', 'error');
            }
            const canvas = document.getElementById('safety-signature-canvas');
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
            console.error('Erreur réseau signature BVSR:', err);
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
