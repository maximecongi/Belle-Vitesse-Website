/**
 * project-billing.js — Section « Facturation » du formulaire projet ([data-billing]).
 * - factures multiples, lignes repliables : la ligne résume (n°, libellé, émission, matériel,
 *   montant HT), le détail contient la saisie ; « Ajouter une facture » clone le <template> (champs invoices-<n>-…) ;
 * - Montant total HT saisi ; ventilation par véhicule / tête coché dans la section Matériel ;
 *   « Autres prestations » = montant total − matériel (alerte si le matériel dépasse le total) ;
 * - fichier de facture : l'icône d'envoi ouvre le sélecteur, le fichier part à l'enregistrement du projet
 *   (copie locale + dossier 2_FACTURES sur kDrive) ; l'icône de téléchargement apparaît ensuite ;
 * - récapitulatif : total facturé, encaissé (factures « Payée »), reste à encaisser, barre de progression.
 */
(function (document) {
    'use strict';

    var euro = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', minimumFractionDigits: 2 });

    function parseAmount(raw) {
        var text = String(raw || '').replace(/[\s  €]/g, '').replace(',', '.');
        if (!text) return null;
        var n = Number(text);
        return isFinite(n) && n >= 0 ? n : NaN;
    }

    function parseIso(value) {
        var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ''));
        return m ? new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])) : null;
    }

    function iso(d) { return d.toISOString().slice(0, 10); }

    function short(value) {
        var d = parseIso(value);
        return d ? iso(d).slice(8, 10) + '/' + iso(d).slice(5, 7) : '';
    }

    function long(value) {
        var d = parseIso(value);
        return d ? short(value) + '/' + iso(d).slice(0, 4) : '';
    }

    function setOut(card, key, text) {
        card.querySelectorAll('[data-invoice-out="' + key + '"]').forEach(function (el) { el.textContent = text; });
    }

    function init() {
        var section = document.querySelector('[data-billing]');
        if (!section || section._billingBound) return;
        section._billingBound = true;
        var form = section.closest('form');
        var list = section.querySelector('[data-invoice-list]');
        var template = section.querySelector('[data-invoice-template]');
        var emptyHint = section.querySelector('[data-invoice-empty]');
        var counter = list.querySelectorAll('[data-invoice]').length;

        function cards() { return Array.prototype.slice.call(list.querySelectorAll('[data-invoice]')); }
        function field(card, key) { return card.querySelector('[data-invoice-in="' + key + '"]'); }

        function isChecked(type, id) {
            var name = type === 'vehicle' ? 'vehicle_ids' : 'head_ids';
            return Array.prototype.some.call(form.querySelectorAll('input[name="' + name + '"]:checked'),
                function (cb) { return cb.value === id; });
        }

        function syncRows(card) {
            var visible = 0;
            card.querySelectorAll('[data-billing-row]').forEach(function (row) {
                var on = isChecked(row.dataset.billingType, row.dataset.billingId);
                row.hidden = !on;
                row.querySelector('input').disabled = !on;
                if (on) visible += 1;
            });
            var hint = card.querySelector('[data-billing-empty]');
            if (hint) hint.hidden = visible > 0;
        }

        /** Met à jour la ligne résumé d'une facture ; retourne son montant HT. */
        function syncCard(card) {
            var equipment = 0;
            card.querySelectorAll('[data-billing-amount]').forEach(function (input) {
                if (input.disabled) return;
                var v = parseAmount(input.value);
                if (v) equipment += v;
            });
            var entered = parseAmount(card.querySelector('[data-invoice-amount]').value);
            // Montant total saisi ; à défaut, la somme du matériel
            var total = (entered === null || isNaN(entered)) ? equipment : entered;
            var other = total - equipment;
            card.querySelector('[data-billing-error]').hidden = !(other < -0.005);
            other = Math.max(other, 0);
            setOut(card, 'number', field(card, 'number').value.trim() || '—');
            setOut(card, 'label', field(card, 'label').value.trim() || '—');
            setOut(card, 'issued_on', long(field(card, 'issued_on').value) || '—');
            setOut(card, 'equipment', euro.format(equipment));
            setOut(card, 'other', euro.format(other));
            setOut(card, 'total', euro.format(total));
            return total;
        }

        function syncTotals() {
            var total = 0;
            var paid = 0;
            var all = cards();
            all.forEach(function (card) {
                var amount = syncCard(card);
                total += amount;
                if (card.querySelector('[data-invoice-paid]').checked) paid += amount;
            });
            var rate = total ? Math.round(100 * paid / total) : 0;
            emptyHint.hidden = all.length > 0;
            var head = section.querySelector('[data-invoice-head]');
            if (head) head.hidden = all.length === 0;
            section.querySelector('[data-invoice-total]').textContent = euro.format(total);
            section.querySelector('[data-invoice-paid-total]').textContent = euro.format(paid);
            section.querySelector('[data-invoice-due]').textContent = euro.format(Math.max(total - paid, 0));
            section.querySelector('[data-invoice-progress]').style.width = rate + '%';
            section.querySelector('[data-invoice-progress-label]').textContent =
                rate + ' % encaissé · ' + all.length + ' facture' + (all.length > 1 ? 's' : '');
        }

        function syncAll() {
            cards().forEach(syncRows);
            syncTotals();
        }

        function setOpen(card, open) {
            card.classList.toggle('is-open', open);
            card.querySelector('[data-invoice-detail]').hidden = !open;
            card.querySelector('[data-invoice-toggle]').setAttribute('aria-expanded', open ? 'true' : 'false');
        }

        /** Accordéon : une seule facture dépliée à la fois. */
        function openOnly(card) {
            cards().forEach(function (other) { setOpen(other, other === card); });
        }

        function addInvoice(values) {
            var idx = 'n' + (counter++);
            var wrapper = document.createElement('div');
            wrapper.innerHTML = template.innerHTML.replace(/__i__/g, idx).trim();
            var card = wrapper.firstElementChild;
            list.appendChild(card);
            values = values || {};
            Object.keys(values).forEach(function (key) {
                var input = field(card, key);
                if (input) input.value = values[key];
            });
            if (!field(card, 'issued_on').value) field(card, 'issued_on').value = iso(new Date());
            syncRows(card);
            if (window.lucide && window.lucide.createIcons) window.lucide.createIcons();
            return card;
        }

        section.querySelector('[data-invoice-add]').addEventListener('click', function () {
            var card = addInvoice();
            openOnly(card);
            syncTotals();
            var first = field(card, 'number');
            if (first) first.focus();
        });

        list.addEventListener('click', function (e) {
            var toggle = e.target.closest('[data-invoice-toggle]');
            if (toggle) {
                var c = toggle.closest('[data-invoice]');
                if (c.classList.contains('is-open')) setOpen(c, false);
                else openOnly(c);
                return;
            }
            var btn = e.target.closest('[data-invoice-remove]');
            if (!btn) return;
            var card = btn.closest('[data-invoice]');
            var filled = Array.prototype.some.call(card.querySelectorAll('input[type="text"]'),
                function (input) { return input.value.trim(); });
            if ((filled || card.querySelector('input[name$="-id"]')) && !window.confirm('Supprimer cette facture ?')) return;
            card.remove();
            syncTotals();
            form.dispatchEvent(new Event('change', { bubbles: true }));
        });

        list.addEventListener('change', function (e) {
            if (!e.target.matches('[data-invoice-file]')) return;
            var card = e.target.closest('[data-invoice]');
            var file = e.target.files && e.target.files[0];
            var name = card.querySelector('[data-invoice-file-name]');
            var upload = card.querySelector('[data-invoice-upload]');
            var download = card.querySelector('[data-invoice-download]');
            if (file) {
                name.textContent = file.name + ' — envoyé à l\'enregistrement';
                upload.hidden = false;
                upload.classList.add('is-pending');
                upload.title = file.name + ' (envoyé à l\'enregistrement)';
                if (download) download.hidden = true;
            }
        });

        form.addEventListener('change', function (e) {
            if (e.target.name === 'vehicle_ids' || e.target.name === 'head_ids') syncAll();
            if (e.target.matches && e.target.matches('[data-invoice-paid]')) syncTotals();
        });
        section.addEventListener('input', syncTotals);
        // Au chargement (ex. re-saisie après erreur), seule la première facture dépliée le reste
        var firstOpen = list.querySelector('[data-invoice].is-open');
        if (firstOpen) openOnly(firstOpen);
        syncAll();
    }

    window.initProjectBilling = init;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(document);
