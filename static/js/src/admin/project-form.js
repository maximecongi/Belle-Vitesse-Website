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
        $('.project-checkbox-card input[type="checkbox"]').on('change', function () {
            $(this).closest('.project-checkbox-card').toggleClass('selected', this.checked);
        });

        // 4. Modale Production Rapide
        function openProductionModal() {
            $('#modalProdName').val('');
            $('#modalProdAddress').val('');
            $('#modalProdMail').val('');
            $('#modalProdPhone').val('');
            $('#quickProductionModal').css('display', 'flex');
            setTimeout(function () {
                $('#modalProdName').focus();
            }, 100);
        }

        function closeProductionModal() {
            $('#quickProductionModal').css('display', 'none');
        }

        $('#quickAddProductionBtn').on('click', function () {
            openProductionModal();
        });

        $('#closeProductionModalBtn, #cancelProductionModalBtn').on('click', function () {
            closeProductionModal();
        });

        $('#quickProductionModal').on('click', function (e) {
            if (e.target === this) {
                closeProductionModal();
            }
        });

        $('#quickProductionForm').on('submit', function (e) {
            e.preventDefault();

            const prodName = $('#modalProdName').val().trim();
            const prodAddress = $('#modalProdAddress').val().trim();
            const prodMail = $('#modalProdMail').val().trim();
            const prodPhone = $('#modalProdPhone').val().trim();

            if (!prodName) {
                alert("Le nom de la production est requis.");
                return;
            }

            const csrfToken = $('input[name="csrf_token"]').val();
            const $submitBtn = $('#submitProductionModalBtn');
            $submitBtn.prop('disabled', true).text('Création...');

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
                    $submitBtn.prop('disabled', false).text('Créer la production');
                    if (response && response.id) {
                        const $select = $('#productionSelect');
                        if ($select.find("option[value='" + response.id + "']").length === 0) {
                            const newOption = new Option(response.name, response.id, true, true);
                            $select.append(newOption);
                        } else {
                            $select.val(response.id);
                        }
                        $select.trigger('change');

                        // Mettre à jour aussi dans la modale de contact
                        const $modalProd = $('#modalContactProduction');
                        if ($modalProd.find("option[value='" + response.id + "']").length === 0) {
                            $modalProd.append(new Option(response.name, response.id));
                        }

                        closeProductionModal();
                    } else {
                        alert("Une erreur est survenue lors de la création de la production.");
                    }
                },
                error: function (xhr) {
                    $submitBtn.prop('disabled', false).text('Créer la production');
                    const errorMsg = xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : "Erreur serveur";
                    alert("Impossible de créer la production : " + errorMsg);
                }
            });
        });

        // 5. Modale Contact Rapide
        $('.quick-add-contact-btn').on('click', function () {
            const targetSelectName = $(this).data('target');
            const defaultJob = $(this).data('job') || '';

            $('#modalTargetSelect').val(targetSelectName);
            $('#modalContactFirstName').val('');
            $('#modalContactLastName').val('');
            $('#modalContactMail').val('');
            $('#modalContactPhone').val('');
            $('#modalContactProduction').val('');

            if (defaultJob) {
                $('#modalContactJob').val(defaultJob);
            } else {
                $('#modalContactJob').val('');
            }

            $('#quickContactModal').css('display', 'flex');
            setTimeout(function () {
                $('#modalContactFirstName').focus();
            }, 100);
        });

        function closeContactModal() {
            $('#quickContactModal').css('display', 'none');
        }

        $('#closeContactModalBtn, #cancelContactModalBtn').on('click', function () {
            closeContactModal();
        });

        $('#quickContactModal').on('click', function (e) {
            if (e.target === this) {
                closeContactModal();
            }
        });

        $(document).on('keydown', function (e) {
            if (e.key === 'Escape') {
                if ($('#quickProductionModal').is(':visible')) {
                    closeProductionModal();
                } else if ($('#quickContactModal').is(':visible')) {
                    closeContactModal();
                }
            }
        });

        $('#quickContactForm').on('submit', function (e) {
            e.preventDefault();

            const firstName = $('#modalContactFirstName').val().trim();
            const lastName = $('#modalContactLastName').val().trim();
            const jobTitle = $('#modalContactJob').val();
            const mail = $('#modalContactMail').val().trim();
            const phone = $('#modalContactPhone').val().trim();
            const productionId = $('#modalContactProduction').val();
            const targetSelectName = $('#modalTargetSelect').val();

            if (!firstName || !lastName) {
                alert("Le prénom et le nom sont requis.");
                return;
            }

            const csrfToken = $('input[name="csrf_token"]').val();
            const $submitBtn = $('#submitContactModalBtn');
            $submitBtn.prop('disabled', true).text('Création...');

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
                    $submitBtn.prop('disabled', false).text('Créer le contact');
                    if (response && response.id) {
                        const contactSelectNames = [
                            'production_contact_id',
                            'dop_contact_id',
                            'pilot_contact_id',
                            'first_ac_contact_id',
                            'key_grip_contact_id'
                        ];

                        contactSelectNames.forEach(function (name) {
                            const $sel = $('select[name="' + name + '"]');
                            if ($sel.length) {
                                const isTarget = (name === targetSelectName);
                                if ($sel.find("option[value='" + response.id + "']").length === 0) {
                                    const newOpt = new Option(response.name, response.id, isTarget, isTarget);
                                    $sel.append(newOpt);
                                }
                                if (isTarget) {
                                    $sel.val(response.id);
                                }
                                $sel.trigger('change');
                            }
                        });

                        closeContactModal();
                    } else {
                        alert("Une erreur est survenue lors de la création du contact.");
                    }
                },
                error: function (xhr) {
                    $submitBtn.prop('disabled', false).text('Créer le contact');
                    const errorMsg = xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : "Erreur serveur";
                    alert("Impossible de créer le contact : " + errorMsg);
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
        $('#departure_date_input, #shoot_start_input, #shoot_end_input, #return_date_input').on('change', checkBookingConflicts);

        // Observer les inputs cachés modifiés par ProjectTimelineDatePicker
        if (window.MutationObserver) {
            const dateObserver = new MutationObserver(checkBookingConflicts);
            ['departure_date_input', 'shoot_start_input', 'shoot_end_input', 'return_date_input'].forEach(function (id) {
                const el = document.getElementById(id);
                if (el) {
                    dateObserver.observe(el, { attributes: true, attributeFilter: ['value'] });
                }
            });
        }

        // Vérification initiale si on est en mode édition
        if (currentProjectId) {
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
