/**
 * modal-backdrop-guard.js — Empêche la fermeture accidentelle des modales.
 *
 * Problème : quand on sélectionne du texte dans un champ d'une modale et que la
 * souris est relâchée hors de la carte (sur le fond), le navigateur émet un
 * `click` dont la cible est le fond (ancêtre commun). Les handlers du type
 * `if (e.target === overlay) close()` ferment alors la modale.
 *
 * Solution globale : on mémorise les cibles de mousedown / mouseup et, en phase
 * de capture sur window (avant tout autre handler), on neutralise un clic dont
 * la cible est un fond plein écran (position fixed couvrant le viewport) si le
 * geste n'a pas commencé ET fini sur ce même fond.
 */
(function () {
    if (window.__bvModalBackdropGuard) return;
    window.__bvModalBackdropGuard = true;

    var downTarget = null;
    var upTarget = null;

    window.addEventListener('mousedown', function (e) { downTarget = e.target; upTarget = null; }, true);
    window.addEventListener('mouseup', function (e) { upTarget = e.target; }, true);

    function isFullscreenBackdrop(el) {
        if (!el || el.nodeType !== 1 || el === document.body || el === document.documentElement) return false;
        var style = window.getComputedStyle(el);
        if (style.position !== 'fixed') return false;
        var r = el.getBoundingClientRect();
        return r.left <= 1 && r.top <= 1 &&
            r.right >= window.innerWidth - 1 && r.bottom >= window.innerHeight - 1;
    }

    window.addEventListener('click', function (e) {
        var target = e.target;
        var start = downTarget;
        var end = upTarget;
        downTarget = null;
        upTarget = null;

        // Clic clavier / programmatique : pas de mousedown associé → on laisse passer.
        if (!start || e.detail === 0) return;
        if (start === target && (!end || end === target)) return;
        if (!isFullscreenBackdrop(target)) return;

        e.stopImmediatePropagation();
        e.preventDefault();
    }, true);
})();
