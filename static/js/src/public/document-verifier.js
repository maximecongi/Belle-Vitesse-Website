/**
 * document-verifier.js — Gestion du glisser-déposer (Drag & Drop) et de la sélection
 * de fichiers PDF sur les portails publics de vérification d'intégrité scellée.
 */

function initDocumentVerifier() {
    const pdfInput = document.getElementById('pdf-input');
    const fileNameDisp = document.getElementById('file-name');
    const submitBtn = document.getElementById('submit-btn');
    const uploadArea = document.getElementById('upload-area');

    if (!pdfInput || !fileNameDisp || !submitBtn || !uploadArea) return;
    if (uploadArea._hasVerifierListener) return;
    uploadArea._hasVerifierListener = true;

    pdfInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            fileNameDisp.textContent = "Fichier sélectionné : " + e.target.files[0].name;
            fileNameDisp.style.display = 'block';
            submitBtn.disabled = false;
            uploadArea.classList.add('is-active');
        } else {
            fileNameDisp.style.display = 'none';
            submitBtn.disabled = true;
            uploadArea.classList.remove('is-active');
        }
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.classList.add('is-active');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (eventName === 'dragleave') uploadArea.classList.remove('is-active');
        });
    });

    uploadArea.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt ? dt.files : null;
        if (files && files.length > 0) {
            pdfInput.files = files;
            pdfInput.dispatchEvent(new Event('change'));
        }
    });
}

window.initDocumentVerifier = initDocumentVerifier;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDocumentVerifier);
} else {
    initDocumentVerifier();
}
document.addEventListener('swup:contentReplaced', initDocumentVerifier);

