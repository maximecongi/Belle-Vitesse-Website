/**
 * project-form.js — Contrôleur dynamique du formulaire de création et édition de projet.
 * Gère :
 * - L'initialisation du DatePicker Timeline unifié (ProjectTimelineDatePicker)
 * - Les sélecteurs enrichis Select2 pour les productions et contacts
 * - Les modales AJAX d'ajout rapide (Production & Contacts)
 * - La validation front-end avant soumission
 * - La détection en temps réel des conflits de réservation matériels (véhicules / têtes)
 */

(function () {
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

        // 3. Bascule d'état visuel sur les cartes à cocher
        $('.project-checkbox-card input[type="checkbox"]').off('change.cardHighlight').on('change.cardHighlight', function () {
            $(this).closest('.project-checkbox-card').toggleClass('selected', this.checked);
        });

        // 3b. Gestion sécurisée du bouton de suppression de projet
        $('#deleteProjectBtn').off('click.deleteProject').on('click.deleteProject', function (e) {
            e.preventDefault();
            if (confirm('Êtes-vous sûr de vouloir supprimer ce projet ? Cette action supprimera également son dossier sur kDrive.')) {
                const delForm = document.getElementById('deleteProjectForm');
                if (delForm) {
                    delForm.submit();
                }
            }
        });

        // Utilitaire générique pour insérer ou sélectionner une option dans un <select> / Select2 avec tri alphabétique
        function upsertSelectOption($select, id, text, selectIt) {
            if (!$select || !$select.length) return;
            const currentVal = $select.val();

            let $opt = $select.find("option[value='" + id + "']");
            if ($opt.length === 0) {
                $opt = $('<option>', { value: id, text: text });
                $select.append($opt);
            } else {
                $opt.text(text);
            }

            // Tri alphabétique des options (en préservant le placeholder value="" en première position)
            const $placeholder = $select.find('option[value=""]');
            const $options = $select.find('option[value!=""]').get();

            $options.sort(function (a, b) {
                return (a.text || '').localeCompare(b.text || '', 'fr', { sensitivity: 'base' });
            });

            $select.empty();
            if ($placeholder.length) {
                $select.append($placeholder);
            }
            $options.forEach(function (opt) {
                $select.append(opt);
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
                        upsertSelectOption($('#modalContactProduction'), response.id, response.name, false);
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

        // 5. Modale Contact Rapide
        $('.quick-add-contact-btn').off('click').on('click', function () {
            const targetSelectName = $(this).data('target');
            const defaultJob = $(this).data('job') || '';

            $('#modalTargetSelect').val(targetSelectName);
            $('#modalContactFirstName').val('');
            $('#modalContactLastName').val('');
            $('#modalContactMail').val('');
            $('#modalContactPhone').val('');
            const currentSelectedProd = $('#productionSelect').val() || '';
            if (targetSelectName === 'production_contact_id' && currentSelectedProd) {
                $('#modalContactProduction').val(currentSelectedProd);
            } else {
                $('#modalContactProduction').val('');
            }

            if (defaultJob) {
                $('#modalContactJob').val(defaultJob);
            } else {
                $('#modalContactJob').val('');
            }

            const $submitBtn = $('#submitContactModalBtn');
            $submitBtn.data('submitting', false).prop('disabled', false).text('Créer le contact');

            $('#quickContactModal').css('display', 'flex');
            setTimeout(function () {
                $('#modalContactFirstName').focus();
            }, 100);
        });

        function closeContactModal() {
            const $submitBtn = $('#submitContactModalBtn');
            $submitBtn.data('submitting', false).prop('disabled', false).text('Créer le contact');
            $('#quickContactModal').css('display', 'none');
        }

        $('#closeContactModalBtn, #cancelContactModalBtn').off('click').on('click', function () {
            closeContactModal();
        });

        $('#quickContactModal').off('click').on('click', function (e) {
            if (e.target === this) {
                closeContactModal();
            }
        });

        $(document).off('keydown.modalEscape').on('keydown.modalEscape', function (e) {
            if (e.key === 'Escape') {
                if ($('#quickProductionModal').is(':visible')) {
                    closeProductionModal();
                } else if ($('#quickContactModal').is(':visible')) {
                    closeContactModal();
                }
            }
        });

        $('#quickContactForm').off('submit').on('submit', function (e) {
            e.preventDefault();

            const $submitBtn = $('#submitContactModalBtn');
            // Verrou anti-double soumission
            if ($submitBtn.data('submitting') || $submitBtn.prop('disabled')) {
                return;
            }

            const firstName = ($('#modalContactFirstName').val() || '').trim();
            const lastName = ($('#modalContactLastName').val() || '').trim();
            const jobTitle = ($('#modalContactJob').val() || '').trim();
            const mail = ($('#modalContactMail').val() || '').trim();
            const phone = ($('#modalContactPhone').val() || '').trim();
            const productionId = $('#modalContactProduction').val();
            const targetSelectName = $('#modalTargetSelect').val();

            if (!firstName || !lastName) {
                alert("Le prénom et le nom sont requis.");
                return;
            }

            const csrfToken = $('input[name="csrf_token"]').val();
            $submitBtn.data('submitting', true).prop('disabled', true).text('Création...');

            $.ajax({
                url: "/admin/api/contacts/quick",
                type: "POST",
                contentType: "application/json",
                headers: {
                    "X-CSRFToken": csrfToken
                },
                data: JSON.stringify({
                    first_name: firstName,
                    last_name: lastName,
                    job_title: jobTitle,
                    mail: mail,
                    phone: phone,
                    production_id: productionId || null
                }),
                success: function (response) {
                    if (response && response.id) {
                        const contactSelectNames = [
                            'production_contact_id',
                            'dop_contact_id',
                            'pilot_contact_id',
                            'first_ac_contact_id',
                            'key_grip_contact_id'
                        ];

                        contactSelectNames.forEach(function (name) {
                            upsertSelectOption($('select[name="' + name + '"]'), response.id, response.name, name === targetSelectName);
                        });

                        closeContactModal();
                    } else {
                        alert("Une erreur est survenue lors de la création du contact.");
                    }
                },
                error: function (xhr) {
                    const errorMsg = xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : "Erreur serveur";
                    alert("Impossible de créer le contact : " + errorMsg);
                },
                complete: function () {
                    $submitBtn.data('submitting', false).prop('disabled', false).text('Créer le contact');
                }
            });
        });

        // 6. Validation front-end de la production requise
        $('form:not(#quickContactForm):not(#quickProductionForm)').on('submit', function (e) {
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
                const startDate = $('#departure_date_input').val() || $('#shoot_start_input').val();
                const endDate = $('#return_date_input').val() || $('#shoot_end_input').val() || startDate;
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
                    } catch (e) {}
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
                            data.conflicts_list.forEach(function (c) {
                                const itemLabel = (c.item_type === 'vehicle' ? '🏎️ ' : '🎥 ') + c.item_name;
                                $list.append(
                                    $('<li>').html(
                                        '<strong>' + itemLabel + '</strong> déjà réservé sur <em>' + c.project_name + '</em> (' + c.production + '), ' + c.period_label
                                    )
                                );

                                const $card = $('.project-checkbox-card[data-item-id="' + c.item_id + '"]');
                                $card.addClass('has-conflict');
                                $card.find('.conflict-placeholder').html(
                                    '<span class="conflict-badge" title="Déjà réservé par ' + c.production + ' (' + c.period_label + ')">⚠️ ' + c.project_name + '</span>'
                                );
                            });

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
