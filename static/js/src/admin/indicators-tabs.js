/**
 * indicators-tabs.js — Onglets de la page Indicateurs (Commercial, Matériel, Incidents).
 * Les trois onglets sont rendus côté serveur ; seul le panneau affiché change, sans rechargement.
 * L'onglet est reporté dans l'URL (?tab=) et dans les liens de période, pour qu'un changement de
 * période, un rechargement ou un lien partagé rouvrent le même onglet.
 */
(function (window, document) {
    'use strict';

    function withTab(href, tab) {
        try {
            var url = new URL(href, window.location.href);
            url.searchParams.set('tab', tab);
            return url.pathname + url.search + url.hash;
        } catch (err) {
            return href;
        }
    }

    function select(tab) {
        var found = false;
        document.querySelectorAll('[data-ind-tab]').forEach(function (btn) {
            var active = btn.getAttribute('data-ind-tab') === tab;
            if (active) found = true;
            btn.setAttribute('aria-selected', active ? 'true' : 'false');
            btn.tabIndex = active ? 0 : -1;
        });
        if (!found) return;
        document.querySelectorAll('[data-ind-panel]').forEach(function (panel) {
            panel.hidden = panel.getAttribute('data-ind-panel') !== tab;
        });
        document.querySelectorAll('[data-ind-period-link]').forEach(function (a) {
            a.setAttribute('href', withTab(a.getAttribute('href'), tab));
        });
        try {
            window.history.replaceState(null, '', withTab(window.location.href, tab));
        } catch (err) { /* navigation ancienne : on garde simplement l'affichage */ }
    }

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-ind-tab]');
        if (btn) select(btn.getAttribute('data-ind-tab'));
    });

    // Flèches gauche / droite entre les onglets (motif ARIA « tabs »)
    document.addEventListener('keydown', function (e) {
        var btn = e.target.closest && e.target.closest('[data-ind-tab]');
        if (!btn || (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight')) return;
        var tabs = Array.prototype.slice.call(document.querySelectorAll('[data-ind-tab]'));
        var next = tabs[(tabs.indexOf(btn) + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
        e.preventDefault();
        next.focus();
        select(next.getAttribute('data-ind-tab'));
    });
})(window, document);
