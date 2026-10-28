/**
 * mcp-modal.js — Contrôleur modulaire unifié pour la modale MCP et les connecteurs API.
 * Utilisé dans settings.html et mcp_connector.html.
 */

function initMcpModal() {
    const modal = document.getElementById('mcpTokenModal');
    if (!modal && !document.getElementById('mcpStatusBadge') && !document.querySelector('.tab-btn')) {
        return;
    }

    // 1. Boutons d'ouverture de la modale
    const openBtns = [
        document.getElementById('openCreateTokenModal'),
        ...document.querySelectorAll('.openCreateTokenModalBtn')
    ].filter(Boolean);

    const closeBtn = document.getElementById('closeMcpModal');
    const confirmCloseBtn = document.getElementById('confirmMcpModalClose');
    const refreshBtn = document.getElementById('modalCloseAndRefresh');
    const modalResultBlock = document.getElementById('modalResultBlock');

    // 2. Formulaire de génération de jeton (support des deux IDs : settings et mcp_connector)
    const form = document.getElementById('generateMcpTokenForm') || document.getElementById('generateMcpTokenFormModal');
    const rawTokenInput = document.getElementById('mcpRawTokenInput') || document.getElementById('modalRawTokenInput');
    const claudeUrlInput = document.getElementById('mcpClaudeUrlInput') || document.getElementById('modalClaudeUrlInput');
    const configPreview = document.getElementById('mcpConfigPreview');

    openBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            if (modal) modal.style.display = 'flex';
            if (modalResultBlock) modalResultBlock.style.display = 'none';
            if (form) form.style.display = 'block';
        });
    });

    function closeModalAndReload() {
        if (modal) modal.style.display = 'none';
        window.location.reload();
    }

    if (closeBtn) closeBtn.addEventListener('click', () => {
        if (refreshBtn || confirmCloseBtn) closeModalAndReload();
        else if (modal) modal.style.display = 'none';
    });
    if (confirmCloseBtn) confirmCloseBtn.addEventListener('click', closeModalAndReload);
    if (refreshBtn) refreshBtn.addEventListener('click', closeModalAndReload);

    if (modal) {
        modal.addEventListener('click', function (e) {
            if (e.target === modal) closeModalAndReload();
        });
    }

    if (form) {
        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            const formData = new FormData(form);
            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    body: formData
                });
                const data = await response.json();
                if (response.ok && data.raw_token) {
                    if (modalResultBlock) {
                        form.style.display = 'none';
                        modalResultBlock.style.display = 'block';
                    }
                    if (rawTokenInput) rawTokenInput.value = data.raw_token;

                    const isLocal = window.location.origin.includes('127.0.0.1') || window.location.origin.includes('localhost');
                    const mcpUrl = isLocal ? "http://127.0.0.1:8080/mcp" : "https://team.bellevitesse.com/mcp";
                    const directClaudeUrl = `${mcpUrl}?token=${data.raw_token}`;

                    if (claudeUrlInput) claudeUrlInput.value = directClaudeUrl;

                    if (configPreview) {
                        configPreview.textContent = JSON.stringify({
                            "mcpServers": {
                                "BV-MCP": {
                                    "url": mcpUrl,
                                    "headers": {
                                        "Authorization": `Bearer ${data.raw_token}`
                                    }
                                }
                            }
                        }, null, 2);
                    }

                    if (modal && !modalResultBlock) {
                        modal.style.display = 'flex';
                    }
                } else {
                    alert(data.message || 'Erreur lors de la génération du token.');
                }
            } catch (err) {
                console.error("Erreur génération MCP token:", err);
                alert("Erreur lors de la communication avec le serveur.");
            }
        });
    }

    // 3. Gestion de la copie dans le presse-papier
    function setupCopyButton(btnId, inputEl, copiedLabel) {
        const btn = document.getElementById(btnId);
        if (!btn || !inputEl) return;
        btn.addEventListener('click', function () {
            const val = inputEl.value !== undefined ? inputEl.value : inputEl;
            if (inputEl.select) inputEl.select();
            navigator.clipboard.writeText(val).then(() => {
                const orig = btn.innerHTML;
                btn.innerHTML = copiedLabel || '✅ Copié !';
                setTimeout(() => btn.innerHTML = orig, 2500);
            }).catch(err => console.error("Erreur copie:", err));
        });
    }

    setupCopyButton('copyMcpTokenBtn', rawTokenInput, '✅ Copié !');
    setupCopyButton('modalCopyRawTokenBtn', rawTokenInput, '✅ Copié !');
    setupCopyButton('copyClaudeUrlBtn', claudeUrlInput, '✅ URL Copiée !');
    setupCopyButton('modalCopyClaudeUrlBtn', claudeUrlInput, '✅ Copié !');

    const copyEndpointBtn = document.getElementById('copyEndpointBtn');
    if (copyEndpointBtn) {
        copyEndpointBtn.addEventListener('click', function () {
            navigator.clipboard.writeText('https://team.bellevitesse.com/mcp').then(() => {
                copyEndpointBtn.textContent = '✅ Copié !';
                setTimeout(() => copyEndpointBtn.textContent = 'Copier', 2000);
            });
        });
    }

    // 4. Vérification dynamique du statut du serveur MCP
    const statusBadge = document.getElementById('mcpStatusBadge');
    if (statusBadge) {
        const isLocal = window.location.origin.includes('127.0.0.1') || window.location.origin.includes('localhost');
        const healthUrl = isLocal ? 'http://127.0.0.1:8080/health' : 'https://team.bellevitesse.com/mcp/health';
        fetch(healthUrl, { method: 'GET' })
            .then(res => res.json())
            .then(data => {
                if (data && data.status === 'healthy') {
                    statusBadge.className = 'badge-pill u-bg-success u-text-white';
                    statusBadge.textContent = 'EN LIGNE (Streamable HTTP)';
                } else {
                    statusBadge.className = 'badge-pill u-bg-danger u-text-white';
                    statusBadge.textContent = 'SERVEUR NON DISPONIBLE';
                }
            })
            .catch(() => {
                statusBadge.className = 'badge-pill u-bg-danger u-text-white';
                statusBadge.textContent = 'HORS LIGNE';
            });
    }

    // 5. Gestion des Onglets
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            tabBtns.forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.add('u-d-none'));
            btn.classList.add('active');
            const targetId = btn.getAttribute('data-tab');
            const targetEl = document.getElementById(targetId);
            if (targetEl) targetEl.classList.remove('u-d-none');
        });
    });
}

window.initMcpModal = initMcpModal;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMcpModal);
} else {
    initMcpModal();
}
document.addEventListener('swup:contentReplaced', initMcpModal);

