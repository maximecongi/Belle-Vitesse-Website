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

async function addItem(category) {
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
    const list = document.getElementById('modalList');
    const title = document.getElementById('modalTitle');

    const catLabel = PRE_QUOTE_CAT_MAP[category] || category;
    title.textContent = `Sélectionner : ${catLabel}`;
    modal.style.display = 'flex';

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

    displayItems.forEach(item => {
        const div = document.createElement('div');
        div.className = 'modal-item';
        const catLabel = PRE_QUOTE_CAT_MAP[item.category] || item.category;
        div.innerHTML = `
            <div class="modal-item-info">
                <span class="category-badge category-${item.category}">${item.sub_category}</span>
                <span class="modal-item-name">${item.name}</span>
            </div>
            <div class="modal-item-price">${item.price.toFixed(2)} € / ${item.unit}</div>
        `;
        div.onclick = () => {
            injectLine(item);
            closeModal();
        };
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
});

function injectLine(item) {
    const container = document.getElementById('lineItemsList');
    const catLabel = PRE_QUOTE_CAT_MAP[item.category] || item.category;

    let badgeHtml = '';
    if (item.category === 'custom') {
        badgeHtml = `<input type="text" class="category-badge category-custom item-custom-cat" value="${item.custom_category || 'Autre'}" style="border: 1px dashed #d1d5db; background: #f3f4f6; color: #374151; width: 90px; text-align: center; text-transform: uppercase; font-size: 0.65rem; font-weight: 600; padding: 0.15rem 0.4rem; border-radius: 2px; margin-bottom: 4px;" placeholder="Autre">`;
    } else {
        badgeHtml = `<span class="category-badge category-${item.category}">${catLabel}</span>`;
    }

    const html = `
        <div class="line-item-row" data-category="${item.category}" draggable="true">
            <div class="drag-handle">⠿</div>
            <div style="position: relative; bottom: 0.65rem;">
                ${badgeHtml}
                <input type="text" class="form-input item-desc" value="${item.name}" placeholder="Description">
            </div>
            <div><input type="number" step="0.5" class="form-input text-center item-qty" value="1" onchange="recalculate()"></div>
            <input type="hidden" class="item-unit" value="${item.unit}">
            <div>
                <input type="number" step="1" min="0" max="100" class="form-input text-center item-discount" value="0" onchange="recalculate()" placeholder="0%">
            </div>
            <div><input type="number" step="0.01" class="form-input text-right item-price" value="${item.price.toFixed(2)}" onchange="recalculate()"></div>
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

function recalculate() {
    let totalHT = 0;
    const rows = document.querySelectorAll('.line-item-row');

    rows.forEach(row => {
        const qty = parseFloat(row.querySelector('.item-qty').value) || 0;
        const price = parseFloat(row.querySelector('.item-price').value) || 0;
        const discount = parseFloat(row.querySelector('.item-discount').value) || 0;

        const lineTotal = (qty * price) * (1 - (discount / 100));
        totalHT += lineTotal;
    });

    const tvaRate = parseFloat(document.getElementById('tvaRate').value) || 0;
    const tvaAmount = totalHT * (tvaRate / 100);
    const totalTTC = totalHT + tvaAmount;

    document.getElementById('totalHT').textContent = totalHT.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
    document.getElementById('tvaAmount').textContent = tvaAmount.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
    document.getElementById('totalTTC').textContent = totalTTC.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
}

// ── DRAG AND DROP ─────────────────────────────────────────────

let draggedRow = null;

function initDragAndDrop() {
    const list = document.getElementById('lineItemsList');
    if (!list) return;

    // Initialize existing rows
    list.querySelectorAll('.line-item-row').forEach(row => {
        row.setAttribute('draggable', 'true');
        initDragOnRow(row);
    });

    initDropZone(list);
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

        if (!draggedRow) return;

        const afterElement = getDragAfterElement(zone, e.clientY);
        if (afterElement == null) {
            zone.appendChild(draggedRow);
        } else {
            zone.insertBefore(draggedRow, afterElement);
        }

        // Maintain calculations if needed (though order doesn't change totals)
        // But it's good for the final document order
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
            const customCatInput = row.querySelector('.item-custom-cat');
            prestations.push({
                category: category,
                custom_category: customCatInput ? customCatInput.value : null,
                description: row.querySelector('.item-desc').value,
                quantity: parseFloat(row.querySelector('.item-qty').value) || 0,
                unit: row.querySelector('.item-unit').value,
                unit_price: parseFloat(row.querySelector('.item-price').value) || 0,
                discount_rate: parseFloat(row.querySelector('.item-discount').value) || 0
            });
        });

        const data = {
            production_id: document.querySelector('select[name="production_id"]').value,
            project_name: document.querySelector('input[name="project_name"]').value,
            tva_rate: parseFloat(document.getElementById('tvaRate').value) || 20.00,
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
