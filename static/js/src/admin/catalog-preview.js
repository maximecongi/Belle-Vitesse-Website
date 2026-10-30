/**
 * catalog-preview.js — Contrôleur de prévisualisation et mise à jour du catalogue PDF.
 * Gestion de l'état de chargement lors de la régénération du catalogue.
 */
document.addEventListener("DOMContentLoaded", () => {
    const updateBtn = document.querySelector('[data-action="update-catalog"]');
    if (!updateBtn) return;

    updateBtn.addEventListener("click", () => {
        updateBtn.classList.add("is-loading");
        updateBtn.setAttribute("aria-busy", "true");
        updateBtn.textContent = "Génération du PDF en cours...";

        const hintEl = document.querySelector(".preview-controls-hint");
        if (hintEl) {
            hintEl.textContent = "Génération du catalogue (environ 30 secondes)...";
        }
    });
});

