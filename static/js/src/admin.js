/**
 * admin.js — Orchestrateur central JavaScript pour l'administration Belle Vitesse.
 * Coordonne l'initialisation des modules spécialisés (navigation, flash, selects,
 * tables, graphiques, calendrier, formulaires projets & inspections, Cmd+K).
 *
 * Compatible Swup.js : init() est ré-exécuté après chaque transition de contenu.
 */

function init() {
    if (typeof window.initFlash === 'function') window.initFlash();
    if (typeof window.initSelects === 'function') window.initSelects();
    if (typeof window.initTables === 'function') window.initTables();
    if (typeof window.initDashboardCharts === 'function') window.initDashboardCharts();
    if (typeof window.initCalendar === 'function') window.initCalendar();
    if (typeof window.initProjectInteractions === 'function') window.initProjectInteractions();
    if (typeof window.initCmdK === 'function') window.initCmdK();
}

window.init = init;

// Déclenchement automatique au chargement du DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// Support Swup : réinitialisation après chaque remplacement de contenu
document.addEventListener('swup:contentReplaced', init);
