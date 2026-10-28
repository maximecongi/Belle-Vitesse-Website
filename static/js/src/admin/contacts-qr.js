/**
 * contacts-qr.js — Gestion du QR code vCard et du téléchargement des fiches contacts.
 */

function initContactsQr() {
    const modal = document.getElementById('qrModal');
    const modalName = document.getElementById('qrModalName');
    const modalCode = document.getElementById('qrModalCode');
    const modalDownload = document.getElementById('qrModalDownload');

    if (!modal || !modalName || !modalCode || !modalDownload) return;

    let currentVcfB64 = '';
    let currentFilename = '';

    function renderQR(container, text, size) {
        if (typeof qrcode === 'undefined') return;
        const qr = qrcode(0, 'L');
        qr.addData(text);
        qr.make();
        const cellSize = Math.floor(size / qr.getModuleCount());
        const img = document.createElement('img');
        img.src = qr.createDataURL(cellSize, 0);
        img.style.width = size + 'px';
        img.style.height = size + 'px';
        container.appendChild(img);
    }

    document.querySelectorAll('.qr-trigger').forEach(trigger => {
        if (trigger._hasQrListener) return;
        trigger._hasQrListener = true;

        trigger.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();

            modalName.textContent = trigger.dataset.name || '';
            modalCode.innerHTML = '';
            currentVcfB64 = trigger.dataset.vcf || '';
            currentFilename = trigger.dataset.filename || 'contact.vcf';
            try {
                const vcfText = decodeURIComponent(escape(atob(currentVcfB64)));
                renderQR(modalCode, vcfText, 260);
                modal.style.display = 'flex';
            } catch (err) {
                console.error("Erreur décodage vCard:", err);
            }
        });
    });

    if (!modalDownload._hasDownloadListener) {
        modalDownload._hasDownloadListener = true;
        modalDownload.addEventListener('click', function () {
            if (!currentVcfB64) return;
            try {
                const raw = atob(currentVcfB64);
                const blob = new Blob([raw], { type: 'text/vcard' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = currentFilename;
                a.click();
                URL.revokeObjectURL(url);
            } catch (err) {
                console.error("Erreur téléchargement vCard:", err);
            }
        });
    }

    if (!modal._hasCloseListener) {
        modal._hasCloseListener = true;
        modal.addEventListener('click', function (e) {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && modal.style.display === 'flex') {
                modal.style.display = 'none';
            }
        });
    }
}

window.initContactsQr = initContactsQr;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initContactsQr);
} else {
    initContactsQr();
}
document.addEventListener('swup:contentReplaced', initContactsQr);

