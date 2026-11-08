/**
 * vehicle-sheet.js — Documents publics véhicule (fiche technique & règles de sécurité) :
 * bouton d'impression navigateur et synchronisation du lien PDF avec la langue active.
 * La bascule FR/EN elle-même est gérée par vehicle-safety-rules.js (classes partagées).
 */

function initVehicleDoc() {
    if (!document.body.classList.contains('vdoc-page')) return;

    document.querySelectorAll('[data-vdoc-action="print"]').forEach(btn => {
        btn.addEventListener('click', () => window.print());
    });

    const pdfLink = document.getElementById('vdocPdfLink');
    if (!pdfLink) return;
    const base = pdfLink.getAttribute('data-pdf-base');

    function syncPdfLink() {
        const lang = document.body.classList.contains('lang-en') ? 'en' : 'fr';
        pdfLink.setAttribute('href', `${base}?lang=${lang}&download=1`);
    }

    document.querySelectorAll('.safety-lang-btn').forEach(btn => {
        btn.addEventListener('click', syncPdfLink);
    });
    syncPdfLink();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVehicleDoc);
} else {
    initVehicleDoc();
}
