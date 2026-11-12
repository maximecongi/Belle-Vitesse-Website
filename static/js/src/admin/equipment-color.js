/**
 * equipment-color.js — Sélecteur de la couleur d'identification fixe d'un véhicule / d'une tête
 * (page Flotte). Composant : templates/admin/_equipment_color.html.
 * Ouverture au clic, fermeture au clic extérieur ou Échap, enregistrement AJAX immédiat.
 */
(function (window, document) {
    'use strict';

    var COLOR_CLASS_PREFIX = 'eq-color-';

    // Ne retire que les classes de la palette (eq-color-<clé>), jamais celles du composant (eq-color-trigger…)
    function setColorClass(picker, el, color) {
        picker.querySelectorAll('[data-eq-color-choice]').forEach(function (sw) {
            el.classList.remove(COLOR_CLASS_PREFIX + sw.getAttribute('data-eq-color-choice'));
        });
        el.classList.add(COLOR_CLASS_PREFIX + color);
    }

    function closeAll(except) {
        document.querySelectorAll('[data-eq-color-picker]').forEach(function (picker) {
            if (picker === except) return;
            var pop = picker.querySelector('[data-eq-color-popover]');
            var btn = picker.querySelector('[data-eq-color-toggle]');
            if (pop) pop.hidden = true;
            if (btn) btn.setAttribute('aria-expanded', 'false');
        });
    }

    // Une couleur = un seul matériel : libère l'ancienne couleur et réserve la nouvelle
    // dans les sélecteurs des autres matériels de la page (« none » = sans couleur, jamais réservée).
    function syncTaken(picker, oldColor, newColor) {
        var owner = picker.getAttribute('data-equipment-name') || '';
        document.querySelectorAll('[data-eq-color-picker]').forEach(function (other) {
            if (other === picker) return;
            other.querySelectorAll('[data-eq-color-choice]').forEach(function (sw) {
                var key = sw.getAttribute('data-eq-color-choice');
                if (key === 'none') return; // « Sans couleur » : toujours disponible
                var name = sw.getAttribute('data-eq-color-name') || key;
                if (key === oldColor && oldColor !== newColor) {
                    sw.classList.remove('is-taken');
                    sw.disabled = false;
                    sw.title = name;
                    sw.setAttribute('aria-label', name);
                } else if (key === newColor && newColor !== 'none') {
                    sw.classList.add('is-taken');
                    sw.disabled = true;
                    sw.title = name + ' — utilisée par ' + owner;
                    sw.setAttribute('aria-label', name + ' (utilisée par ' + owner + ')');
                }
            });
        });
    }

    function save(picker, color, name) {
        var trigger = picker.querySelector('[data-eq-color-toggle]');
        var csrfMeta = document.querySelector('meta[name="csrf-token"]');
        trigger.classList.add('is-saving');
        return fetch(picker.getAttribute('data-url'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfMeta ? csrfMeta.getAttribute('content') : '',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                equipment_type: picker.getAttribute('data-equipment-type'),
                equipment_id: picker.getAttribute('data-equipment-id'),
                color: color
            })
        }).then(function (resp) {
            return resp.json().catch(function () { return {}; }).then(function (body) {
                if (!resp.ok || body.status !== 'success') {
                    throw new Error(body.message || 'La couleur n\'a pas pu être enregistrée.');
                }
                var previous = picker.querySelector('[data-eq-color-choice].is-selected');
                syncTaken(picker, previous ? previous.getAttribute('data-eq-color-choice') : null, body.color);
                setColorClass(picker, trigger, body.color);
                var label = picker.querySelector('[data-eq-color-label]');
                if (label) label.textContent = body.label || name;
                picker.querySelectorAll('[data-eq-color-choice]').forEach(function (sw) {
                    var selected = sw.getAttribute('data-eq-color-choice') === body.color;
                    sw.classList.toggle('is-selected', selected);
                    sw.setAttribute('aria-pressed', selected ? 'true' : 'false');
                });
            });
        }).catch(function (err) {
            if (typeof window.showFlash === 'function') window.showFlash(err.message, 'error');
        }).then(function () {
            trigger.classList.remove('is-saving');
        });
    }

    document.addEventListener('click', function (e) {
        var toggle = e.target.closest('[data-eq-color-toggle]');
        if (toggle) {
            e.preventDefault();
            var picker = toggle.closest('[data-eq-color-picker]');
            var pop = picker.querySelector('[data-eq-color-popover]');
            var willOpen = pop.hidden;
            closeAll(picker);
            pop.hidden = !willOpen;
            toggle.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
            if (willOpen) {
                var selected = pop.querySelector('.is-selected') || pop.querySelector('[data-eq-color-choice]');
                if (selected) selected.focus();
            }
            return;
        }
        var choice = e.target.closest('[data-eq-color-choice]');
        if (choice) {
            e.preventDefault();
            var isNone = choice.getAttribute('data-eq-color-choice') === 'none';
            if (!isNone && (choice.disabled || choice.classList.contains('is-taken'))) return;
            var p = choice.closest('[data-eq-color-picker]');
            closeAll();
            save(p, choice.getAttribute('data-eq-color-choice'), choice.getAttribute('data-eq-color-name'));
            var t = p.querySelector('[data-eq-color-toggle]');
            if (t) t.focus();
            return;
        }
        if (!e.target.closest('[data-eq-color-popover]')) closeAll();
    });

    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        var open = document.querySelector('[data-eq-color-popover]:not([hidden])');
        if (!open) return;
        var picker = open.closest('[data-eq-color-picker]');
        closeAll();
        var t = picker && picker.querySelector('[data-eq-color-toggle]');
        if (t) t.focus();
    });
})(window, document);
