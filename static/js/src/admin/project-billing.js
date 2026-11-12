/**
 * project-billing.js — Section « Facturation » du formulaire projet ([data-billing]).
 * - une ligne de montant par véhicule / tête coché dans la section Matériel (les autres sont masquées
 *   et désactivées, donc non envoyées) ;
 * - récapitulatif en direct : total matériel et « Autres prestations » (montant global − matériel) ;
 * - alerte si la somme du matériel dépasse le montant global (le serveur refuse aussi ce cas).
 */
(function (document) {
    'use strict';

    var euro = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 2 });

    function parseAmount(raw) {
        var text = String(raw || '').replace(/[\s  €]/g, '').replace(',', '.');
        if (!text) return null;
        var n = Number(text);
        return isFinite(n) ? n : NaN;
    }

    function init() {
        var section = document.querySelector('[data-billing]');
        if (!section || section._billingBound) return;
        section._billingBound = true;
        var form = section.closest('form');
        var rows = Array.prototype.slice.call(section.querySelectorAll('[data-billing-row]'));
        var totalInput = section.querySelector('[data-billing-total]');
        var emptyHint = section.querySelector('[data-billing-empty]');
        var equipmentOut = section.querySelector('[data-billing-equipment]');
        var otherOut = section.querySelector('[data-billing-other]');
        var errorOut = section.querySelector('[data-billing-error]');

        function isChecked(type, id) {
            var name = type === 'vehicle' ? 'vehicle_ids' : 'head_ids';
            return Array.prototype.some.call(form.querySelectorAll('input[name="' + name + '"]:checked'),
                function (cb) { return cb.value === id; });
        }

        function syncRows() {
            var visible = 0;
            rows.forEach(function (row) {
                var on = isChecked(row.dataset.billingType, row.dataset.billingId);
                row.hidden = !on;
                row.querySelector('input').disabled = !on;
                if (on) visible += 1;
            });
            if (emptyHint) emptyHint.hidden = visible > 0;
        }

        function syncTotals() {
            var equipment = 0;
            var invalid = false;
            rows.forEach(function (row) {
                var input = row.querySelector('input');
                if (input.disabled) return;
                var v = parseAmount(input.value);
                if (v === null) return;
                if (isNaN(v) || v < 0) { invalid = true; return; }
                equipment += v;
            });
            var total = totalInput ? parseAmount(totalInput.value) : null;
            equipmentOut.textContent = equipment ? euro.format(equipment) : '—';
            if (total === null || isNaN(total)) {
                otherOut.textContent = '—';
                errorOut.hidden = true;
                return;
            }
            var other = total - equipment;
            otherOut.textContent = euro.format(Math.max(other, 0));
            errorOut.hidden = !(other < -0.005) || invalid;
        }

        function sync() { syncRows(); syncTotals(); }

        form.addEventListener('change', function (e) {
            if (e.target.name === 'vehicle_ids' || e.target.name === 'head_ids') sync();
        });
        section.addEventListener('input', syncTotals);
        sync();
    }

    window.initProjectBilling = init;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(document);
