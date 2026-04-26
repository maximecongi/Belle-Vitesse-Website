/**
 * Pre-Quote Management JS
 */

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
    
    title.textContent = `Sélectionner : ${category}`;
    modal.style.display = 'flex';
    
    renderModalList();
    
    document.getElementById('modalSearch').value = '';
    document.getElementById('modalSearch').focus();
    
    document.getElementById('modalSearch').oninput = (e) => {
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
        div.className = 'modal-list-item';
        div.style.padding = '0.75rem';
        div.style.borderBottom = '1px solid #f3f4f6';
        div.style.cursor = 'pointer';
        div.style.display = 'flex';
        div.style.justifyContent = 'space-between';
        div.style.alignItems = 'center';
        div.innerHTML = `
            <div>
                <span class="category-badge category-${item.category}">${item.sub_category}</span><br>
                <span style="font-weight: 600;">${item.name}</span>
            </div>
            <div style="font-weight: bold;">${item.price.toFixed(2)} € / ${item.unit}</div>
        `;
        div.onclick = () => {
            injectLine(item);
            closeModal();
        };
        list.appendChild(div);
    });
}

function injectLine(item) {
    const container = document.getElementById('lineItemsList');
    const html = `
        <div class="line-item-row" data-category="${item.category}">
            <div class="drag-handle">⠿</div>
            <div><input type="text" class="form-input item-desc" value="${item.name}" placeholder="Description"></div>
            <div><input type="number" step="0.25" class="form-input text-center item-qty" value="1" onchange="recalculate()"></div>
            <div><input type="text" class="form-input text-center item-unit" value="${item.unit}" placeholder="Unité"></div>
            <div><input type="number" step="0.01" class="form-input text-right item-price" value="${item.price.toFixed(2)}" onchange="recalculate()"></div>
            <div class="text-right"><button type="button" onclick="this.parentElement.parentElement.remove(); recalculate();" style="color: #ef4444; font-weight: bold; font-size: 1.2rem;">&times;</button></div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', html);
    recalculate();
}

function recalculate() {
    let totalHT = 0;
    const rows = document.querySelectorAll('.line-item-row');
    
    rows.forEach(row => {
        const qty = parseFloat(row.querySelector('.item-qty').value) || 0;
        const price = parseFloat(row.querySelector('.item-price').value) || 0;
        totalHT += qty * price;
    });
    
    const tvaRate = parseFloat(document.getElementById('tvaRate').value) || 0;
    const tvaAmount = totalHT * (tvaRate / 100);
    const totalTTC = totalHT + tvaAmount;
    
    document.getElementById('totalHT').textContent = totalHT.toLocaleString('fr-FR', { minimumFractionDigits: 2 }) + ' €';
    document.getElementById('tvaAmount').textContent = tvaAmount.toLocaleString('fr-FR', { minimumFractionDigits: 2 }) + ' €';
    document.getElementById('totalTTC').textContent = totalTTC.toLocaleString('fr-FR', { minimumFractionDigits: 2 }) + ' €';
}

async function saveQuote() {
    const btn = document.getElementById('saveBtn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Enregistrement...';
    
    try {
        const prestations = [];
        document.querySelectorAll('.line-item-row').forEach(row => {
            prestations.push({
                category: row.dataset.category,
                description: row.querySelector('.item-desc').value,
                quantity: parseFloat(row.querySelector('.item-qty').value) || 0,
                unit: row.querySelector('.item-unit').value,
                unit_price: parseFloat(row.querySelector('.item-price').value) || 0
            });
        });
        
        const data = {
            production_id: document.querySelector('select[name="production_id"]').value,
            project_name: document.querySelector('input[name="project_name"]').value,
            shoot_date: document.querySelector('input[name="shoot_date"]').value,
            shoot_location: document.querySelector('input[name="shoot_location"]').value,
            tva_rate: parseFloat(document.getElementById('tvaRate').value) || 20.00,
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
            window.location.href = '/admin/pre-quotes';
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
