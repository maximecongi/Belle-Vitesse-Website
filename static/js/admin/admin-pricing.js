/**
 * Admin Pricing Management JS (Refactored)
 * Organized into a class-based structure for better maintainability.
 */

class PricingAdmin {
    constructor(config) {
        this.csrfToken = config.csrfToken;
        this.isAdmin = config.isAdmin;
        this.invoiceFactor = config.invoiceFactor;
        this.draggedRow = null;
        this.activeAnnexe = 'Annexe 1';

        if (this.isAdmin) {
            this.initEvents();
            this.initDragAndDrop();
        }
        this.initTabs();
        this.initAnnexeTabs();
    }

    // ── Helper API ─────────────────────────────────────────────
    async fetchAPI(url, method = 'GET', body = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            }
        };
        if (body) options.body = JSON.stringify(body);

        try {
            const response = await fetch(url, options);
            const data = await response.json();
            if (!data.success && data.error) this.flash(data.error, 'error');
            return data;
        } catch (error) {
            this.flash('Erreur réseau ou serveur', 'error');
            return { success: false };
        }
    }

    flash(msg, category) {
        if (window.showFlash) window.showFlash(msg, category);
    }

    // ── Tabs ───────────────────────────────────────────────────
    initTabs() {
        const savedTab = localStorage.getItem('activePricingTab');
        if (savedTab) {
            document.querySelector(`[data-tab="${savedTab}"]`)?.click();
        }

        document.querySelectorAll('.pricing-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.pricing-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.pricing-tab-content').forEach(p => p.classList.remove('active'));
                
                tab.classList.add('active');
                const panel = document.getElementById('panel-' + tab.dataset.tab);
                if (panel) panel.classList.add('active');
                localStorage.setItem('activePricingTab', tab.dataset.tab);
            });
        });
    }

    // ── Annexe Tabs ───────────────────────────────────────────
    initAnnexeTabs() {
        const savedAnnexe = localStorage.getItem('activePricingAnnexe') || 'Annexe 1';
        this.activeAnnexe = savedAnnexe;

        const tabs = document.querySelectorAll('.annexe-tab');
        tabs.forEach(tab => {
            if (tab.dataset.annexe === this.activeAnnexe) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.activeAnnexe = tab.dataset.annexe;
                localStorage.setItem('activePricingAnnexe', this.activeAnnexe);
                this.filterSalaryRows();
            });
        });

        this.filterSalaryRows();
    }

    filterSalaryRows() {
        const isFacture = this.activeAnnexe === 'Facture';

        // Show/hide factor badge container
        const factorContainer = document.getElementById('factorContainer');
        if (factorContainer) {
            factorContainer.style.display = isFacture ? 'flex' : 'none';
        }



        document.querySelectorAll('#panel-salaries tr[data-row-id]').forEach(row => {
            const annexe = row.dataset.annexe || 'Annexe 1';
            if (annexe === this.activeAnnexe) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });

        // Update group visible counts
        document.querySelectorAll('.salary-group').forEach(group => {
            const tbody = group.querySelector('.salary-drop-zone');
            if (tbody) {
                this.updateGroupCount(tbody);
            }
        });
    }

    // ── Events Delegation ──────────────────────────────────────
    initEvents() {
        // Global click listener for delegation
        document.addEventListener('click', (e) => {
            const target = e.target;

            // Invoice Factor Click
            if (target.closest('#factorBadge')) {
                this.handleFactorEdit(target.closest('#factorBadge'));
            }

            // Inline Edit Click
            const cell = target.closest('.editable-cell');
            if (cell && !cell.classList.contains('editing')) {
                this.handleInlineEdit(cell);
            }

            // Rename Group Click
            const title = target.closest('.editable-group-title');
            if (title && !title.querySelector('input')) {
                this.handleGroupRename(title);
            }

            // Button Actions
            if (target.closest('.btn-delete-line')) this.handleDeleteLine(target.closest('.btn-delete-line'));
            if (target.closest('.btn-delete-group')) this.handleDeleteGroup(target.closest('.btn-delete-group'));
            if (target.closest('.btn-add-salary-line')) this.handleAddSalaryLine(target.closest('.btn-add-salary-line'));
            if (target.closest('.btn-add-line')) this.handleAddLine(target.closest('.btn-add-line'));
        });

        // Add Group Button
        const btnAddGroup = document.getElementById('btnAddGroup');
        if (btnAddGroup) {
            btnAddGroup.addEventListener('click', () => this.handleAddGroup());
        }
    }

    // ── Action Handlers ────────────────────────────────────────
    
    handleFactorEdit(badge) {
        if (badge.querySelector('input')) return;
        const currentVal = this.invoiceFactor;
        const input = document.createElement('input');
        input.type = 'text';
        input.value = currentVal;
        input.style.cssText = 'width: 60px; text-align: center; font-size: 0.8rem; font-weight: 600; border: 2px solid var(--admin-accent); border-radius: 6px; padding: 0.2rem 0.4rem; background: #fffdf5; outline: none;';
        
        badge.textContent = '×';
        badge.appendChild(input);
        input.focus();
        input.select();

        const save = async () => {
            const num = parseFloat(input.value.trim().replace(',', '.'));
            input.remove();
            if (isNaN(num) || num <= 0) {
                badge.textContent = '×' + currentVal;
                return this.flash('Facteur invalide', 'error');
            }
            
            badge.textContent = '×…';
            const res = await this.fetchAPI('/admin/api/pricing/invoice-factor', 'PATCH', { value: num });
            if (res.success) {
                this.invoiceFactor = res.factor;
                badge.textContent = '×' + res.factor;
                this.flash(`Facteur mis à jour (${res.salaries.length} lignes recalculées)`, 'success');
                this.updateSalaryRows(res.salaries);
            } else {
                badge.textContent = '×' + currentVal;
            }
        };

        input.addEventListener('blur', save);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') input.blur();
            if (e.key === 'Escape') { input.remove(); badge.textContent = '×' + currentVal; }
        });
    }
    handleInlineEdit(cell) {
        const valueSpan = cell.querySelector('.cell-value');
        const originalValue = valueSpan.textContent.trim();
        cell.classList.add('editing');

        const field = cell.dataset.field;
        let input;

        if (field === 'annexe') {
            input = document.createElement('select');
            input.className = 'cell-input';
            const options = ['Annexe 1', 'Annexe 2', 'Annexe 1 renfort', 'USPA', 'Court-métrage', 'Publicité', 'Facture'];
            options.forEach(opt => {
                const el = document.createElement('option');
                el.value = opt;
                el.textContent = opt;
                if (opt === originalValue) el.selected = true;
                input.appendChild(el);
            });
        } else {
            input = document.createElement('input');
            input.className = 'cell-input';
            input.value = originalValue.replace(/\s*€$/, '');
        }

        valueSpan.style.display = 'none';
        cell.appendChild(input);
        input.focus();
        if (field !== 'annexe') {
            input.select();
        }

        const save = async () => {
            let newValue = input.value.trim();
            const field = cell.dataset.field;
            const isNumeric = ['base_hourly', 'daily_rate'].includes(field);

            if (isNumeric) {
                const num = parseFloat(newValue.replace(/[^\d.,-]/g, '').replace(',', '.') || 0);
                newValue = num.toFixed(2);
            }

            input.remove();
            valueSpan.style.display = '';
            cell.classList.remove('editing');

            if (newValue === originalValue.replace(/\s*€$/, '')) {
                valueSpan.textContent = originalValue;
                return;
            }

            const suffix = (isNumeric && ['salary', 'equipment'].includes(cell.dataset.type)) ? ' €' : '';
            valueSpan.textContent = newValue + suffix;

            const type = cell.dataset.type;
            const urlMap = {
                'equipment': '/admin/api/pricing/equipment',
                'salary': '/admin/api/pricing/salary',
                'logistics': '/admin/api/pricing/logistics'
            };
            const body = { id: parseInt(cell.dataset.id) || cell.dataset.id, field, value: newValue };
            if (type === 'equipment') body.table = cell.dataset.table;

            const res = await this.fetchAPI(urlMap[type], 'PATCH', body);
            if (res.success) {
                this.flash('Sauvegardé', 'success');
                if (res.updated_rates) {
                    this.updateSalaryRows(res.updated_rates);
                } else if (field === 'base_hourly' && res.data) {
                    this.updateSalaryRow(cell.closest('tr'), res.data);
                }
            } else {
                valueSpan.textContent = originalValue;
            }
        };

        input.addEventListener('blur', save);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') input.blur();
            if (e.key === 'Escape') { input.value = originalValue; input.blur(); }
        });
    }

    handleGroupRename(title) {
        const currentName = title.textContent.trim();
        const input = document.createElement('input');
        input.value = currentName;
        input.className = 'group-title-input';
        title.textContent = '';
        title.appendChild(input);
        input.focus();
        input.select();

        const save = async () => {
            const newName = input.value.trim();
            input.remove();
            if (!newName || newName === currentName) return title.textContent = currentName;

            title.textContent = '…';
            const res = await this.fetchAPI('/admin/api/pricing/salary/rename-group', 'PATCH', { old_name: currentName, new_name: newName });
            if (res.success) {
                title.textContent = res.new_name;
                const groupDiv = title.closest('.salary-group');
                if (groupDiv) this.syncGroupDataAttributes(groupDiv, res.new_name);
                this.flash('Groupe renommé', 'success');
            } else {
                title.textContent = currentName;
            }
        };

        input.addEventListener('blur', save);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') input.blur();
            if (e.key === 'Escape') { input.remove(); title.textContent = currentName; }
        });
    }

    async handleDeleteGroup(btn) {
        const name = btn.dataset.group;
        if (!confirm(`Supprimer le groupe "${name}" ?`)) return;

        const res = await this.fetchAPI('/admin/api/pricing/salary/delete-group', 'DELETE', { group_name: name });
        if (res.success) {
            btn.closest('.salary-group').remove();
            this.flash('Groupe supprimé', 'success');
        }
    }

    async handleDeleteLine(btn) {
        if (!confirm('Supprimer cette ligne ?')) return;
        const type = btn.dataset.type;
        const id = btn.dataset.id;
        const url = (type === 'salary' ? '/admin/api/pricing/salary/' : '/admin/api/pricing/logistics/') + id;

        const res = await this.fetchAPI(url, 'DELETE');
        if (res.success) {
            const row = btn.closest('tr');
            const tbody = row.closest('tbody');
            if (type === 'salary') {
                const positionId = row.dataset.positionId;
                if (positionId) {
                    document.querySelectorAll(`tr[data-position-id="${positionId}"]`).forEach(r => r.remove());
                } else {
                    row.remove();
                }
            } else {
                row.remove();
            }
            this.updateGroupCount(tbody);
            this.flash('Supprimé', 'success');
        }
    }

    async handleAddGroup() {
        const name = prompt('Nom du nouveau groupe :');
        if (!name?.trim()) return;

        const res = await this.fetchAPI('/admin/api/pricing/salary', 'POST', { 
            group_name: name.trim(),
            annexe: this.activeAnnexe
        });
        if (res.success) {
            this.injectNewGroupUI(name.trim(), res.data);
            this.filterSalaryRows();
            this.flash('Groupe créé', 'success');
        }
    }

    async handleAddSalaryLine(btn) {
        const group = btn.dataset.group;
        const res = await this.fetchAPI('/admin/api/pricing/salary', 'POST', { 
            group_name: group,
            annexe: this.activeAnnexe
        });
        if (res.success) {
            const tbody = btn.closest('.salary-group').querySelector('.salary-drop-zone');
            if (res.data && res.data.all_rates) {
                res.data.all_rates.forEach(rateData => {
                    this.injectSalaryRowUI(tbody, rateData, false);
                });
                this.filterSalaryRows();
                const activeRow = tbody.querySelector(`tr[data-row-id="${res.data.id}"][data-annexe="${this.activeAnnexe}"]`);
                if (activeRow) {
                    activeRow.querySelector('.editable-cell[data-field="position"]')?.click();
                }
            } else {
                this.injectSalaryRowUI(tbody, res.data, true);
                this.filterSalaryRows();
            }
            this.flash('Position ajoutée', 'success');
        }
    }

    async handleAddLine(btn) {
        if (btn.dataset.type !== 'logistics') return;
        const res = await this.fetchAPI('/admin/api/pricing/logistics', 'POST', {});
        if (res.success) {
            const tbody = document.getElementById('logistics-tbody');
            this.injectLogisticsRowUI(tbody, res.data);
            this.flash('Ligne ajoutée', 'success');
        }
    }

    // ── UI Updates ─────────────────────────────────────────────
    
    updateSalaryRows(salaries) {
        salaries.forEach(s => {
            const row = document.querySelector(`tr[data-row-id="${s.id}"]`);
            if (row) this.updateSalaryRow(row, s);
        });
    }

    updateSalaryRow(row, data) {
        const posCell = row.querySelector(`[data-field="position"] .cell-value`);
        if (posCell && data.position !== undefined) {
            posCell.textContent = data.position;
        }

        const baseCell = row.querySelector(`[data-field="base_hourly"] .cell-value`);
        if (baseCell && data.base_hourly !== undefined) {
            baseCell.textContent = parseFloat(data.base_hourly || 0).toFixed(2) + ' €';
        }

        const fields = ['inter_8h', 'inter_10h'];
        fields.forEach(f => {
            const cell = row.querySelector(`.computed-cell[data-field="${f}"] .cell-value`);
            if (cell) cell.textContent = parseFloat(data[f] || 0).toFixed(2) + ' €';
        });
    }

    updateGroupCount(tbody) {
        if (!tbody) return;
        const groupDiv = tbody.closest('.salary-group');
        if (groupDiv) {
            const badge = groupDiv.querySelector('.salary-group-count');
            if (badge) {
                const isSalary = tbody.classList.contains('salary-drop-zone');
                const selector = isSalary ? 'tr[data-row-id]:not([style*="display: none"])' : 'tr[data-row-id]';
                badge.textContent = tbody.querySelectorAll(selector).length;
            }
        }
    }

    syncGroupDataAttributes(groupDiv, newName) {
        groupDiv.dataset.groupName = newName;
        groupDiv.querySelector('.salary-drop-zone').dataset.group = newName;
        const addBtn = groupDiv.querySelector('.btn-add-salary-line');
        if (addBtn) addBtn.dataset.group = newName;
        const delBtn = groupDiv.querySelector('.btn-delete-group');
        if (delBtn) delBtn.dataset.group = newName;
    }

    // ── UI Injection ───────────────────────────────────────────
    
    injectNewGroupUI(name, firstRate) {
        const container = document.getElementById('salary-groups-container');
        const emptyState = container.querySelector('.admin-card:not(.salary-group)');
        if (emptyState) emptyState.remove();

        const html = `
        <div class="salary-group" data-group-name="${name}">
            <div class="salary-group-header">
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <span class="salary-group-title editable-group-title">${name}</span>
                    <span class="salary-group-count">1</span>
                </div>
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <button class="admin-btn admin-btn-primary btn-add-salary-line" data-group="${name}">+ Nouvelle position</button>
                    <button class="admin-btn admin-btn-danger btn-delete-group" data-group="${name}">Supprimer</button>
                </div>
            </div>
            <div class="admin-table-container">
                <table class="admin-table">
                    <thead>
                        <tr>
                            <th style="width: 30px;"></th>
                            <th>Position</th>
                            <th style="width: 80px; text-align: right;">Base/H</th>
                            <th style="width: 100px; text-align: right;">8h</th>
                            <th style="width: 100px; text-align: right;">10h</th>
                            <th style="width: 80px;"></th>
                        </tr>
                    </thead>
                    <tbody class="salary-drop-zone" data-group="${name}"></tbody>
                </table>
            </div>
        </div>`;
        container.insertAdjacentHTML('beforeend', html);
        const tbody = container.lastElementChild.querySelector('tbody');
        if (firstRate && firstRate.all_rates) {
            firstRate.all_rates.forEach(rateData => {
                this.injectSalaryRowUI(tbody, rateData, false);
            });
            const activeRow = tbody.querySelector(`tr[data-row-id="${firstRate.id}"][data-annexe="${this.activeAnnexe}"]`);
            if (activeRow) {
                activeRow.querySelector('.editable-cell[data-field="position"]')?.click();
            }
        } else {
            this.injectSalaryRowUI(tbody, firstRate, true);
        }
        this.initDropZone(tbody);
    }

    injectSalaryRowUI(tbody, data, startEditing = true) {
        const isComputed = data.annexe === 'Facture' || data.annexe === 'Annexe 1 renfort';
        const baseClass = isComputed ? 'computed-cell' : 'editable-cell';
        const html = `
            <tr data-row-id="${data.id}" data-position-id="${data.position_id}" data-annexe="${data.annexe || 'Annexe 1'}" draggable="true">
                <td class="drag-handle">⠿</td>
                <td class="editable-cell" data-id="${data.id}" data-field="position" data-type="salary"><span class="cell-value" style="font-weight: 600;">${data.position || ''}</span></td>
                <td class="${baseClass}" data-id="${data.id}" data-field="base_hourly" data-type="salary" style="text-align: right;"><span class="cell-value">${parseFloat(data.base_hourly || 0).toFixed(2)} €</span></td>
                <td class="computed-cell" data-field="inter_8h" style="text-align: right;"><span class="cell-value">${parseFloat(data.inter_8h || 0).toFixed(2)} €</span></td>
                <td class="computed-cell" data-field="inter_10h" style="text-align: right;"><span class="cell-value">${parseFloat(data.inter_10h || 0).toFixed(2)} €</span></td>
                <td style="text-align: center;"><button class="admin-btn admin-btn-danger btn-delete-line" data-id="${data.id}" data-type="salary">Supprimer</button></td>
            </tr>`;
        tbody.insertAdjacentHTML('beforeend', html);
        const row = tbody.lastElementChild;
        this.initDragOnRow(row);
        this.updateGroupCount(tbody);
        if (startEditing) {
            row.querySelector('.editable-cell[data-field="position"]')?.click();
        }
    }

    injectLogisticsRowUI(tbody, data) {
        const html = `
            <tr data-row-id="${data.id}" draggable="true">
                <td class="drag-handle">⠿</td>
                <td class="editable-cell" data-id="${data.id}" data-field="item_name" data-type="logistics"><span class="cell-value" style="font-weight: 600;"></span></td>
                <td class="editable-cell" data-id="${data.id}" data-field="daily_rate" data-type="logistics" style="text-align: right;"><span class="cell-value">0.00</span></td>
                <td class="editable-cell" data-id="${data.id}" data-field="notes" data-type="logistics"><span class="cell-value"></span></td>
                <td style="text-align: center;"><button class="admin-btn admin-btn-danger btn-delete-line" data-id="${data.id}" data-type="logistics">Supprimer</button></td>
            </tr>`;
        if (tbody.querySelector('td[colspan]')) tbody.innerHTML = '';
        tbody.insertAdjacentHTML('beforeend', html);
        this.initDragOnRow(tbody.lastElementChild);
        this.updateGroupCount(tbody);
        tbody.lastElementChild.querySelector('.editable-cell').click();
    }

    // ── Drag & Drop ────────────────────────────────────────────
    
    initDragAndDrop() {
        document.querySelectorAll('tr[draggable="true"]').forEach(r => this.initDragOnRow(r));
        document.querySelectorAll('.salary-drop-zone, .equipment-drop-zone, .logistics-drop-zone').forEach(z => this.initDropZone(z));
    }

    initDragOnRow(row) {
        row.addEventListener('dragstart', (e) => {
            this.draggedRow = row;
            row.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
        });
        row.addEventListener('dragend', () => {
            row.classList.remove('dragging');
            this.draggedRow = null;
            document.querySelectorAll('.drag-over').forEach(z => z.classList.remove('drag-over'));
            document.querySelectorAll('.drag-indicator').forEach(i => i.remove());
        });
    }

    initDropZone(zone) {
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('drag-over');
            this.showDragIndicator(zone, e.clientY);
        });

        zone.addEventListener('dragleave', (e) => {
            if (!zone.contains(e.relatedTarget)) {
                zone.classList.remove('drag-over');
                zone.querySelectorAll('.drag-indicator').forEach(i => i.remove());
            }
        });

        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('drag-over');
            zone.querySelectorAll('.drag-indicator').forEach(i => i.remove());

            if (!this.draggedRow) return;

            const sourceZone = this.draggedRow.closest('tbody');
            if (zone.className !== sourceZone.className) return this.flash('Interdit d\'une section à l\'autre', 'error');
            if (zone.classList.contains('equipment-drop-zone') && zone !== sourceZone) return this.flash('Catégorie fixe', 'error');

            this.placeDraggedRow(zone, e.clientY);
            this.updateGroupCount(sourceZone);
            this.updateGroupCount(zone);
            this.saveReorder(zone);
        });
    }

    showDragIndicator(zone, y) {
        zone.querySelectorAll('.drag-indicator').forEach(i => i.remove());
        const afterRow = this.getDragAfterElement(zone, y);
        const indicator = document.createElement('tr');
        indicator.className = 'drag-indicator';
        indicator.innerHTML = '<td colspan="11" style="height: 3px; padding: 0; background: var(--admin-accent);"></td>';
        if (afterRow) zone.insertBefore(indicator, afterRow);
        else zone.appendChild(indicator);
    }

    placeDraggedRow(zone, y) {
        const afterRow = this.getDragAfterElement(zone, y);
        if (afterRow) zone.insertBefore(this.draggedRow, afterRow);
        else zone.appendChild(this.draggedRow);
    }

    getDragAfterElement(zone, y) {
        const draggableElements = [...zone.querySelectorAll('tr[data-row-id]:not(.dragging)')];
        return draggableElements.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;
            if (offset < 0 && offset > closest.offset) return { offset: offset, element: child };
            else return closest;
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    }

    async saveReorder(zone) {
        if (zone.classList.contains('salary-drop-zone')) {
            const groups = {};
            document.querySelectorAll('.salary-drop-zone').forEach(z => {
                const ids = [...z.querySelectorAll('tr[data-row-id]')].map(r => parseInt(r.dataset.rowId));
                if (ids.length) groups[z.dataset.group] = ids;
            });
            const res = await this.fetchAPI('/admin/api/pricing/salary/reorder', 'PATCH', { groups });
            if (res.success) this.flash('Ordre sauvegardé', 'success');
        } else {
            const type = zone.classList.contains('equipment-drop-zone') ? 'equipment' : 'logistics';
            const ids = [...zone.querySelectorAll('tr[data-row-id]')].map(r => r.dataset.rowId);
            const body = type === 'equipment' ? { table: zone.dataset.table, ids } : { ids: ids.map(Number) };
            const res = await this.fetchAPI(`/admin/api/pricing/${type}/reorder`, 'PATCH', body);
            if (res.success) this.flash('Ordre sauvegardé', 'success');
        }
    }
}

// Global initialization
window.initPricing = (config) => {
    window.pricingAdmin = new PricingAdmin(config);
};
