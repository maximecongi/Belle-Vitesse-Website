/**
 * sign-incident.js — Contrôleur public pour la signature contradictoire d'un constat d'incident.
 * 
 * Fonctionnalités harmonisées avec sign-cgl.js, sign-pilot-waiver.js et sign-safety-rules.js :
 * - Capture et scellement de la signature électronique via BelleVitesseSignaturePad
 * - Validation fluide des champs obligatoires (nom, qualité, acceptation, signature manuscrite)
 * - Soumission asynchrone sécurisée vers l'endpoint public contradictoire
 * - Feedback unifié et actualisation automatique de l'état scellé
 */

document.addEventListener('DOMContentLoaded', function () {
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }

    const canvasEl = document.getElementById('signature-canvas');
    const btnSign = document.getElementById('btn-sign');
    if (!canvasEl || !btnSign) return;

    let signaturePad = null;
    if (typeof BelleVitesseSignaturePad !== 'undefined') {
        signaturePad = new BelleVitesseSignaturePad('signature-canvas');
    }

    const clearBtn = document.getElementById('btn-clear');
    if (clearBtn) {
        clearBtn.addEventListener('click', function () {
            if (typeof hideFeedback === 'function') hideFeedback();
        });
    }

    btnSign.addEventListener('click', async function (e) {
        e.preventDefault();
        if (typeof hideFeedback === 'function') hideFeedback();

        const nameInput = document.getElementById('signer_name');
        const roleInput = document.getElementById('signer_role');
        const acceptTerms = document.getElementById('accept_terms');

        const nameVal = (nameInput ? nameInput.value : '').trim();
        const roleVal = (roleInput ? roleInput.value : '').trim();

        if (!nameVal) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez renseigner votre nom et prénom.', 'error');
            }
            if (nameInput) nameInput.focus();
            return;
        }

        if (!roleVal) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez renseigner votre qualité / fonction sur le tournage.', 'error');
            }
            if (roleInput) roleInput.focus();
            return;
        }

        if (acceptTerms && !acceptTerms.checked) {
            if (typeof showFeedback === 'function') {
                showFeedback('Vous devez attester avoir pris connaissance du constat d\'incident.', 'error');
            }
            return;
        }

        if (!signaturePad || signaturePad.isEmpty()) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez apposer votre signature manuscrite dans le cadre prévu avant de valider.', 'error');
            }
            return;
        }

        btnSign.disabled = true;
        const originalHtml = btnSign.innerHTML;
        btnSign.innerHTML = '<i data-lucide="loader-2" class="u-spin"></i> <span>Envoi en cours…</span>';
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }

        const signatureData = signaturePad.toDataURL('image/png');

        try {
            const response = await fetch(window.location.href, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    signer_name: nameVal,
                    signer_role: roleVal,
                    signature: signatureData,
                }),
            });

            const result = await response.json();

            if (result.success || result.status === 'signed') {
                if (typeof showFeedback === 'function') {
                    showFeedback('<i data-lucide="circle-check-big"></i> Constat d\'incident signé avec succès.', 'success');
                }
                btnSign.innerHTML = '<i data-lucide="circle-check-big"></i> <span>Signé ✓</span>';
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
                if (signaturePad && signaturePad.canvas) {
                    signaturePad.canvas.style.pointerEvents = 'none';
                }
                setTimeout(function () {
                    window.location.reload();
                }, 2000);
            } else {
                if (typeof showFeedback === 'function') {
                    showFeedback(result.error || result.message || 'Erreur lors de la signature.', 'error');
                }
                btnSign.disabled = false;
                btnSign.innerHTML = originalHtml;
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
            }
        } catch (err) {
            console.error(err);
            if (typeof showFeedback === 'function') {
                showFeedback('Erreur réseau. Vérifiez votre connexion et réessayez.', 'error');
            }
            btnSign.disabled = false;
            btnSign.innerHTML = originalHtml;
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }
    });
});

