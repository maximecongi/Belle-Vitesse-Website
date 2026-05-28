/**
 * Pre-Quote Management JS
 */

const PRE_QUOTE_CAT_MAP = {
    'equipment': 'Équipement',
    'salary': 'Salaire',
    'logistics': 'Logistique',
    'insurance': 'Assurances',
    'custom': 'Autre',
    'all': 'Tout'
};

let allRates = [];
let filteredRates = [];
let activeCategory = '';
let activeModalAnnexe = 'Annexe 1';

function toggleMAD(checkbox) {
    const row = checkbox.closest('.line-item-row');
    if (!row) return;
    const discountInput = row.querySelector('.item-discount');
    if (discountInput) {
        if (checkbox.checked) {
            discountInput.value = 100;
            discountInput.disabled = true;
            discountInput.style.backgroundColor = '#fef2f2';
            discountInput.style.color = '#b91c1c';
            discountInput.style.fontWeight = '500';
        } else {
            discountInput.value = 0;
            discountInput.disabled = false;
            discountInput.style.backgroundColor = '';
            discountInput.style.color = '';
            discountInput.style.fontWeight = '';
        }
    }
    recalculate();
}

async function addItem(category) {
    activeCategory = category;
    if (category === 'custom') {
        injectLine({
            category: 'custom',
            name: '',
            price: 0,
            unit: 'unité'
        });
        return;
    }

    if (category === 'insurance') {
        injectLine({
            category: 'insurance',
            name: '',
            price: 0,
            unit: 'unité'
        });
        return;
    }

    if (allRates.length === 0) {
        const res = await fetch('/admin/api/pre-quotes/all-rates');
        allRates = await res.json();
    }

    filteredRates = allRates.filter(r => r.category === category || category === 'all');
    openModal(category);
}

function openModal(category) {
    const modal = document.getElementById('selectionModal');
    const title = document.getElementById('modalTitle');

    const catLabel = PRE_QUOTE_CAT_MAP[category] || category;
    title.textContent = `Sélectionner : ${catLabel}`;
    modal.style.display = 'flex';

    // Show/hide modal annexe tabs
    const modalTabsContainer = document.getElementById('modalAnnexeTabsContainer');
    if (modalTabsContainer) {
        if (category === 'salary') {
            modalTabsContainer.style.display = 'block';
            modalTabsContainer.querySelectorAll('.modal-annexe-tab').forEach(btn => {
                if (btn.dataset.modalAnnexe === activeModalAnnexe) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        } else {
            modalTabsContainer.style.display = 'none';
        }
    }

    renderModalList();

    const searchInput = document.getElementById('modalSearch');
    searchInput.value = '';
    searchInput.focus();

    searchInput.oninput = (e) => {
        const val = e.target.value.toLowerCase();
        renderModalList(val);
    };
}

function closeModal() {
    document.getElementById('selectionModal').style.display = 'none';
}

function renderModalList(search = '') {
    const list = document.getElementById('modalList');
    list.innerHTML = '';

    const displayItems = search
        ? filteredRates.filter(r => r.name.toLowerCase().includes(search) || r.sub_category.toLowerCase().includes(search))
        : filteredRates;

    let itemsToDisplay = displayItems;
    if (activeCategory === 'salary') {
        itemsToDisplay = displayItems.filter(r => r.annexe === activeModalAnnexe);
    }

    itemsToDisplay.forEach(item => {
        const div = document.createElement('div');
        div.className = 'modal-item';
        
        if (item.category === 'salary') {
            const price8h = item.rates['8h'] || 0;
            const price10h = item.rates['10h'] || 0;
            
            div.innerHTML = `
                <div class="modal-item-info">
                    <span class="category-badge category-${item.category}">${item.sub_category}</span>
                    <span class="modal-item-name">${item.position || item.name.replace(/\s*\(.*\)$/, '')}</span>
                </div>
                <div style="display: flex; gap: 0.5rem; align-items: center;">
                    <button type="button" class="modal-annexe-tab btn-select-rate-8h" style="margin: 0; padding: 0.4rem 0.8rem; font-size: 0.75rem;">8h (${price8h.toFixed(2)} €)</button>
                    <button type="button" class="modal-annexe-tab btn-select-rate-10h" style="margin: 0; padding: 0.4rem 0.8rem; font-size: 0.75rem;">10h (${price10h.toFixed(2)} €)</button>
                </div>
            `;
            
            div.querySelector('.btn-select-rate-8h').onclick = (e) => {
                e.stopPropagation();
                injectLine(item, '8h');
                closeModal();
            };
            div.querySelector('.btn-select-rate-10h').onclick = (e) => {
                e.stopPropagation();
                injectLine(item, '10h');
                closeModal();
            };
        } else {
            const catLabel = PRE_QUOTE_CAT_MAP[item.category] || item.category;
            let priceHtml = '';
            if (item.unit === 'km') {
                priceHtml = `À partir de ${item.price.toFixed(2)} €`;
            } else {
                priceHtml = `${item.price.toFixed(2)} € / ${item.unit}`;
            }

            div.innerHTML = `
                <div class="modal-item-info">
                    <span class="category-badge category-${item.category}">${item.sub_category}</span>
                    <span class="modal-item-name">${item.name}</span>
                </div>
                <div class="modal-item-price">${priceHtml}</div>
            `;
            div.onclick = () => {
                injectLine(item);
                closeModal();
            };
        }
        list.appendChild(div);
    });
}

// Initialisation et listeners
document.addEventListener('DOMContentLoaded', () => {
    // Gestion visuelle du switch des remises
    const showDiscountsCb = document.getElementById('showDiscounts');
    if (showDiscountsCb) {
        showDiscountsCb.addEventListener('change', () => {
            const track = showDiscountsCb.closest('.status-toggle').querySelector('.toggle-track');
            if (showDiscountsCb.checked) {
                track.classList.add('active');
            } else {
                track.classList.remove('active');
            }
        });
    }

    // Onglets annexe du modal
    const modalTabsContainer = document.getElementById('modalAnnexeTabsContainer');
    if (modalTabsContainer) {
        modalTabsContainer.querySelectorAll('.modal-annexe-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                modalTabsContainer.querySelectorAll('.modal-annexe-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                activeModalAnnexe = btn.dataset.modalAnnexe;
                renderModalList(document.getElementById('modalSearch').value.toLowerCase());
            });
        });
    }

    // Initialisation des items en Mise à Disposition (M.A.D.)
    document.querySelectorAll('.item-mad-checkbox').forEach(cb => {
        if (cb.checked) {
            const row = cb.closest('.line-item-row');
            if (row) {
                const discountInput = row.querySelector('.item-discount');
                if (discountInput) {
                    discountInput.value = 100;
                    discountInput.disabled = true;
                    discountInput.style.backgroundColor = '#fef2f2';
                    discountInput.style.color = '#b91c1c';
                    discountInput.style.fontWeight = '500';
                }
            }
        }
    });
});

function injectLine(item, rateType = '10h') {
    const container = document.getElementById(`list-${item.category}`);
    if (!container) {
        console.error("No dropzone found for category:", item.category);
        return;
    }
    const catLabel = PRE_QUOTE_CAT_MAP[item.category] || item.category;

    let badgeHtml = '';
    let rowDataAttr = '';
    if (item.category === 'custom') {
        badgeHtml = `<input type="text" class="category-badge category-custom item-custom-cat" value="${item.custom_category || 'Autre'}" style="border: 1px dashed #d1d5db; background: #f3f4f6; color: #374151; width: 90px; text-align: center; text-transform: uppercase; font-size: 0.65rem; font-weight: 600; padding: 0.15rem 0.4rem; border-radius: 2px; margin-bottom: 4px;" placeholder="Autre">`;
    } else {
        badgeHtml = `<span class="category-badge category-${item.category}">${catLabel}</span>`;
        if (item.category === 'equipment') {
            badgeHtml += `
                <label class="mad-label" style="display: inline-flex; align-items: center; font-size: 0.7rem; color: #b91c1c; margin-left: 8px; cursor: pointer; font-weight: 500; vertical-align: middle;">
                    <input type="checkbox" class="item-mad-checkbox" onchange="toggleMAD(this)" ${item.is_mad ? 'checked' : ''} style="margin-right: 3px; accent-color: #b91c1c; vertical-align: middle;">
                    M.A.D.
                </label>
            `;
        }
        if (item.category === 'salary') {
            rowDataAttr = `data-rates='${JSON.stringify(item.rates || {})}'`;
            badgeHtml += `
                <select class="form-input salary-rate-select" onchange="changeSalaryRate(this)" style="display: inline-block; width: auto; font-size: 0.75rem; padding: 0.15rem 0.4rem; height: auto; margin-left: 8px; vertical-align: middle;">
                    <option value="10h" ${rateType === '10h' ? 'selected' : ''}>10h</option>
                    <option value="8h" ${rateType === '8h' ? 'selected' : ''}>8h</option>
                </select>
            `;
        }
    }

    let readonlyAttr = '';
    if (item.unit === 'km') {
        readonlyAttr = 'readonly style="background-color: #f3f4f6; cursor: not-allowed;"';
    }

    const initialPrice = item.category === 'salary' ? (parseFloat(item.rates[rateType]) || 0) : item.price;

    const isSalary = item.category === 'salary';
    const positionStyle = isSalary ? 'bottom: 0.2rem;' : 'bottom: 0.65rem;';
    const employeeInputHtml = isSalary 
        ? `<input type="text" class="form-input item-employee" value="${item.employee_name || ''}" placeholder="Nom de l'intervenant / technicien" style="font-size: 0.75rem; padding: 0.2rem 0.4rem; height: auto; display: block; width: 100%; border-color: #d1d5db; background-color: #f9fafb;">`
        : '';

    const html = `
        <div class="line-item-row" data-category="${item.category}" data-annexe="${item.annexe || ''}" ${rowDataAttr} draggable="true">
            <div class="drag-handle">⠿</div>
            <div style="position: relative; ${positionStyle}">
                ${badgeHtml}
                <input type="text" class="form-input item-desc" value="${item.name}" placeholder="Description" style="margin-bottom: 4px;">
                ${employeeInputHtml}
            </div>
            <div><input type="number" step="0.5" class="form-input text-center item-qty" value="1" onchange="recalculate()"></div>
            <input type="hidden" class="item-unit" value="${item.unit}">
            <div>
                <input type="number" step="1" min="0" max="100" class="form-input text-center item-discount" value="0" onchange="recalculate()" placeholder="0%">
            </div>
            <div><input type="number" step="0.01" class="form-input text-right item-price" value="${initialPrice.toFixed(2)}" onchange="recalculate()" ${readonlyAttr}></div>
            <div class="text-right">
                <button type="button" onclick="this.parentElement.parentElement.remove(); recalculate();" class="admin-btn" style="padding: 0.25rem 0.5rem; font-size: 0.8rem; background: #fee2e2; color: #dc2626; border: 1px solid #fca5a5;">Supprimer</button>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', html);
    const newRow = container.lastElementChild;
    initDragOnRow(newRow);
    recalculate();
}

function changeSalaryRate(selectElement) {
    const row = selectElement.closest('.line-item-row');
    if (!row) return;

    const ratesData = row.getAttribute('data-rates');
    if (!ratesData) return;

    try {
        const rates = JSON.parse(ratesData);
        const rateType = selectElement.value;
        const price = parseFloat(rates[rateType]) || 0;

        const priceInput = row.querySelector('.item-price');
        if (priceInput) {
            priceInput.value = price.toFixed(2);
        }
        recalculate();
    } catch (e) {
        console.error("Error parsing rates in changeSalaryRate:", e);
    }
}

function recalculate() {
    let baseRentalHT = 0;
    const rows = document.querySelectorAll('.line-item-row');

    rows.forEach(row => {
        if (row.dataset.category === 'insurance') {
            return; // Skip legacy insurance rows to avoid double insurance
        }
        const qty = parseFloat(row.querySelector('.item-qty').value) || 0;
        const discount = parseFloat(row.querySelector('.item-discount').value) || 0;
        const unit = row.querySelector('.item-unit').value;

        let lineTotal = 0;
        if (unit === 'km') {
            const baseDist = DELIVERY_CONFIG.baseDistance;
            const basePrice = DELIVERY_CONFIG.basePrice;
            const midDist = DELIVERY_CONFIG.midDistance;
            const midRate = DELIVERY_CONFIG.midRate;
            const highRate = DELIVERY_CONFIG.highRate;

            let totalItemPrice = 0;
            if (qty <= baseDist) {
                totalItemPrice = basePrice;
            } else if (qty <= midDist) {
                totalItemPrice = basePrice + (qty - baseDist) * midRate * 2;
            } else {
                totalItemPrice = basePrice + (midDist - baseDist) * midRate * 2 + (qty - midDist) * highRate * 2;
            }

            lineTotal = totalItemPrice * (1 - (discount / 100));

            // Mettre à jour le prix unitaire pour afficher le total de la livraison
            row.querySelector('.item-price').value = totalItemPrice.toFixed(2);
        } else {
            const price = parseFloat(row.querySelector('.item-price').value) || 0;
            lineTotal = (qty * price) * (1 - (discount / 100));
        }

        // Exclude all salary items from client-side totals
        if (row.dataset.category === 'salary') {
            return;
        }

        baseRentalHT += lineTotal;
    });

    const insuranceRate = parseFloat(document.getElementById('insuranceRate').value) || 0;
    const insuranceAmount = baseRentalHT * (insuranceRate / 100);
    const totalHT = baseRentalHT + insuranceAmount;

    const tvaRate = parseFloat(document.getElementById('tvaRate').value) || 0;
    const tvaAmount = totalHT * (tvaRate / 100);
    const totalTTC = totalHT + tvaAmount;

    const baseRentalHTEl = document.getElementById('baseRentalHT');
    if (baseRentalHTEl) baseRentalHTEl.textContent = baseRentalHT.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';

    const insuranceAmountEl = document.getElementById('insuranceAmount');
    if (insuranceAmountEl) insuranceAmountEl.textContent = insuranceAmount.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';

    document.getElementById('totalHT').textContent = totalHT.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
    document.getElementById('tvaAmount').textContent = tvaAmount.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
    document.getElementById('totalTTC').textContent = totalTTC.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
}

// ── DRAG AND DROP ─────────────────────────────────────────────

let draggedRow = null;

function initDragAndDrop() {
    const zones = ['equipment', 'salary', 'logistics', 'custom'];
    zones.forEach(zoneKey => {
        const zone = document.getElementById(`list-${zoneKey}`);
        if (!zone) return;

        // Initialize existing rows in this zone
        zone.querySelectorAll('.line-item-row').forEach(row => {
            row.setAttribute('draggable', 'true');
            initDragOnRow(row);
        });

        initDropZone(zone);
    });
}

function initDragOnRow(row) {
    row.addEventListener('dragstart', (e) => {
        draggedRow = row;
        row.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
    });

    row.addEventListener('dragend', () => {
        row.classList.remove('dragging');
        draggedRow = null;
        document.querySelectorAll('.drag-indicator').forEach(i => i.remove());
    });
}

function initDropZone(zone) {
    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        
        // Prevent cross-category drag and drop
        if (!draggedRow || draggedRow.dataset.category !== zone.dataset.category) {
            e.dataTransfer.dropEffect = 'none';
            return;
        }

        e.dataTransfer.dropEffect = 'move';
        const afterElement = getDragAfterElement(zone, e.clientY);

        // Visual indicator
        document.querySelectorAll('.drag-indicator').forEach(i => i.remove());
        const indicator = document.createElement('div');
        indicator.className = 'drag-indicator';
        indicator.style.height = '2px';
        indicator.style.background = 'var(--yellow-1)';
        indicator.style.margin = '5px 0';

        if (afterElement == null) {
            zone.appendChild(indicator);
        } else {
            zone.insertBefore(indicator, afterElement);
        }
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        document.querySelectorAll('.drag-indicator').forEach(i => i.remove());

        if (!draggedRow || draggedRow.dataset.category !== zone.dataset.category) return;

        const afterElement = getDragAfterElement(zone, e.clientY);
        if (afterElement == null) {
            zone.appendChild(draggedRow);
        } else {
            zone.insertBefore(draggedRow, afterElement);
        }

        recalculate();
    });
}

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.line-item-row:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

async function saveQuote() {
    const btn = document.getElementById('saveBtn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Enregistrement...';

    try {
        const prestations = [];
        document.querySelectorAll('.line-item-row').forEach(row => {
            const category = row.dataset.category;
            const annexe = row.dataset.annexe || null;
            const customCatInput = row.querySelector('.item-custom-cat');
            
            const salaryRateSelect = row.querySelector('.salary-rate-select');
            const salaryRateType = salaryRateSelect ? salaryRateSelect.value : null;
            const ratesAttr = row.getAttribute('data-rates');
            const rates = ratesAttr ? JSON.parse(ratesAttr) : null;

            const madCheckbox = row.querySelector('.item-mad-checkbox');
            const isMad = madCheckbox ? madCheckbox.checked : false;

            const employeeInput = row.querySelector('.item-employee');
            const employeeName = employeeInput ? employeeInput.value : null;

            prestations.push({
                category: category,
                annexe: annexe,
                custom_category: customCatInput ? customCatInput.value : null,
                description: row.querySelector('.item-desc').value,
                quantity: parseFloat(row.querySelector('.item-qty').value) || 0,
                unit: row.querySelector('.item-unit').value,
                unit_price: parseFloat(row.querySelector('.item-price').value) || 0,
                discount_rate: parseFloat(row.querySelector('.item-discount').value) || 0,
                salary_rate_type: salaryRateType,
                rates: rates,
                is_mad: isMad,
                employee_name: employeeName
            });
        });

        const data = {
            production_id: document.querySelector('select[name="production_id"]').value,
            project_name: document.querySelector('input[name="project_name"]').value,
            project_id: document.querySelector('select[name="project_id"]').value,
            tva_rate: parseFloat(document.getElementById('tvaRate').value) || 20.00,
            insurance_rate: parseFloat(document.getElementById('insuranceRate').value) || 10.00,
            show_discounts: document.getElementById('showDiscounts').checked,
            prestations: prestations
        };

        if (!data.production_id) {
            alert("Veuillez sélectionner une production.");
            btn.disabled = false;
            btn.textContent = originalText;
            return;
        }

        const isEdit = window.location.pathname.includes('/edit');
        const url = isEdit ? window.location.pathname : '/admin/pre-quotes/new';

        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
            },
            body: JSON.stringify(data)
        });

        const result = await res.json();
        if (result.status === 'success') {
            if (isEdit) {
                if (window.showFlash) {
                    window.showFlash("Pré-Devis mis à jour avec succès !", "success");
                } else {
                    alert("Pré-Devis mis à jour avec succès !");
                }
                btn.disabled = false;
                btn.textContent = originalText;
            } else {
                // Pour un nouveau devis, on redirige vers l'édition du devis créé
                window.location.href = `/admin/pre-quotes/${result.id}/edit`;
            }
        } else {
            alert("Erreur : " + result.message);
            btn.disabled = false;
            btn.textContent = originalText;
        }
    } catch (error) {
        console.error(error);
        alert("Une erreur est survenue lors de l'enregistrement.");
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

async function createVersion() {
    const note = prompt("Saisissez une note de version pour vous rappeler ce qui a été fait (ex: Ajout du chauffeur, rabais matériel) :");
    if (note === null) return; // user cancelled

    const btn = document.getElementById('versionBtn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Enregistrement...';

    // D'abord on sauvegarde les modifications actuelles du devis
    await saveQuote();

    const quoteId = window.location.pathname.split('/').filter(Boolean).find(p => !isNaN(p));
    if (!quoteId) {
        alert("Impossible de déterminer l'identifiant du devis.");
        btn.disabled = false;
        btn.textContent = originalText;
        return;
    }

    try {
        const res = await fetch(`/admin/api/pre-quotes/${quoteId}/version`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
            },
            body: JSON.stringify({ note: note.trim() })
        });
        const result = await res.json();
        if (result.status === 'success') {
            alert(`Version ${result.version_number} figée avec succès !`);
            window.location.reload();
        } else {
            alert("Erreur lors de la création de la version : " + result.message);
            btn.disabled = false;
            btn.textContent = originalText;
        }
    } catch (e) {
        console.error(e);
        alert("Une erreur est survenue lors de l'enregistrement de la version.");
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

async function restoreVersion(versionId, versionNumber) {
    if (!confirm(`Êtes-vous sûr de vouloir restaurer la version ${versionNumber} ? Les modifications non enregistrées seront perdues.`)) {
        return;
    }

    try {
        const res = await fetch(`/admin/api/pre-quotes/version/${versionId}/restore`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
            }
        });
        const result = await res.json();
        if (result.status === 'success') {
            alert(`Version ${versionNumber} restaurée avec succès !`);
            window.location.reload();
        } else {
            alert("Erreur lors de la restauration : " + result.message);
        }
    } catch (e) {
        console.error(e);
        alert("Une erreur est survenue lors de la restauration de la version.");
    }
}
