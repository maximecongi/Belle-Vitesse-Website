/**
 * incident-detail.js — Contrôleur de la vue détaillée d'incident.
 * Gère :
 * - Les modales de signature électronique (BV et Production)
 * - Les canvas manuscrits BelleVitesseSignaturePad
 * - Le changement rapide de statut (résolution / clôture / transition directe)
 * - Les raccourcis clavier et fermeture des overlays
 */

(function () {
    const pads = {};

    function getOrCreatePad(canvasId, clearBtnId) {
        if (pads[canvasId]) return pads[canvasId];
        if (typeof window.BelleVitesseSignaturePad !== 'function') {
            console.warn("BelleVitesseSignaturePad non disponible.");
            return null;
        }
        const padObj = new window.BelleVitesseSignaturePad(canvasId, {
            clearBtnId: clearBtnId,
            padOptions: {
                backgroundColor: 'rgba(248, 250, 252, 0)',
                penColor: '#0f172a'
            }
        });
        pads[canvasId] = padObj;
        return padObj;
    }

    function openIncidentModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.add('is-open');

        if (modalId === 'modalBvSign') {
            const padObj = getOrCreatePad('bvCanvas', 'clearBvCanvas');
            setTimeout(() => padObj && padObj.resize(), 50);
        } else if (modalId === 'modalProdSign') {
            const padObj = getOrCreatePad('prodCanvas', 'clearProdCanvas');
            setTimeout(() => padObj && padObj.resize(), 50);
        }
    }
    window.openIncidentModal = openIncidentModal;

    function closeIncidentModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('is-open');
        }
    }
    window.closeIncidentModal = closeIncidentModal;

    function quickStatusChange(newStatus) {
        if (!newStatus) return;
        const detailView = document.getElementById('incidentDetailView');
        const statusUrl = detailView ? detailView.dataset.statusUrl : '';
        if (!statusUrl) {
            console.error("URL d'action de statut d'incident manquante (data-status-url).");
            return;
        }

        const csrfToken = detailView ? detailView.dataset.csrfToken : (document.querySelector('input[name="csrf_token"]')?.value || '');

        const form = document.createElement('form');
        form.method = 'POST';
        form.action = statusUrl;

        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrf_token';
        csrfInput.value = csrfToken;
        form.appendChild(csrfInput);

        const statusInput = document.createElement('input');
        statusInput.type = 'hidden';
        statusInput.name = 'status';
        statusInput.value = newStatus;
        form.appendChild(statusInput);

        document.body.appendChild(form);
        form.submit();
    }
    window.quickStatusChange = quickStatusChange;

    function quickStatusSelect(newStatus) {
        if (newStatus === 'resolu' || newStatus === 'cloture') {
            const select = document.getElementById('quickResolveStatusSelect');
            if (select) select.value = newStatus;
            openIncidentModal('modalQuickResolve');
        } else {
            quickStatusChange(newStatus);
        }
    }
    window.quickStatusSelect = quickStatusSelect;

    function bindSignatureForm(formId, canvasId, dataInputId, alertMsg, loadingText) {
        const form = document.getElementById(formId);
        if (!form) return;
        let isSubmitting = false;

        form.addEventListener('submit', function (e) {
            if (isSubmitting) {
                e.preventDefault();
                return false;
            }
            const padObj = pads[canvasId];
            if (!padObj || !padObj.pad || padObj.pad.isEmpty()) {
                e.preventDefault();
                alert(alertMsg);
                return false;
            }
            const input = document.getElementById(dataInputId);
            if (input) input.value = padObj.pad.toDataURL('image/png');
            isSubmitting = true;
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = loadingText;
            }
        });
    }

    function initIncidentDetail() {
        const detailView = document.getElementById('incidentDetailView');
        if (!detailView) return;

        // Fermeture des modales : clic overlay ou touche Échap
        document.querySelectorAll('.incident-modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', function (e) {
                if (e.target === this) closeIncidentModal(this.id);
            });
        });

        window.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                document.querySelectorAll('.incident-modal-overlay').forEach(m => closeIncidentModal(m.id));
            }
        });

        bindSignatureForm('formBvSign', 'bvCanvas', 'bvSignatureData', 'Veuillez apposer votre visa manuscrit avant de valider.', 'Enregistrement en cours...');
        bindSignatureForm('formProdSign', 'prodCanvas', 'prodSignatureData', 'Veuillez recueillir la signature manuscrite avant de valider.', 'Scellement en cours...');
    }
    window.initIncidentDetail = initIncidentDetail;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initIncidentDetail);
    } else {
        initIncidentDetail();
    }
})();
