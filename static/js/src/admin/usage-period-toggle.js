/**
 * usage-period-toggle.js — Bascule de période (30 derniers jours / année en cours) du classement
 * « Jours utilisés par matériel » (page Flotte), sans rechargement : les deux périodes sont
 * rendues côté serveur, seul le panneau affiché change. L'URL est mise à jour (?usage_period=)
 * pour que le choix survive à un rechargement ou à un partage de lien.
 */
(function (window, document) {
    'use strict';

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-usage-period]');
        if (!btn) return;
        var root = btn.closest('[data-usage-period-root]');
        if (!root) return;
        var period = btn.getAttribute('data-usage-period');

        root.querySelectorAll('[data-usage-period]').forEach(function (b) {
            var active = b === btn;
            b.setAttribute('aria-pressed', active ? 'true' : 'false');
            b.classList.toggle('admin-btn-primary', active);
            b.classList.toggle('admin-btn-quaternary', !active);
        });
        root.querySelectorAll('[data-usage-period-panel]').forEach(function (panel) {
            panel.hidden = panel.getAttribute('data-usage-period-panel') !== period;
        });

        try {
            var url = new URL(window.location.href);
            url.searchParams.set('usage_period', period);
            window.history.replaceState(null, '', url.toString());
        } catch (err) { /* navigation ancienne : on garde simplement l'affichage */ }
    });
})(window, document);
