/**
 * data-bars.js — Barres de graphiques sans style inline dans les templates :
 * chaque élément [data-pct] reçoit la variable CSS --pct (0–100 %), que le CSS
 * consomme en largeur (barres horizontales) ou en hauteur (colonnes).
 */
(function (document) {
    'use strict';

    function applyBars(root) {
        (root || document).querySelectorAll('[data-pct]').forEach(function (el) {
            var v = parseFloat(el.getAttribute('data-pct'));
            if (isNaN(v)) v = 0;
            el.style.setProperty('--pct', Math.max(0, Math.min(100, v)) + '%');
        });
    }

    window.applyDataBars = applyBars;
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { applyBars(); });
    } else {
        applyBars();
    }
})(document);
