/**
 * commercial-timeline.js — Timeline commerciale de la fiche projet.
 * - sélection d'une prise de contact (clic / clavier ←→) et affichage de son détail ;
 * - modale d'ajout (focus sur le type à l'ouverture, liste des contacts au-dessus de la modale) ;
 * - champ « Motif de l'abandon » affiché et requis uniquement pour le type « Abandon » ;
 * - choix « Déjà eu lieu / À venir » : types planifiables, bornes de date, titre et bouton adaptés ;
 * - positionnement des segments « silence en cours », zone et ligne « à venir » (data-ctl-start / data-ctl-end).
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

        // Modale d'ajout (ouverture / fermeture gérées par confirm-dialog.js via data-modal-open/close)
        var form = root.querySelector('[data-ctl-form]');
        var modal = document.getElementById('ctlModal');
        if (modal) {
            modal.addEventListener('admin-modal:open', function () {
                var first = form && form.querySelector('[data-ctl-type]');
                if (first) setTimeout(function () { first.focus(); }, 50);
            });
            modal.addEventListener('admin-modal:close', function () {
                var $ = window.jQuery;
                if ($ && $.fn && $.fn.select2) $(modal).find('[data-ctl-contact]').select2('close');
            });
        }

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

        // Contact : liste longue (tout l'annuaire) avec recherche au clavier.
        // L'encart « + Nouveau contact » est géré par contact-picker.js ([data-contact-picker]).
        var contactSelect = root.querySelector('[data-ctl-contact]');
        var $ = window.jQuery;
        if (contactSelect && $ && $.fn && $.fn.select2) {
            $(contactSelect).select2({
                width: '100%',
                placeholder: contactSelect.dataset.placeholder || '',
                // Rattachée au voile de la modale : la liste n'est pas rognée par le défilement du corps
                dropdownParent: $(modal || form)
            });
        }

        // ── Modes de la modale : ajout (vierge) ou modification (pré-remplie) ──
        if (!form || !modal) return;
        var titleEl = modal.querySelector('.admin-modal-title');
        var submitBtn = form.querySelector('[data-ctl-submit]');
        var defaults = {};
        Array.prototype.forEach.call(form.elements, function (el) {
            // Les boutons radio « Déjà eu lieu / À venir » sont gérés à part (setWhen)
            if (el.name && el.name !== 'csrf_token' && el.type !== 'radio') defaults[el.name] = el.value;
        });

        function setValue(name, value) {
            var el = form.elements[name];
            if (!el) return;
            el.value = value == null ? '' : value;
            var $ = window.jQuery;
            if (el === contactSelect && $ && $.fn && $.fn.select2) {
                $(el).trigger('change');
            } else {
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        // ── « Déjà eu lieu » / « À venir » : types proposés, bornes de date, libellés ──
        var today = form.dataset.today;
        var dateInput = form.elements.occurred_date;
        var isEditMode = false;

        function isPlanned() {
            var checked = form.querySelector('input[name="is_planned"]:checked');
            return !!checked && checked.value === '1';
        }

        function syncWhen() {
            var planned = isPlanned();
            if (typeSelect) {
                Array.prototype.forEach.call(typeSelect.options, function (opt) {
                    opt.disabled = planned ? !opt.hasAttribute('data-plannable') : opt.hasAttribute('data-planned-only');
                    opt.hidden = opt.disabled;
                });
                var current = typeSelect.options[typeSelect.selectedIndex];
                if (!current || current.disabled) {
                    var firstOk = Array.prototype.find.call(typeSelect.options, function (o) { return !o.disabled; });
                    if (firstOk) {
                        typeSelect.value = firstOk.value;
                        typeSelect.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
                typeSelect.querySelectorAll('optgroup').forEach(function (g) {
                    g.hidden = !Array.prototype.some.call(g.children, function (o) { return !o.disabled; });
                });
            }
            if (dateInput && today) {
                if (planned) {
                    dateInput.min = today;
                    dateInput.removeAttribute('max');
                    if (dateInput.value && dateInput.value < today) dateInput.value = today;
                } else {
                    dateInput.max = today;
                    dateInput.removeAttribute('min');
                    if (dateInput.value && dateInput.value > today) dateInput.value = today;
                }
            }
            if (titleEl) {
                titleEl.textContent = isEditMode
                    ? (planned ? 'Modifier l’événement prévu' : 'Modifier la prise de contact')
                    : (planned ? 'Planifier une prise de contact' : 'Nouvelle prise de contact');
            }
            if (submitBtn) submitBtn.textContent = isEditMode ? 'Enregistrer' : (planned ? 'Planifier' : 'Ajouter');
        }

        function setWhen(value) {
            var radio = form.querySelector('input[name="is_planned"][value="' + (value === '1' ? '1' : '0') + '"]');
            if (radio) radio.checked = true;
            syncWhen();
        }

        form.querySelectorAll('input[name="is_planned"]').forEach(function (r) {
            r.addEventListener('change', syncWhen);
        });

        function setMode(isEdit, action) {
            isEditMode = isEdit;
            form.action = action || form.dataset.createAction;
            var errorBox = form.querySelector('[data-ctl-form-error]');
            if (errorBox) errorBox.hidden = true;
            syncWhen();
        }

        // Ajout : formulaire remis à zéro (avant l'ouverture gérée par confirm-dialog.js)
        root.querySelectorAll('[data-ctl-create]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                Object.keys(defaults).forEach(function (name) { setValue(name, defaults[name]); });
                setWhen('0');
                setMode(false);
            });
        });

        // Modification / report : pré-remplissage depuis les données de l'événement
        root.querySelectorAll('[data-ctl-edit]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var data = {};
                try { data = JSON.parse(btn.dataset.ctlEditData || '{}'); } catch (e) { data = {}; }
                Object.keys(defaults).forEach(function (name) { setValue(name, defaults[name]); });
                setWhen(data.is_planned);
                setValue('event_type', data.event_type);
                setValue('occurred_date', data.date);
                setValue('occurred_time', data.time);
                setValue('contact_id', data.contact_id);
                setValue('lost_reason', data.lost_reason);
                setValue('summary', data.summary);
                setMode(true, btn.dataset.ctlEditAction);
                if (window.adminModal) window.adminModal.open('ctlModal');
                // Report d'un événement prévu : focus direct sur la date
                if (data.is_planned === '1' && dateInput) setTimeout(function () { dateInput.focus(); }, 80);
            });
        });

        syncWhen();
    }

    // ── Envoi sans rechargement (ajout, modification, suppression) ──
    // Le serveur renvoie le HTML de la carte redessinée : on la remplace puis on réinitialise ses comportements.

    function htmlToElement(html) {
        var tpl = document.createElement('template');
        tpl.innerHTML = (html || '').trim();
        return tpl.content.firstElementChild;
    }

    function notify(message, category) {
        if (message && typeof window.showFlash === 'function') window.showFlash(message, category || 'success');
    }

    function replaceCard(oldRoot, html, eventId) {
        var newRoot = htmlToElement(html);
        if (!newRoot) return;
        var $ = window.jQuery;
        if ($ && $.fn && $.fn.select2) {
            $(oldRoot).find('select').each(function () {
                if ($(this).data('select2')) $(this).select2('destroy');
            });
        }
        oldRoot.replaceWith(newRoot);
        if (typeof window.applyDataBars === 'function') window.applyDataBars(newRoot);
        if (window.lucide && typeof window.lucide.createIcons === 'function') window.lucide.createIcons();
        init();
        if (typeof window.initContactPickers === 'function') window.initContactPickers(newRoot);
        // Remet en avant le point (journée) qui contient la prise de contact ajoutée / modifiée
        var row = eventId != null && newRoot.querySelector('[data-ctl-item="' + eventId + '"]');
        var panel = row && row.closest('[data-ctl-detail]');
        var dot = panel && newRoot.querySelector('[data-ctl-event="' + panel.dataset.ctlDetail + '"]');
        if (dot) dot.click();
    }

    function submitAjax(form, submitter) {
        var root = form.closest('[data-commercial-timeline]');
        var errorBox = form.querySelector('[data-ctl-form-error]');
        var btn = submitter || form.querySelector('[type="submit"]');
        var label = btn ? btn.innerHTML : null;
        if (form._ctlSending) return;
        form._ctlSending = true;
        if (btn) btn.disabled = true;
        if (btn && form.hasAttribute('data-ctl-form')) btn.textContent = 'Enregistrement…';
        if (errorBox) errorBox.hidden = true;
        root.classList.add('is-busy');

        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' },
            credentials: 'same-origin'
        }).then(function (response) {
            return response.json().catch(function () { return {}; }).then(function (data) {
                if (!response.ok || data.status !== 'success') {
                    throw new Error(data.message || ('Erreur ' + response.status));
                }
                return data;
            });
        }).then(function (data) {
            if (window.adminModal && document.getElementById('ctlModal')) window.adminModal.close('ctlModal');
            replaceCard(root, data.html, data.event_id);
            notify(data.message, 'success');
        }).catch(function (err) {
            var message = (err && err.message) || 'Erreur réseau : la prise de contact n’a pas été enregistrée.';
            if (errorBox) {
                errorBox.textContent = message;
                errorBox.hidden = false;
            } else {
                notify(message, 'error');
            }
        }).then(function () {
            form._ctlSending = false;
            if (root) root.classList.remove('is-busy');
            if (btn && document.contains(btn)) {
                btn.disabled = false;
                btn.innerHTML = label;
            }
        });
    }

    // Écoute en phase de bouillonnement : la confirmation de suppression (confirm-dialog.js, en capture)
    // a déjà bloqué le premier envoi ; on ne traite que l'envoi confirmé ou un envoi direct.
    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement) || e.defaultPrevented) return;
        if (!form.hasAttribute('data-ctl-ajax') || !form.closest('[data-commercial-timeline]')) return;
        if (typeof window.fetch !== 'function') return; // repli : envoi classique
        e.preventDefault();
        submitAjax(form, e.submitter || null);
    });

    window.initCommercialTimeline = init;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(document);
