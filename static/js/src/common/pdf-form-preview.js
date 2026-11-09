/**
 * pdf-form-preview.js — Aperçu PDF live des formulaires publics de signature (CGL, BVSR, BVPA, BVRA).
 *
 * - Le serveur rend le vrai PDF (template WeasyPrint de l'archive scellée) à partir des valeurs saisies.
 * - Les valeurs issues du formulaire y sont surlignées en jaune BV et portent un lien
 *   « https://preview.invalid/field/<nom> » : on lit ces annotations via pdf.js pour poser
 *   des zones cliquables qui font défiler la page jusqu'au champ et lui donnent le focus.
 * - Régénération automatique (debounce) à chaque saisie ; une seule requête en vol par onglet
 *   (les saisies intermédiaires sont regroupées), réessai automatique si le serveur répond 429,
 *   position de défilement de l'aperçu conservée.
 *
 * Dépendance : pdf.js (window.pdfjsLib) chargé depuis cdnjs par le template.
 */

const BelleVitessePdfFormPreview = (function () {
    const FIELD_URL_PREFIX = 'https://preview.invalid/field/';
    const PDFJS_WORKER_URL = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    const DEBOUNCE_MS = 800;

    function resolveField(form, key) {
        const esc = window.CSS && CSS.escape ? CSS.escape(key) : key;
        return form.querySelector('[data-pf-field="' + esc + '"]')
            || form.querySelector('[name="' + esc + '"]:not([type="hidden"])');
    }

    function fieldLabel(form, field) {
        if (!field) return '';
        const label = field.id ? form.querySelector('label[for="' + field.id + '"]') : null;
        return label ? label.textContent.split('*').join('').replace(/\s+/g, ' ').trim() : (field.name || '');
    }

    function focusField(form, key) {
        const field = resolveField(form, key);
        if (!field) return;
        // Champ masqué (bloc conditionnel) : on cible le premier ancêtre visible
        let target = field;
        while (target && target !== form && target.offsetParent === null) {
            target = target.parentElement;
        }
        (target || field).scrollIntoView({ behavior: 'smooth', block: 'center' });
        if (field.offsetParent !== null) {
            try {
                field.focus({ preventScroll: true });
            } catch (e) {
                field.focus();
            }
        }
        const group = field.closest('.form-group') || field;
        group.classList.remove('pf-field-pulse');
        // Relance de l'animation
        void group.offsetWidth;
        group.classList.add('pf-field-pulse');
        setTimeout(function () { group.classList.remove('pf-field-pulse'); }, 1600);
    }

    function init(options) {
        const root = options.container;
        const form = options.form;
        if (!root || !form) return null;
        const previewUrl = root.getAttribute('data-preview-url');
        const pagesEl = root.querySelector('.pdf-form-preview-pages');
        const statusEl = root.querySelector('.pdf-form-preview-status');
        const openLink = root.querySelector('.pdf-form-preview-open');
        const serialize = options.serialize || function () { return new FormData(form); };

        if (!previewUrl || !pagesEl) return null;
        if (!window.pdfjsLib) {
            setStatus('error', "L'aperçu PDF n'a pas pu être chargé.");
            return null;
        }
        window.pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER_URL;

        let debounceTimer = null;
        let retryTimer = null;
        let inFlight = false;      // une seule requête d'aperçu en cours par onglet
        let pending = false;       // une saisie est survenue pendant la requête en cours
        let lastSentSignature = null;
        let renderSeq = 0;
        let lastWidth = 0;
        let lastPdfBytes = null;
        let currentBlobUrl = null;

        function setStatus(state, message) {
            root.classList.toggle('is-loading', state === 'loading');
            root.classList.toggle('has-error', state === 'error');
            if (statusEl) {
                statusEl.textContent = message || '';
                statusEl.hidden = !message;
            }
        }

        function csrfToken() {
            const input = form.querySelector('input[name="csrf_token"]');
            return input ? input.value : '';
        }

        // Largeur utile des pages : clientWidth inclut le padding du conteneur (mais pas la
        // barre de défilement), on le retire pour garder la même marge à gauche et à droite.
        function availableWidth() {
            const styles = window.getComputedStyle(pagesEl);
            const padding = (parseFloat(styles.paddingLeft) || 0) + (parseFloat(styles.paddingRight) || 0);
            const inner = (pagesEl.clientWidth || root.clientWidth || 600) - padding;
            return Math.max(Math.floor(inner), 200);
        }

        async function renderPdf(bytes, seq) {
            const pdf = await window.pdfjsLib.getDocument({ data: bytes.slice(0) }).promise;
            const width = availableWidth();
            const dpr = window.devicePixelRatio || 1;
            const fragment = document.createDocumentFragment();

            for (let n = 1; n <= pdf.numPages; n++) {
                const page = await pdf.getPage(n);
                if (seq !== renderSeq) return false;
                const base = page.getViewport({ scale: 1 });
                const viewport = page.getViewport({ scale: width / base.width });

                const pageEl = document.createElement('div');
                pageEl.className = 'pdf-form-preview-page';
                pageEl.style.width = viewport.width + 'px';
                pageEl.style.height = viewport.height + 'px';

                const canvas = document.createElement('canvas');
                canvas.width = Math.floor(viewport.width * dpr);
                canvas.height = Math.floor(viewport.height * dpr);
                canvas.style.width = viewport.width + 'px';
                canvas.style.height = viewport.height + 'px';
                pageEl.appendChild(canvas);

                await page.render({
                    canvasContext: canvas.getContext('2d'),
                    viewport: viewport,
                    transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null,
                }).promise;

                const annotations = await page.getAnnotations();
                annotations.forEach(function (annot) {
                    if (annot.subtype !== 'Link' || !annot.url || annot.url.indexOf(FIELD_URL_PREFIX) !== 0) return;
                    const key = decodeURIComponent(annot.url.slice(FIELD_URL_PREFIX.length));
                    const rect = viewport.convertToViewportRectangle(annot.rect);
                    const left = Math.min(rect[0], rect[2]);
                    const top = Math.min(rect[1], rect[3]);
                    const hit = document.createElement('button');
                    hit.type = 'button';
                    hit.className = 'pdf-form-preview-hit';
                    hit.setAttribute('data-pf-key', key);
                    hit.style.left = left + 'px';
                    hit.style.top = top + 'px';
                    hit.style.width = Math.abs(rect[2] - rect[0]) + 'px';
                    hit.style.height = Math.abs(rect[3] - rect[1]) + 'px';
                    const label = fieldLabel(form, resolveField(form, key));
                    hit.setAttribute('aria-label', 'Modifier : ' + (label || key));
                    hit.title = label ? 'Modifier « ' + label + ' »' : 'Modifier ce champ';
                    pageEl.appendChild(hit);
                });
                fragment.appendChild(pageEl);
            }
            if (seq !== renderSeq) return false;

            // Remplacement sans clignotement en conservant la position de lecture
            const scrollTop = pagesEl.scrollTop;
            pagesEl.replaceChildren(fragment);
            pagesEl.scrollTop = scrollTop;
            lastWidth = width;
            pdf.destroy();
            return true;
        }

        // Empreinte des valeurs texte du formulaire : évite de redemander un aperçu identique
        function payloadSignature(formData) {
            const parts = [];
            formData.forEach(function (value, key) {
                if (key === 'csrf_token' || typeof value !== 'string') return;
                parts.push(key + '=' + value);
            });
            return parts.join('\u0001');
        }

        async function refresh() {
            clearTimeout(retryTimer);
            // Pas de requêtes concurrentes : le serveur ne sait pas interrompre un rendu
            // WeasyPrint en cours. On mémorise la saisie et on relance une fois la requête finie.
            if (inFlight) {
                pending = true;
                return;
            }
            const body = serialize();
            const signature = payloadSignature(body);
            if (signature === lastSentSignature) return;

            inFlight = true;
            const seq = ++renderSeq;
            setStatus('loading', '');
            try {
                const response = await fetch(previewUrl, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken() },
                    body: body,
                    credentials: 'same-origin',
                });
                if (response.status === 429) {
                    // Serveur occupé (plafond de rendus simultanés) ou quota atteint : nouvel essai
                    const retryAfter = parseInt(response.headers.get('Retry-After') || '', 10);
                    const delay = (isNaN(retryAfter) ? 3 : Math.min(Math.max(retryAfter, 1), 30)) * 1000;
                    setStatus('loading', 'Aperçu en attente…');
                    // Le réessai enverra de toute façon le dernier état du formulaire
                    pending = false;
                    retryTimer = setTimeout(refresh, delay);
                    return;
                }
                if (!response.ok) throw new Error('HTTP ' + response.status);
                const buffer = await response.arrayBuffer();
                lastSentSignature = signature;
                lastPdfBytes = new Uint8Array(buffer);

                // Lien « Ouvrir le PDF » vers le dernier aperçu reçu (ouverture dans un nouvel onglet)
                if (openLink) {
                    if (currentBlobUrl) URL.revokeObjectURL(currentBlobUrl);
                    currentBlobUrl = URL.createObjectURL(new Blob([buffer], { type: 'application/pdf' }));
                    openLink.href = currentBlobUrl;
                    openLink.hidden = false;
                }

                const done = await renderPdf(lastPdfBytes, seq);
                if (done && !pending) setStatus('idle', '');
            } catch (err) {
                console.error('Aperçu PDF :', err);
                setStatus('error', "Impossible d'actualiser l'aperçu pour le moment. Le dernier aperçu reste affiché.");
            } finally {
                inFlight = false;
                if (pending) {
                    pending = false;
                    refresh();
                }
            }
        }

        function schedule() {
            clearTimeout(debounceTimer);
            clearTimeout(retryTimer);
            debounceTimer = setTimeout(refresh, DEBOUNCE_MS);
        }

        form.addEventListener('input', function (e) {
            if (e.target && e.target.type === 'file') return;
            schedule();
        });
        form.addEventListener('change', function (e) {
            if (e.target && (e.target.type === 'file' || e.target.type === 'checkbox')) return;
            schedule();
        });

        pagesEl.addEventListener('click', function (e) {
            const hit = e.target.closest('.pdf-form-preview-hit');
            if (!hit) return;
            e.preventDefault();
            focusField(form, hit.getAttribute('data-pf-key'));
        });

        // Re-rendu (sans nouvel appel serveur) si la largeur du conteneur change
        let resizeTimer = null;
        window.addEventListener('resize', function () {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function () {
                if (!lastPdfBytes) return;
                if (Math.abs(availableWidth() - lastWidth) < 8) return;
                renderPdf(lastPdfBytes, ++renderSeq);
            }, 250);
        });

        refresh();
        return { refresh: refresh, schedule: schedule };
    }

    return { init: init, focusField: focusField };
})();

window.BelleVitessePdfFormPreview = BelleVitessePdfFormPreview;
