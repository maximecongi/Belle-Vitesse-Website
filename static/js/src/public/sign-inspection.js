/**
 * Belle Vitesse - Gestionnaire modulaire de signature des inspections (Check-out et Check-in)
 * Aucun JS inline - respect strict des standards CSP et règles de développement.
 */

document.addEventListener('DOMContentLoaded', function () {
    const container = document.getElementById('inspection-sign-container');
    if (!container) return;

    const isAlreadySigned = container.getAttribute('data-already-signed') === 'true';
    const redirectCounter = document.getElementById('redirect-counter');

    // ── Gestion de la redirection automatique si déjà signé ────────
    if (isAlreadySigned && redirectCounter) {
        let count = 3;
        const countdownTimer = setInterval(function () {
            count--;
            if (redirectCounter) {
                redirectCounter.textContent = count;
            }
            if (count <= 0) {
                clearInterval(countdownTimer);
                window.location.href = '/';
            }
        }, 1000);
        return;
    }

    const abandonUrl = container.getAttribute('data-abandon-url');
    const resumeUrl = container.getAttribute('data-resume-url');
    let isSigned = false;

    // ── Logique d'abandon et reprise de session ─────────────────────
    if (abandonUrl) {
        window.addEventListener('pagehide', function () {
            if (!isSigned) {
                navigator.sendBeacon(abandonUrl);
            }
        });
    }

    if (resumeUrl) {
        window.addEventListener('pageshow', function (event) {
            if (event.persisted && !isSigned) {
                fetch(resumeUrl, { method: 'POST' }).catch(function (err) {
                    console.warn('Inspection resume failed', err);
                });
            }
        });
    }

    // ── Initialisation du Signature Pad ────────────────────────────
    const canvasEl = document.getElementById('signature-canvas');
    let signaturePad = null;
    if (canvasEl && typeof BelleVitesseSignaturePad === 'function') {
        signaturePad = new BelleVitesseSignaturePad('signature-canvas');
    }

    const btnClear = document.getElementById('btn-clear');
    if (btnClear && signaturePad) {
        btnClear.addEventListener('click', function () {
            signaturePad.clear();
        });
    }

    // ── Soumission de la Signature ─────────────────────────────────
    const btnSign = document.getElementById('btn-sign');
    if (btnSign && signaturePad) {
        btnSign.addEventListener('click', function () {
            if (typeof hideFeedback === 'function') {
                hideFeedback();
            }
            if (signaturePad.isEmpty()) {
                if (typeof showFeedback === 'function') {
                    showFeedback('Veuillez signer avant de valider.', 'error');
                }
                return;
            }

            const btn = btnSign;
            btn.disabled = true;
            btn.textContent = 'Envoi en cours…';

            const signatureData = signaturePad.toDataURL('image/png');

            fetch('', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ signature: signatureData }),
            })
                .then(function (res) {
                    return res.json().then(function (data) {
                        return { ok: res.ok, status: res.status, data: data };
                    });
                })
                .then(function (resObj) {
                    const result = resObj.data || {};
                    if (resObj.ok && (result.status === 'signed' || resObj.status === 200)) {
                        isSigned = true;
                        if (typeof showFeedback === 'function') {
                            showFeedback('<i data-lucide="circle-check-big"></i> Document signé avec succès. Redirection en cours…', 'success');
                        }
                        btn.textContent = 'Signé ✓';
                        if (signaturePad && signaturePad.canvas) {
                            signaturePad.canvas.style.pointerEvents = 'none';
                        }
                        if (window.lucide && typeof window.lucide.createIcons === 'function') {
                            window.lucide.createIcons();
                        }
                        setTimeout(function () {
                            window.location.reload();
                        }, 1200);
                    } else {
                        const errMsg = result.error || 'Une erreur est survenue lors de la validation.';
                        if (typeof showFeedback === 'function') {
                            showFeedback(errMsg, 'error');
                        }
                        btn.disabled = false;
                        btn.textContent = 'Signer le document';
                    }
                })
                .catch(function () {
                    if (typeof showFeedback === 'function') {
                        showFeedback('Erreur réseau. Veuillez vérifier votre connexion et réessayez.', 'error');
                    }
                    btn.disabled = false;
                    btn.textContent = 'Signer le document';
                });
        });
    }

    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
});
