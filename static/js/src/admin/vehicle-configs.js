/**
 * vehicle-configs.js — Matrice points de contrôle × véhicules.
 *
 * - Suivi des modifications par rapport à l'état chargé (cellules et lignes marquées « modifié »)
 * - Bascule d'une colonne (en-tête) ou d'une ligne (« Tout ») sur les véhicules affichés
 * - Enregistrement unique et groupé de toutes les lignes modifiées (une seule transaction serveur)
 * - Barre d'enregistrement collante, raccourci ⌘S / Ctrl+S, alerte avant de quitter la page
 */
(function () {
    'use strict';

    function initVehicleConfigs() {
        const root = document.getElementById('cpMatrix');
        if (!root || root._cpMatrixReady) return;
        root._cpMatrixReady = true;

        const saveUrl = root.dataset.saveUrl;
        const savebar = document.getElementById('cpMatrixSavebar');
        const dirtyLabel = document.getElementById('cpMatrixDirtyLabel');
        const btnSave = document.getElementById('cpMatrixSave');
        const btnCancel = document.getElementById('cpMatrixCancel');
        const search = document.getElementById('cpMatrixSearch');
        const noResults = document.getElementById('cpMatrixNoResults');
        const rows = Array.from(root.querySelectorAll('.cp-matrix-row'));
        const boxes = Array.from(root.querySelectorAll('.checkpoint-toggle'));
        let saving = false;

        // État de référence (dernier état enregistré)
        boxes.forEach(cb => { cb.dataset.initial = cb.checked ? '1' : '0'; });

        const isChanged = cb => (cb.checked ? '1' : '0') !== cb.dataset.initial;
        const visibleRows = () => rows.filter(r => !r.classList.contains('u-d-none'));
        const rowBoxes = row => Array.from(row.querySelectorAll('.checkpoint-toggle'));

        function refresh() {
            let changedCells = 0;
            const changedVehicles = new Set();
            const colCounts = {};

            boxes.forEach(cb => {
                const changed = isChanged(cb);
                cb.closest('.cp-matrix-cell').classList.toggle('is-dirty', changed);
                if (changed) {
                    changedCells++;
                    changedVehicles.add(cb.dataset.vehicle);
                }
                if (cb.checked) colCounts[cb.dataset.key] = (colCounts[cb.dataset.key] || 0) + 1;
            });

            // Total par véhicule (colonne « Total »)
            rows.forEach(row => {
                const counter = row.querySelector('[data-row-count]');
                if (counter) counter.textContent = rowBoxes(row).filter(cb => cb.checked).length;
                row.classList.toggle('is-dirty', changedVehicles.has(row.dataset.vehicle));
            });

            // Nombre de véhicules concernés par point de contrôle (pied de tableau)
            root.querySelectorAll('[data-col-count]').forEach(cell => {
                cell.textContent = colCounts[cell.dataset.colCount] || 0;
            });

            const dirty = changedCells > 0;
            savebar.classList.toggle('u-d-none', !dirty);
            document.body.classList.toggle('has-admin-savebar', dirty);
            if (dirty) {
                const plural = changedCells > 1 ? 's' : '';
                dirtyLabel.textContent = `${changedCells} modification${plural} non enregistrée${plural}`;
            }
            root.classList.toggle('is-dirty', dirty);
            return { dirty, changedVehicles };
        }

        function setAll(list, value) {
            list.forEach(cb => { cb.checked = value; });
            refresh();
        }

        // ── Bascules ──
        root.addEventListener('change', e => {
            if (e.target.classList.contains('checkpoint-toggle')) refresh();
        });

        root.addEventListener('click', e => {
            const colBtn = e.target.closest('.cp-matrix-col-toggle');
            if (colBtn) {
                const key = colBtn.dataset.colKey;
                const list = visibleRows().map(r => r.querySelector(`.checkpoint-toggle[data-key="${CSS.escape(key)}"]`)).filter(Boolean);
                // Si tout est coché → on décoche, sinon on coche tout
                setAll(list, !list.every(cb => cb.checked));
                return;
            }
            const rowBtn = e.target.closest('[data-row-toggle]');
            if (rowBtn) {
                const list = rowBoxes(rowBtn.closest('.cp-matrix-row'));
                setAll(list, !list.every(cb => cb.checked));
            }
        });

        // Surbrillance de la colonne survolée (en-tête, cellules et pied de tableau)
        let hoveredKey = null;
        function highlightColumn(key) {
            if (key === hoveredKey) return;
            root.querySelectorAll('.is-col-hover').forEach(el => el.classList.remove('is-col-hover'));
            hoveredKey = key;
            if (key) {
                root.querySelectorAll(`[data-col-key="${CSS.escape(key)}"]`).forEach(el => {
                    if (el.tagName === 'TH' || el.tagName === 'TD') el.classList.add('is-col-hover');
                });
            }
        }
        root.addEventListener('mouseover', e => {
            const cell = e.target.closest('th[data-col-key], td[data-col-key]');
            highlightColumn(cell ? cell.dataset.colKey : null);
        });
        root.addEventListener('mouseleave', () => highlightColumn(null));

        // ── Filtre véhicules ──
        if (search) {
            search.addEventListener('input', () => {
                const q = search.value.trim().toLowerCase();
                let visible = 0;
                rows.forEach(r => {
                    const match = !q || (r.dataset.search || '').includes(q);
                    r.classList.toggle('u-d-none', !match);
                    if (match) visible++;
                });
                if (noResults) noResults.classList.toggle('u-d-none', visible > 0 || rows.length === 0);
            });
        }

        // ── Annuler ──
        btnCancel.addEventListener('click', () => {
            boxes.forEach(cb => { cb.checked = cb.dataset.initial === '1'; });
            refresh();
        });

        // ── Enregistrer ──
        async function save() {
            const { dirty, changedVehicles } = refresh();
            if (!dirty || saving) return;
            saving = true;

            const configs = {};
            changedVehicles.forEach(vehicleId => {
                configs[vehicleId] = boxes
                    .filter(cb => cb.dataset.vehicle === vehicleId && cb.checked)
                    .map(cb => cb.dataset.key);
            });

            const label = btnSave.querySelector('span');
            const originalLabel = label.textContent;
            btnSave.disabled = true;
            btnCancel.disabled = true;
            label.textContent = 'Enregistrement…';

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
            try {
                const res = await fetch(saveUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                    body: JSON.stringify({ configs })
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok || !data.success) throw new Error(data.error || 'Enregistrement impossible.');

                // Le nouvel état devient la référence
                boxes.forEach(cb => { cb.dataset.initial = cb.checked ? '1' : '0'; });
                refresh();
                const n = data.updated || changedVehicles.size;
                if (window.showFlash) window.showFlash(`Configuration enregistrée pour ${n} véhicule${n > 1 ? 's' : ''}.`, 'success');
            } catch (err) {
                if (window.showFlash) window.showFlash(err.message || 'Erreur de connexion.', 'error');
            } finally {
                saving = false;
                btnSave.disabled = false;
                btnCancel.disabled = false;
                label.textContent = originalLabel;
            }
        }

        btnSave.addEventListener('click', save);

        document.addEventListener('keydown', e => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's' && document.getElementById('cpMatrix')) {
                e.preventDefault();
                save();
            }
        });

        // Alerte avant de quitter la page avec des modifications non enregistrées
        window.addEventListener('beforeunload', e => {
            if (root.classList.contains('is-dirty')) {
                e.preventDefault();
                e.returnValue = '';
            }
        });

        refresh();
    }

    window.initVehicleConfigs = initVehicleConfigs;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initVehicleConfigs);
    } else {
        initVehicleConfigs();
    }
})();
