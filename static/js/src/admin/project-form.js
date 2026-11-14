/**
 * project-form.js — Contrôleur dynamique du formulaire de création et édition de projet.
 * Gère :
 * - L'initialisation du DatePicker Timeline unifié (ProjectTimelineDatePicker)
 * - Les sélecteurs enrichis Select2 pour les productions et contacts
 * - Les modales AJAX d'ajout rapide (Production & contacts de l'équipe)
 * - La validation front-end avant soumission
 * - La détection en temps réel des conflits de réservation matériels (véhicules / têtes)
 */

(function () {
    // Échappement des valeurs issues de la base (noms de projets, productions, matériel) avant insertion HTML
    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function initProjectForm() {
        if (typeof window.jQuery === 'undefined') return;
        const $ = window.jQuery;

        const $mainForm = $('#projectMainForm');
        const $pickerContainer = $('#projectDatePickerContainer');
        if (!$mainForm.length && !$pickerContainer.length) return;

        // Garde d'idempotence : éviter les enregistrements multiples d'écouteurs d'événements
        if ($mainForm.data('projectFormInitialized')) return;
        $mainForm.data('projectFormInitialized', true);

        // 1. Initialisation du DatePicker Timeline unifié pour les projets
        if ($pickerContainer.length && typeof window.ProjectTimelineDatePicker === 'function') {
            new window.ProjectTimelineDatePicker({
                container: '#projectDatePickerContainer',
                inputDepartureId: 'departure_date_input',
                inputShootStartId: 'shoot_start_input',
                inputShootEndId: 'shoot_end_input',
                inputReturnId: 'return_date_input'
            });
        }

        // 2. Select2 pour les sélecteurs de production et contacts
        if ($.fn.select2) {
            $('.searchable-select').select2({
                width: '100%',
                placeholder: function () {
                    return $(this).data('placeholder') || '';
                }
            });
        }

        // 2 bis. Référents plateau / Techniciens BV : étiquettes à choix multiples (métier affiché en gris dans la liste)
        if ($.fn.select2) {
            $('.bv-user-tags').each(function () {
                const $tags = $(this);
                $tags.select2({
                    width: '100%',
                    placeholder: $tags.data('placeholder') || '',
                    closeOnSelect: false,
                    templateResult: function (opt) {
                        if (!opt.id) return opt.text;
                        const job = $(opt.element).data('job');
                        const $row = $('<span class="bv-referent-option"></span>').text(opt.text);
                        if (job) $row.append($('<span class="bv-referent-option-job"></span>').text(job));
                        return $row;
                    }
                });
                // Menu laissé ouvert après sélection : vider la recherche et réafficher la liste complète
                $tags.on('select2:select', function () {
                    const s2 = $tags.data('select2');
                    if (!s2) return;
                    s2.$container.find('.select2-search__field').val('').trigger('input');
                });
            });
        }

        // 3. Bascule d'état visuel sur les cartes à cocher
        $('.project-checkbox-card input[type="checkbox"]').off('change.cardHighlight').on('change.cardHighlight', function () {
            $(this).closest('.project-checkbox-card').toggleClass('selected', this.checked);
        });

        // Utilitaire générique pour insérer ou sélectionner une option dans un <select> / Select2 avec tri alphabétique
        function upsertSelectOption($select, id, text, selectIt) {
            if (!$select || !$select.length) return;
            const currentVal = $select.val();

            // Les contacts peuvent être regroupés (optgroup « Tous les contacts ») : on insère et trie dans le groupe
            const $group = $select.children('optgroup').first();
            const $container = $group.length ? $group : $select;

            let $opt = $select.find("option[value='" + id + "']");
            if ($opt.length === 0) {
                $opt = $('<option>', { value: id, text: text });
                $container.append($opt);
            } else {
                $opt.text(text);
            }

            // Tri alphabétique ; « — » et « + Nouveau contact » restent en tête de liste
            const $pinned = $container.children('option[value=""], option[value="__new__"]');
            const $options = $container.children('option').not($pinned).get();
            $options.sort(function (a, b) {
                return (a.text || '').localeCompare(b.text || '', 'fr', { sensitivity: 'base' });
            });
            $options.forEach(function (opt) {
                $container.append(opt);
            });

            if (selectIt) {
                $select.val(id);
            } else if (currentVal !== null && currentVal !== undefined) {
                $select.val(currentVal);
            }
            $select.trigger('change');
        }

        // 4. Modale Production Rapide
        function openProductionModal() {
            $('#modalProdName').val('');
            $('#modalProdAddress').val('');
            $('#modalProdMail').val('');
            $('#modalProdPhone').val('');
            const $submitBtn = $('#submitProductionModalBtn');
            $submitBtn.data('submitting', false).prop('disabled', false).text('Créer la production');
            $('#quickProductionModal').css('display', 'flex');
            setTimeout(function () {
                $('#modalProdName').focus();
            }, 100);
        }

        function closeProductionModal() {
            const $submitBtn = $('#submitProductionModalBtn');
            $submitBtn.data('submitting', false).prop('disabled', false).text('Créer la production');
            $('#quickProductionModal').css('display', 'none');
        }

        $('#quickAddProductionBtn').off('click').on('click', function () {
            openProductionModal();
        });

        $('#closeProductionModalBtn, #cancelProductionModalBtn').off('click').on('click', function () {
            closeProductionModal();
        });

        $('#quickProductionModal').off('click').on('click', function (e) {
            if (e.target === this) {
                closeProductionModal();
            }
        });

        $('#quickProductionForm').off('submit').on('submit', function (e) {
            e.preventDefault();

            const $submitBtn = $('#submitProductionModalBtn');
            if ($submitBtn.data('submitting') || $submitBtn.prop('disabled')) {
                return;
            }

            const prodName = ($('#modalProdName').val() || '').trim();
            const prodAddress = ($('#modalProdAddress').val() || '').trim();
            const prodMail = ($('#modalProdMail').val() || '').trim();
            const prodPhone = ($('#modalProdPhone').val() || '').trim();

            if (!prodName) {
                alert("Le nom de la production est requis.");
                return;
            }

            const csrfToken = $('input[name="csrf_token"]').val();
            $submitBtn.data('submitting', true).prop('disabled', true).text('Création...');

            $.ajax({
                url: "/admin/api/productions/quick",
                type: "POST",
                contentType: "application/json",
                headers: {
                    "X-CSRFToken": csrfToken
                },
                data: JSON.stringify({
                    name: prodName,
                    address: prodAddress || null,
                    mail: prodMail || null,
                    phone: prodPhone || null
                }),
                success: function (response) {
                    if (response && response.id) {
                        upsertSelectOption($('#productionSelect'), response.id, response.name, true);
                        upsertSelectOption($('#teamContactNewProduction'), response.id, response.name, false);
                        closeProductionModal();
                    } else {
                        alert("Une erreur est survenue lors de la création de la production.");
                    }
                },
                error: function (xhr) {
                    const errorMsg = xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : "Erreur serveur";
                    alert("Impossible de créer la production : " + errorMsg);
                },
                complete: function () {
                    $submitBtn.data('submitting', false).prop('disabled', false).text('Créer la production');
                }
            });
        });

        // 5. Sélecteurs de contact de l'équipe : « + Nouveau contact » ouvre la modale #teamContactModal
        //    (même saisie que la timeline commerciale). Le contact est créé tout de suite
        //    (/admin/api/contacts/quick), ajouté à toutes les listes de l'équipe et sélectionné.
        const NEW_CONTACT = '__new__';
        const $teamSelects = $('select[data-team-contact]');
        const $teamModal = $('#teamContactModal');
        const $teamForm = $('#teamContactForm');
        let $teamTarget = null;

        $teamSelects.each(function () {
            const $sel = $(this);
            $sel.data('prevValue', $sel.val() === NEW_CONTACT ? '' : ($sel.val() || ''));
        });

        function openTeamContactModal($sel) {
            $teamTarget = $sel;
            $teamForm[0].reset();
            const role = $sel.data('contactRole') || '';
            $teamForm.find('[data-contact-new-suffix]').text(role ? ' · ' + role : '');
            // Production rattachée : au choix ; proposée d'office pour le contact de production uniquement
            const projectProd = $('#productionSelect').val() || '';
            $('#teamContactNewProduction').val($sel.attr('name') === 'production_contact_id' ? projectProd : '').trigger('change.select2');
            // Métier : au choix, proposé d'après le rôle du champ
            $('#teamContactNewJob').val($sel.data('contactJob') || '').trigger('change.select2');
            $teamForm.find('[data-team-contact-submit]').prop('disabled', false).text('Créer le contact');
            if (window.adminModal) window.adminModal.open('teamContactModal');
        }

        $teamSelects.on('change.teamContact', function () {
            const $sel = $(this);
            if ($sel.val() !== NEW_CONTACT) {
                $sel.data('prevValue', $sel.val() || '');
                return;
            }
            // L'option « + Nouveau contact » n'est jamais conservée : on revient à la valeur précédente
            $sel.val($sel.data('prevValue') || '').trigger('change.select2');
            if ($sel.data('select2')) $sel.select2('close');
            openTeamContactModal($sel);
        });

        $teamModal.on('admin-modal:open', function () {
            setTimeout(function () { $teamForm.find('input').first().trigger('focus'); }, 50);
        });

        $teamForm.on('submit', function (e) {
            e.preventDefault();
            const $submit = $teamForm.find('[data-team-contact-submit]');
            if ($submit.prop('disabled') || !$teamTarget) return;

            const field = function (key) { return ($teamForm.find('[name="team_contact_' + key + '"]').val() || '').trim(); };
            const firstName = field('first_name');
            const lastName = field('last_name');
            if (!firstName || !lastName) {
                const $missing = $teamForm.find(firstName ? '[name="team_contact_last_name"]' : '[name="team_contact_first_name"]');
                $missing[0].reportValidity ? $missing[0].reportValidity() : alert('Le prénom et le nom sont requis.');
                $missing.trigger('focus');
                return;
            }

            $submit.prop('disabled', true).text('Création…');
            $.ajax({
                url: '/admin/api/contacts/quick',
                type: 'POST',
                contentType: 'application/json',
                headers: { 'X-CSRFToken': $('input[name="csrf_token"]').val() },
                data: JSON.stringify({
                    first_name: firstName,
                    last_name: lastName,
                    phone: field('phone'),
                    mail: field('mail'),
                    job_title: $('#teamContactNewJob').val() || '',
                    production_id: $('#teamContactNewProduction').val() || null
                }),
                success: function (response) {
                    if (!response || !response.id) {
                        alert('Une erreur est survenue lors de la création du contact.');
                        return;
                    }
                    const $target = $teamTarget;
                    $teamSelects.each(function () {
                        upsertSelectOption($(this), response.id, response.name, this === $target[0]);
                    });
                    if (window.adminModal) window.adminModal.close('teamContactModal');
                },
                error: function (xhr) {
                    const msg = xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : 'Erreur serveur';
                    alert('Impossible de créer le contact : ' + msg);
                },
                complete: function () {
                    $submit.prop('disabled', false).text('Créer le contact');
                }
            });
        });

        $(document).off('keydown.modalEscape').on('keydown.modalEscape', function (e) {
            if (e.key === 'Escape' && $('#quickProductionModal').is(':visible')) {
                closeProductionModal();
            }
        });

        // 6. Validation front-end de la production requise
        $('form:not(#quickProductionForm):not(#teamContactForm)').on('submit', function (e) {
            if (document.activeElement && document.activeElement.getAttribute('formaction') && document.activeElement.getAttribute('formaction').includes('/delete')) {
                return;
            }

            const productionSelect = $('#productionSelect');
            if (productionSelect.length && !productionSelect.val()) {
                e.preventDefault();
                alert('Veuillez sélectionner une production.');
                if (productionSelect.data('select2')) {
                    productionSelect.select2('open');
                } else {
                    productionSelect.focus();
                }
            }
        });

        // 7. Détection en temps réel des conflits de réservation
        let conflictCheckTimer = null;
        const currentProjectId = ($mainForm.length && $mainForm.data('projectId')) ? String($mainForm.data('projectId')) : ($('#current_project_id').val() || '');

        function checkBookingConflicts() {
            clearTimeout(conflictCheckTimer);
            conflictCheckTimer = setTimeout(function () {
                const startDate = $('#shoot_start_input').val() || $('#departure_date_input').val();
                const endDate = $('#shoot_end_input').val() || $('#return_date_input').val() || startDate;
                const dateMode = $('#date_mode_input').val() || 'continuous';
                const isImmobilized = $('#is_immobilized_between_input').val() !== 'false';
                const shootDates = $('#shoot_dates_input').val() || '[]';

                const selectedVehicles = [];
                $('input[name="vehicle_ids"]:checked').each(function () {
                    selectedVehicles.push($(this).val());
                });

                const selectedHeads = [];
                $('input[name="head_ids"]:checked').each(function () {
                    selectedHeads.push($(this).val());
                });

                if (!startDate || (selectedVehicles.length === 0 && selectedHeads.length === 0)) {
                    $('#bookingConflictsAlert').slideUp(200);
                    $('.project-checkbox-card').removeClass('has-conflict');
                    $('.conflict-placeholder').empty();
                    return;
                }

                let interShootStatuses = [];
                const interStatusesVal = $('#inter_shoot_statuses_input').val();
                if (interStatusesVal) {
                    try {
                        interShootStatuses = JSON.parse(interStatusesVal);
                    } catch (e) { }
                }

                const csrfToken = $('input[name="csrf_token"]').val();

                $.ajax({
                    url: "/admin/api/projects/check-conflicts",
                    type: "POST",
                    contentType: "application/json",
                    headers: {
                        "X-CSRFToken": csrfToken
                    },
                    data: JSON.stringify({
                        start_date: startDate,
                        end_date: endDate,
                        // Jours de départ et de retour : le matériel est déjà / encore mobilisé
                        departure_date: $('#departure_date_input').val() || null,
                        return_date: $('#return_date_input').val() || null,
                        date_mode: dateMode,
                        is_immobilized_between: isImmobilized,
                        shoot_dates: shootDates,
                        inter_shoot_statuses: interShootStatuses,
                        vehicle_ids: selectedVehicles,
                        head_ids: selectedHeads,
                        project_id: currentProjectId || null
                    }),
                    success: function (res) {
                        if (!res || !res.data) return;
                        const data = res.data;

                        $('.project-checkbox-card').removeClass('has-conflict');
                        $('.conflict-placeholder').empty();

                        if (data.has_conflicts) {
                            $('#bookingConflictsSummary').text(
                                data.total_conflicts + " conflit(s) détecté(s) pour les dates sélectionnées :"
                            );

                            const $list = $('#bookingConflictsDetailsList').empty();

                            // 1. Marquer individuellement les cartes des équipements en conflit
                            data.conflicts_list.forEach(function (c) {
                                const $card = $('.project-checkbox-card').filter(function () { return String($(this).data('itemId')) === String(c.item_id); });
                                $card.addClass('has-conflict');
                                $card.find('.conflict-placeholder').html(
                                    '<span class="conflict-badge" title="Déjà réservé par ' + escapeHtml(c.production) + ' (' + escapeHtml(c.period_label) + ')"><i data-lucide="triangle-alert"></i> ' + escapeHtml(c.project_name) + '</span>'
                                );
                            });

                            // 2. Regrouper les équipements en conflit par tournage
                            const conflictsByProject = {};
                            data.conflicts_list.forEach(function (c) {
                                const projectKey = String(c.project_id || c.project_name);
                                if (!conflictsByProject[projectKey]) {
                                    conflictsByProject[projectKey] = {
                                        project_id: c.project_id,
                                        project_name: c.project_name,
                                        production: c.production,
                                        period_label: c.period_label,
                                        items: []
                                    };
                                }
                                const exists = conflictsByProject[projectKey].items.some(function (it) {
                                    return String(it.item_id) === String(c.item_id) && it.item_type === c.item_type;
                                });
                                if (!exists) {
                                    conflictsByProject[projectKey].items.push({
                                        item_id: c.item_id,
                                        item_name: c.item_name,
                                        item_type: c.item_type
                                    });
                                }
                            });

                            // 3. Générer un unique .booking-conflict-row par tournage
                            Object.keys(conflictsByProject).forEach(function (key) {
                                const group = conflictsByProject[key];

                                const itemsHtml = group.items.map(function (item) {
                                    const isVehicle = item.item_type === 'vehicle';
                                    const iconName = isVehicle ? 'car' : 'bot';
                                    const pillClass = isVehicle ? 'booking-conflict-pill--vehicle' : 'booking-conflict-pill--head';
                                    return (
                                        '<span class="booking-conflict-pill ' + pillClass + '">' +
                                        '<i data-lucide="' + iconName + '" class="u-w-14 u-h-14"></i>' +
                                        '<span>' + escapeHtml(item.item_name) + '</span>' +
                                        '</span>'
                                    );
                                }).join('');

                                const $item = $('<div>').addClass('booking-conflict-row').html(
                                    '<div class="booking-conflict-row-equipment">' +
                                    itemsHtml +
                                    '</div>' +
                                    '<div class="booking-conflict-row-details">' +
                                    '<span class="booking-conflict-row-project">' +
                                    '<i data-lucide="clapperboard" class="u-w-12 u-h-12 u-text-project"></i> ' +
                                    '<strong>' + escapeHtml(group.project_name) + '</strong>' +
                                    (group.production ? ' <span class="booking-conflict-production">(' + escapeHtml(group.production) + ')</span>' : '') +
                                    '</span>' +
                                    '<span class="booking-conflict-row-period">' +
                                    '<i data-lucide="calendar" class="u-w-12 u-h-12"></i> ' +
                                    escapeHtml(group.period_label) +
                                    '</span>' +
                                    '</div>'
                                );
                                $list.append($item);
                            });

                            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                                window.lucide.createIcons();
                            }

                            $('#bookingConflictsAlert').slideDown(250);
                        } else {
                            $('#bookingConflictsAlert').slideUp(200);
                        }
                    },
                    error: function (err) {
                        console.warn("Vérification des conflits indisponible :", err);
                    }
                });
            }, 300);
        }

        $('input[name="vehicle_ids"], input[name="head_ids"]').on('change', checkBookingConflicts);

        $('#departure_date_input, #shoot_start_input, #shoot_end_input, #return_date_input, #date_mode_input, #is_immobilized_between_input, #shoot_dates_input, #inter_shoot_statuses_input').on('change', checkBookingConflicts);

        // Observer les inputs cachés modifiés par ProjectTimelineDatePicker
        if (window.MutationObserver) {
            const dateObserver = new MutationObserver(checkBookingConflicts);
            [
                'departure_date_input',
                'shoot_start_input',
                'shoot_end_input',
                'return_date_input',
                'date_mode_input',
                'is_immobilized_between_input',
                'shoot_dates_input',
                'inter_shoot_statuses_input'
            ].forEach(function (id) {
                const el = document.getElementById(id);
                if (el) {
                    dateObserver.observe(el, { attributes: true, attributeFilter: ['value'] });
                }
            });
        }

        // Vérification initiale si on est en mode édition ou duplication (équipements pré-sélectionnés)
        if (currentProjectId || $('input[name="vehicle_ids"]:checked').length > 0 || $('input[name="head_ids"]:checked').length > 0) {
            setTimeout(checkBookingConflicts, 400);
        }
    }
    window.initProjectForm = initProjectForm;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initProjectForm);
    } else {
        initProjectForm();
    }
})();
