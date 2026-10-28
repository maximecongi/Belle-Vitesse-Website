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

    function handleFile(file) {
        if (!file) {
            fileNameDisp.textContent = "";
            fileNameDisp.style.display = 'none';
            fileNameDisp.classList.remove('is-error');
            submitBtn.disabled = true;
            uploadArea.classList.remove('is-active');
            return;
        }

        if (!file.name.toLowerCase().endsWith('.pdf')) {
            fileNameDisp.textContent = "Erreur : Seuls les fichiers PDF sont acceptés (" + file.name + ").";
            fileNameDisp.style.display = 'block';
            fileNameDisp.classList.add('is-error');
            submitBtn.disabled = true;
            uploadArea.classList.remove('is-active');
            return;
        }

        fileNameDisp.textContent = "Fichier sélectionné : " + file.name;
        fileNameDisp.style.display = 'block';
        fileNameDisp.classList.remove('is-error');
        submitBtn.disabled = false;
        uploadArea.classList.add('is-active');
    }

    pdfInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        } else {
            handleFile(null);
        }
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.classList.add('is-active');
        });
    });

    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!pdfInput.files || pdfInput.files.length === 0) {
            uploadArea.classList.remove('is-active');
        }
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const dt = e.dataTransfer;
        const files = dt ? dt.files : null;
        if (files && files.length > 0) {
            const file = files[0];
            try {
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                pdfInput.files = dataTransfer.files;
            } catch (_) {
                pdfInput.files = files;
            }
            handleFile(file);
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
