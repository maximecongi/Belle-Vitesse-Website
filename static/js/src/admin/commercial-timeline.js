/**
 * commercial-timeline.js — Timeline commerciale de la fiche projet.
 * - sélection d'une prise de contact (clic / clavier ←→) et affichage de son détail ;
 * - ouverture / fermeture du formulaire d'ajout ;
 * - champ « Motif de l'abandon » affiché et requis uniquement pour le type « Abandon » ;
 * - positionnement du segment « silence en cours » (data-ctl-start / data-ctl-end → --start / --end).
 * Les points eux-mêmes sont positionnés par data-bars.js (data-pct → --pct).
 */
(function (document) {
    'use strict';

    function init() {
        var root = document.querySelector('[data-commercial-timeline]');
        if (!root || root._ctlBound) return;
        root._ctlBound = true;

        root.querySelectorAll('[data-ctl-start]').forEach(function (el) {
            el.style.setProperty('--start', parseFloat(el.dataset.ctlStart) + '%');
            el.style.setProperty('--end', parseFloat(el.dataset.ctlEnd) + '%');
        });

        var dots = Array.prototype.slice.call(root.querySelectorAll('[data-ctl-event]'));

        function select(id, focus) {
            dots.forEach(function (d) {
                var on = d.dataset.ctlEvent === id;
                d.classList.toggle('is-selected', on);
                d.setAttribute('aria-pressed', on ? 'true' : 'false');
                if (on && focus) d.focus();
            });
            root.querySelectorAll('[data-ctl-detail]').forEach(function (p) {
                p.hidden = p.dataset.ctlDetail !== id;
            });
        }

        dots.forEach(function (dot, i) {
            dot.addEventListener('click', function () { select(dot.dataset.ctlEvent); });
            dot.addEventListener('keydown', function (e) {
                var next = null;
                if (e.key === 'ArrowRight') next = dots[i + 1];
                if (e.key === 'ArrowLeft') next = dots[i - 1];
                if (!next) return;
                e.preventDefault();
                select(next.dataset.ctlEvent, true);
            });
        });

        // Formulaire d'ajout
        var form = root.querySelector('[data-ctl-form]');
        var toggles = root.querySelectorAll('[data-ctl-toggle-form]');
        function setFormOpen(open) {
            if (!form) return;
            form.hidden = !open;
            toggles.forEach(function (t) {
                if (t.hasAttribute('aria-expanded')) t.setAttribute('aria-expanded', open ? 'true' : 'false');
            });
            if (open) {
                var first = form.querySelector('[data-ctl-type]');
                if (first) first.focus();
            }
        }
        toggles.forEach(function (t) {
            t.addEventListener('click', function () { setFormOpen(form.hidden); });
        });

        // Motif d'abandon
        var typeSelect = root.querySelector('[data-ctl-type]');
        var lostField = root.querySelector('[data-ctl-lost-field]');
        if (typeSelect && lostField) {
            var lostSelect = lostField.querySelector('select');
            var syncLost = function () {
                var isLost = typeSelect.value === 'lost';
                lostField.hidden = !isLost;
                lostSelect.disabled = !isLost;
                lostSelect.required = isLost;
            };
            typeSelect.addEventListener('change', syncLost);
            syncLost();
        }

        // Contact : « + Nouveau contact » affiche les champs de saisie (désactivés sinon, donc non envoyés)
        var contactSelect = root.querySelector('[data-ctl-contact]');
        var newContact = root.querySelector('[data-ctl-new-contact]');
        if (contactSelect && newContact) {
            var NEW_VALUE = contactSelect.querySelector('option[value^="__"]');
            var syncContact = function () {
                var isNew = NEW_VALUE && contactSelect.value === NEW_VALUE.value;
                newContact.hidden = !isNew;
                newContact.disabled = !isNew;
                if (isNew) {
                    var first = newContact.querySelector('input');
                    if (first) first.focus();
                }
            };
            var $ = window.jQuery;
            if ($ && $.fn && $.fn.select2) {
                // Liste longue (tout l'annuaire) : recherche au clavier
                $(contactSelect).select2({
                    width: '100%',
                    placeholder: contactSelect.dataset.placeholder || '',
                    dropdownParent: $(form)
                }).on('change', syncContact);
            } else {
                contactSelect.addEventListener('change', syncContact);
            }
            syncContact();
        }
    }

    window.initCommercialTimeline = init;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(document);
