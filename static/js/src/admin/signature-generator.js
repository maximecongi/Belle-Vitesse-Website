/**
 * signature-generator.js — Générateur d'aperçu dynamique et de code HTML pour signatures email Belle Vitesse.
 */

function initSignatureGenerator() {
    const nameInput = document.getElementById('f-name');
    const jobInput = document.getElementById('f-job');
    const emailInput = document.getElementById('f-email');
    const phoneInput = document.getElementById('f-phone');
    const codeOutput = document.getElementById('code-output');
    const sigPreview = document.getElementById('sig-preview');
    const copyBtn = document.getElementById('copy-btn');

    if (!nameInput || !jobInput || !emailInput || !phoneInput || !codeOutput || !sigPreview || !copyBtn) {
        return;
    }

    function esc(s) {
        if (!s) return "";
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function buildHtml(name, job, emailLocal, phone) {
        const email = emailLocal.trim() + '@bellevitesse.com';
        const tel = phone.replace(/\s/g, '');
        return [
            '<html>',
            '<body style="margin:0;padding:0;font-family:Helvetica Neue,Helvetica,Arial,sans-serif;">',
            '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;">',
            '  <tr>',
            '    <td style="padding-bottom:12px;">',
            '      <div style="width:100%;height:2px;background:#ffc845;"></div>',
            '    </td>',
            '  </tr>',
            '  <tr>',
            '    <td>',
            '      <table cellpadding="0" cellspacing="0" style="border-collapse:collapse;">',
            '        <tr>',
            '          <td style="padding-right:20px;vertical-align:middle;border-right:1px solid #e8e8e8;">',
            '            <img src="https://bellevitesse.com/static/CDN/noir-fond-transparent.png" width="90" style="display:block;" />',
            '          </td>',
            '          <td style="padding-left:20px;vertical-align:middle;">',
            '            <p style="margin:0 0 1px;font-size:15px;font-weight:700;color:#0f0f0f;">' + name + '</p>',
            '            <p style="margin:0 0 10px;font-size:9px;color:#ffc845;text-transform:uppercase;letter-spacing:0.14em;font-weight:600;">' + job + '</p>',
            '            <table cellpadding="0" cellspacing="0">',
            '              <tr><td style="padding-bottom:4px;">',
            '                <span style="display:inline-block;width:3px;height:3px;background:#ffc845;vertical-align:middle;margin-right:6px;"></span>',
            '                <a href="mailto:' + email + '" style="font-size:11px;color:#333;text-decoration:none;">' + email + '</a>',
            '              </td></tr>',
            '              <tr><td style="padding-bottom:4px;">',
            '                <span style="display:inline-block;width:3px;height:3px;background:#ffc845;vertical-align:middle;margin-right:6px;"></span>',
            '                <a href="tel:' + tel + '" style="font-size:11px;color:#333;text-decoration:none;">' + phone + '</a>',
            '              </td></tr>',
            '              <tr><td style="padding-bottom:4px;">',
            '                <span style="display:inline-block;width:3px;height:3px;background:#ffc845;vertical-align:middle;margin-right:6px;"></span>',
            '                <a href="https://bellevitesse.com" style="font-size:11px;color:#333;text-decoration:none;">bellevitesse.com</a>',
            '              </td></tr>',
            '              <tr><td>',
            '                <span style="display:inline-block;width:3px;height:3px;background:#e0e0e0;vertical-align:middle;margin-right:6px;"></span>',
            '                <span style="font-size:11px;color:#999;">Belle Vitesse SAS</span>',
            '              </td></tr>',
            '            </table>',
            '          </td>',
            '        </tr>',
            '      </table>',
            '    </td>',
            '  </tr>',
            '</table>',
            '</body>',
            '</html>'
        ].join('\n');
    }

    function syntaxColor(raw) {
        let code = esc(raw);
        code = code.replace(/(&lt;\/?)([\w]+)/g, '<span class="t-punct">$1</span><span class="t-tag">$2</span>');
        code = code.replace(/ ([\w-]+)=(&quot;)(.*?)(&quot;)/g, ' <span class="t-attr">$1</span><span class="t-punct">=</span><span class="t-punct">&quot;</span><span class="t-val">$3</span><span class="t-punct">&quot;</span>');
        code = code.replace(/(&gt;)/g, '<span class="t-punct">$1</span>');
        return code;
    }

    function update() {
        const name = nameInput.value || '';
        const job = jobInput.value || '';
        const emailLocal = emailInput.value || '';
        const phone = phoneInput.value || '';
        const email = emailLocal.trim() + '@bellevitesse.com';
        const tel = phone.replace(/\s/g, '');

        const raw = buildHtml(name, job, emailLocal, phone);
        codeOutput.innerHTML = syntaxColor(raw);
        copyBtn.dataset.raw = raw;

        const previewHtml = [
            '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse; font-family:Helvetica Neue,Helvetica,Arial,sans-serif;">',
            '  <tr>',
            '    <td style="padding-bottom:12px;">',
            '      <div style="width:100%;height:2px;background:#ffc845;"></div>',
            '    </td>',
            '  </tr>',
            '  <tr>',
            '    <td>',
            '      <table cellpadding="0" cellspacing="0" style="border-collapse:collapse;">',
            '        <tr>',
            '          <td style="padding-right:20px;vertical-align:middle;border-right:1px solid #e8e8e8;">',
            '            <img src="https://bellevitesse.com/static/CDN/noir-fond-transparent.png" width="90" style="display:block;" />',
            '          </td>',
            '          <td style="padding-left:20px;vertical-align:middle;">',
            '            <p style="margin:0 0 1px;font-size:15px;font-weight:700;color:#0f0f0f;">' + name + '</p>',
            '            <p style="margin:0 0 10px;font-size:9px;color:#ffc845;text-transform:uppercase;letter-spacing:0.14em;font-weight:600;">' + job + '</p>',
            '            <table cellpadding="0" cellspacing="0">',
            '              <tr><td style="padding-bottom:4px;">',
            '                <span class="sig-dot"></span>',
            '                <a href="mailto:' + email + '" style="font-size:11px;color:#333;text-decoration:none;">' + email + '</a>',
            '              </td></tr>',
            '              <tr><td style="padding-bottom:4px;">',
            '                <span class="sig-dot"></span>',
            '                <a href="tel:' + tel + '" style="font-size:11px;color:#333;text-decoration:none;">' + phone + '</a>',
            '              </td></tr>',
            '              <tr><td style="padding-bottom:4px;">',
            '                <span class="sig-dot"></span>',
            '                <a href="https://bellevitesse.com" style="font-size:11px;color:#333;text-decoration:none;">bellevitesse.com</a>',
            '              </td></tr>',
            '              <tr><td>',
            '                <span class="sig-dot muted"></span>',
            '                <span style="font-size:11px;color:#999;">Belle Vitesse SAS</span>',
            '              </td></tr>',
            '            </table>',
            '          </td>',
            '        </tr>',
            '      </table>',
            '    </td>',
            '  </tr>',
            '</table>'
        ].join('\n');

        sigPreview.innerHTML = previewHtml;
    }

    [nameInput, jobInput, emailInput, phoneInput].forEach(inp => {
        if (!inp._hasSigListener) {
            inp._hasSigListener = true;
            inp.addEventListener('input', update);
        }
    });

    if (!copyBtn._hasCopyListener) {
        copyBtn._hasCopyListener = true;
        copyBtn.addEventListener('click', function () {
            const raw = copyBtn.dataset.raw || '';
            navigator.clipboard.writeText(raw).then(function () {
                const originalText = copyBtn.textContent;
                copyBtn.textContent = 'Copié ✓';
                copyBtn.classList.remove('admin-btn-secondary');
                copyBtn.classList.add('admin-btn-primary');
                setTimeout(function () {
                    copyBtn.textContent = originalText;
                    copyBtn.classList.remove('admin-btn-primary');
                    copyBtn.classList.add('admin-btn-secondary');
                }, 2000);
            });
        });
    }

    update();
}

window.initSignatureGenerator = initSignatureGenerator;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSignatureGenerator);
} else {
    initSignatureGenerator();
}
document.addEventListener('swup:contentReplaced', initSignatureGenerator);

