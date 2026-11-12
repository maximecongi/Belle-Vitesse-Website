/**
 * contact-picker.js — Sélecteurs de contact unifiés (templates/admin/_contact_picker.html).
 * Dans chaque bloc [data-contact-picker] : choisir « + Nouveau contact » dans [data-contact-select]
 * affiche l'encart [data-contact-new] (Prénom / Nom / Téléphone / Mail) et place le focus sur le prénom ;
 * toute autre valeur le masque et le désactive (champs non postés, « requis » ignoré).
 * Les listes Métier / Production de l'encart ([data-contact-search]) passent en Select2 avec recherche ;
 * celui de la liste de contacts reste à la charge de la page (dropdownParent propre à chaque contexte).
 */
(function (document) {
    'use strict';

    var NEW_VALUE = '__new__';

    function bind(picker) {
        if (picker._contactPickerBound) return;
        var select = picker.querySelector('[data-contact-select]');
        var fieldset = picker.querySelector('[data-contact-new]');
        if (!select || !fieldset) return;
        picker._contactPickerBound = true;

        var sync = function (focus) {
            var isNew = select.value === NEW_VALUE;
            var wasHidden = fieldset.hidden;
            fieldset.hidden = !isNew;
            fieldset.disabled = !isNew;
            if (isNew && wasHidden && focus) {
                var first = fieldset.querySelector('input');
                if (first) setTimeout(function () { first.focus(); }, 0);
            }
        };

        // Select2 déclenche « change » via jQuery (invisible pour addEventListener) : on écoute via jQuery si présent
        var $ = window.jQuery;
        if ($) {
            $(select).on('change', function () { sync(true); });
        } else {
            select.addEventListener('change', function () { sync(true); });
        }
        sync(false);
    }

    // Listes de l'encart (Métier / Rôle, Production rattachée) : Select2 avec recherche,
    // rattaché à la modale qui les contient pour que la liste ne soit ni rognée ni masquée
    function initSearchSelects(scope) {
        var $ = window.jQuery;
        if (!$ || !$.fn || !$.fn.select2) return;
        $(scope || document).find('select[data-contact-search]').each(function () {
            var $sel = $(this);
            if ($sel.data('select2')) return;
            var $modal = $sel.closest('.admin-modal-overlay');
            if ($modal.length && !$modal.data('contactSearchCloseBound')) {
                // Fermer la modale referme aussi une liste restée ouverte
                $modal.data('contactSearchCloseBound', true);
                $modal.on('admin-modal:close', function () {
                    $modal.find('select[data-contact-search]').each(function () {
                        if ($(this).data('select2')) $(this).select2('close');
                    });
                });
            }
            // Sans placeholder : l'option vide (« — Aucun métier — », « — Aucune / Freelance — »)
            // reste une option normale, affichée et sélectionnable dans la liste
            $sel.select2({
                width: '100%',
                dropdownParent: $modal.length ? $modal : $(document.body)
            });
        });
    }

    function init(scope) {
        (scope || document).querySelectorAll('[data-contact-picker]').forEach(bind);
        initSearchSelects(scope);
    }

    window.initContactPickers = init;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { init(); });
    } else {
        init();
    }
})(document);
