/**
 * waivers.js — Gestion des actions sur les décharges (copie de lien, feedback visuel)
 */
(function () {
    'use strict';

    function copyToClipboard(text) {
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(text);
        }
        return new Promise(function (resolve, reject) {
            var textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            textArea.style.top = '-999999px';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {
                var successful = document.execCommand('copy');
                document.body.removeChild(textArea);
                if (successful) {
                    resolve();
                } else {
                    reject(new Error('execCommand copy failed'));
                }
            } catch (err) {
                document.body.removeChild(textArea);
                reject(err);
            }
        });
    }

    function initCopyWaiverLinks() {
        document.addEventListener('click', function (e) {
            var btn = e.target.closest('.js-copy-waiver-link');
            if (!btn) return;
            e.preventDefault();

            var copyUrl = btn.getAttribute('data-copy-url');
            if (!copyUrl) return;

            var csrfMeta = document.querySelector('meta[name="csrf-token"]');
            var csrfInput = document.querySelector('input[name="csrf_token"]');
            var csrfToken = (csrfMeta && csrfMeta.getAttribute('content')) || (csrfInput && csrfInput.value) || '';

            var originalHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="u-text-2xs">...</span>';

            fetch(copyUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            })
                .then(function (res) {
                    return res.json().then(function (data) {
                        return { ok: res.ok, data: data };
                    });
                })
                .then(function (result) {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;

                    if (!result.ok || !result.data.success || !result.data.url) {
                        var errMsg = (result.data && result.data.error) || 'Impossible de récupérer le lien de signature.';
                        if (typeof window.showFlash === 'function') {
                            window.showFlash(errMsg, 'danger');
                        } else {
                            alert(errMsg);
                        }
                        return;
                    }

                    var signatureUrl = result.data.url;
                    copyToClipboard(signatureUrl)
                        .then(function () {
                            if (typeof window.showFlash === 'function') {
                                window.showFlash('Le lien a été copié dans le presse-papier.', 'info');
                            }
                            btn.innerHTML = '<i data-lucide="check"></i>';
                            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                                window.lucide.createIcons();
                            }
                            setTimeout(function () {
                                btn.innerHTML = originalHtml;
                                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                                    window.lucide.createIcons();
                                }
                            }, 2000);
                        })
                        .catch(function () {
                            prompt('Copiez le lien de signature ci-dessous :', signatureUrl);
                        });
                })
                .catch(function (err) {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                    if (window.lucide && typeof window.lucide.createIcons === 'function') {
                        window.lucide.createIcons();
                    }
                    console.error('Erreur lors de la génération du lien:', err);
                    if (typeof window.showFlash === 'function') {
                        window.showFlash('Erreur réseau lors de la récupération du lien.', 'danger');
                    }
                });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCopyWaiverLinks);
    } else {
        initCopyWaiverLinks();
    }
})();
