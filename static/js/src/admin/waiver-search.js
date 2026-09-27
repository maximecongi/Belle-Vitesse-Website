/**
 * waiver-search.js — Recherche autocomplétée de projet pour les formulaires de décharge
 * Filtre les projets disponibles dès 2 caractères tapés avec navigation clavier et sélection enrichie.
 */
(function () {
    'use strict';

    function initWaiverSearch() {
        var dataScript = document.getElementById('projectsData');
        var hiddenInput = document.getElementById('selectedProjectId');
        var searchInput = document.getElementById('projectSearchInput');
        var clearBtn = document.getElementById('clearSearchBtn');
        var dropdown = document.getElementById('waiverDropdown');
        var resultsList = document.getElementById('waiverResultsList');
        var resultsCount = document.getElementById('resultsCount');
        var searchContainer = document.getElementById('waiverSearchContainer');
        var selectedCard = document.getElementById('waiverSelectedCard');
        var selectedName = document.getElementById('selectedProjectName');
        var selectedProd = document.getElementById('selectedProjectProd');
        var selectedDates = document.getElementById('selectedProjectDates');
        var selectedPilot = document.getElementById('selectedProjectPilot');
        var changeBtn = document.getElementById('changeProjectBtn');
        var submitBtn = document.getElementById('submitWaiverBtn');
        var helperText = document.getElementById('searchHelperText');

        if (!dataScript || !hiddenInput || !searchInput || !dropdown) {
            return;
        }

        var projects = [];
        try {
            projects = JSON.parse(dataScript.textContent || '[]');
        } catch (e) {
            console.error('Erreur de parsing des données projets:', e);
            return;
        }

        var highlightedIndex = -1;
        var currentFiltered = [];

        function normalizeStr(str) {
            return (str || '')
                .toString()
                .toLowerCase()
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '')
                .trim();
        }

        function escapeHtml(str) {
            var div = document.createElement('div');
            div.textContent = str || '';
            return div.innerHTML;
        }

        function selectProject(proj) {
            if (!proj) return;
            hiddenInput.value = proj.id;
            selectedName.textContent = proj.name;
            selectedProd.textContent = proj.production || 'Sans production';

            var datesSpan = selectedDates.querySelector('span');
            if (datesSpan) {
                datesSpan.textContent = proj.dates || 'Dates non définies';
            }

            if (selectedPilot) {
                var person = proj.pilot || proj.contact;
                if (person) {
                    var personSpan = selectedPilot.querySelector('span');
                    if (personSpan) personSpan.textContent = person;
                    selectedPilot.classList.remove('u-d-none');
                } else {
                    selectedPilot.classList.add('u-d-none');
                }
            }

            searchContainer.classList.add('u-d-none');
            selectedCard.classList.remove('u-d-none');
            dropdown.classList.add('u-d-none');

            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.classList.remove('is-disabled');
            }

            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }

        function unselectProject() {
            hiddenInput.value = '';
            selectedCard.classList.add('u-d-none');
            searchContainer.classList.remove('u-d-none');

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.classList.add('is-disabled');
            }

            searchInput.value = '';
            clearBtn.classList.add('u-d-none');
            dropdown.classList.add('u-d-none');
            highlightedIndex = -1;
            currentFiltered = [];

            if (helperText) {
                helperText.classList.remove('u-d-none');
            }

            setTimeout(function () {
                searchInput.focus();
            }, 50);
        }

        function renderDropdown(items, query) {
            resultsList.innerHTML = '';
            currentFiltered = items;
            highlightedIndex = -1;

            if (items.length === 0) {
                var emptyDiv = document.createElement('div');
                emptyDiv.className = 'waiver-results-empty';
                emptyDiv.innerHTML = 'Aucun projet trouvé pour « <strong>' + escapeHtml(query) + '</strong> »';
                resultsList.appendChild(emptyDiv);
                if (resultsCount) resultsCount.textContent = '0';
            } else {
                if (resultsCount) resultsCount.textContent = items.length.toString();

                items.forEach(function (proj, idx) {
                    var itemEl = document.createElement('div');
                    itemEl.className = 'waiver-search-item';
                    itemEl.dataset.id = proj.id;
                    itemEl.dataset.index = idx;
                    itemEl.setAttribute('role', 'option');

                    var personInfo = proj.pilot || proj.contact;
                    var personHtml = personInfo ? '<span class="waiver-item-meta-entry"><i data-lucide="user"></i> ' + escapeHtml(personInfo) + '</span>' : '';

                    itemEl.innerHTML =
                        '<div class="waiver-item-top">' +
                            '<span class="waiver-item-name">' + escapeHtml(proj.name) + '</span>' +
                            '<span class="badge-pill u-text-xs" data-val="neutral">' + escapeHtml(proj.production) + '</span>' +
                        '</div>' +
                        '<div class="waiver-item-meta">' +
                            '<span class="waiver-item-meta-entry">' +
                                '<i data-lucide="calendar"></i> ' + escapeHtml(proj.dates) +
                            '</span>' +
                            personHtml +
                        '</div>';

                    itemEl.addEventListener('click', function () {
                        selectProject(proj);
                    });

                    resultsList.appendChild(itemEl);
                });
            }

            dropdown.classList.remove('u-d-none');

            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }

        function updateHighlight() {
            var itemEls = resultsList.querySelectorAll('.waiver-search-item');
            itemEls.forEach(function (el, idx) {
                if (idx === highlightedIndex) {
                    el.classList.add('is-highlighted');
                    el.scrollIntoView({ block: 'nearest' });
                } else {
                    el.classList.remove('is-highlighted');
                }
            });
        }

        // Événement de saisie dans le champ de recherche
        searchInput.addEventListener('input', function () {
            var rawVal = searchInput.value;
            var q = normalizeStr(rawVal);

            clearBtn.classList.toggle('u-d-none', rawVal.length === 0);

            // Commence la recherche uniquement à partir de 2 caractères
            if (q.length < 2) {
                dropdown.classList.add('u-d-none');
                currentFiltered = [];
                highlightedIndex = -1;
                if (helperText) helperText.classList.remove('u-d-none');
                return;
            }

            if (helperText) helperText.classList.add('u-d-none');

            var filtered = projects.filter(function (p) {
                var searchTarget = normalizeStr(p.search || (p.name + ' ' + p.production + ' ' + (p.pilot || p.contact || '') + ' ' + p.dates));
                return searchTarget.includes(q);
            });

            renderDropdown(filtered, rawVal);
        });

        // Bouton d'effacement de la recherche
        clearBtn.addEventListener('click', function () {
            searchInput.value = '';
            clearBtn.classList.add('u-d-none');
            dropdown.classList.add('u-d-none');
            currentFiltered = [];
            highlightedIndex = -1;
            if (helperText) helperText.classList.remove('u-d-none');
            searchInput.focus();
        });

        // Navigation clavier (Flèches Haut/Bas, Entrée, Échap)
        searchInput.addEventListener('keydown', function (e) {
            if (dropdown.classList.contains('u-d-none') || currentFiltered.length === 0) {
                if (e.key === 'Escape') {
                    dropdown.classList.add('u-d-none');
                }
                return;
            }

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                highlightedIndex = (highlightedIndex + 1) % currentFiltered.length;
                updateHighlight();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                highlightedIndex = (highlightedIndex - 1 + currentFiltered.length) % currentFiltered.length;
                updateHighlight();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (highlightedIndex >= 0 && highlightedIndex < currentFiltered.length) {
                    selectProject(currentFiltered[highlightedIndex]);
                } else if (currentFiltered.length === 1) {
                    selectProject(currentFiltered[0]);
                }
            } else if (e.key === 'Escape') {
                dropdown.classList.add('u-d-none');
            }
        });

        // Fermeture du dropdown lors d'un clic en dehors
        document.addEventListener('click', function (e) {
            if (!searchContainer.contains(e.target)) {
                dropdown.classList.add('u-d-none');
            }
        });

        // Bouton Changer de projet
        if (changeBtn) {
            changeBtn.addEventListener('click', function () {
                unselectProject();
            });
        }

        // Pré-sélection au chargement si project_id est fourni (ex: ?project_id=123)
        var initialId = hiddenInput.value;
        if (initialId) {
            var initialProj = projects.find(function (p) {
                return p.id.toString() === initialId.toString();
            });
            if (initialProj) {
                selectProject(initialProj);
            }
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWaiverSearch);
    } else {
        initWaiverSearch();
    }
})();
