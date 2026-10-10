/**
 * image-compressor.js — Optimisation et compression automatique des photos côté client.
 *
 * Réduit la résolution (max 1920px) et compresse en JPEG 85% avant l'envoi HTTP
 * pour prévenir les timeouts 4G sur mobile et réduire la charge serveur / RAM WeasyPrint.
 */

(function () {
    'use strict';

    /**
     * Formate une taille en octets de manière lisible (ex: 1.4 Mo).
     */
    function formatBytes(bytes) {
        if (!bytes || bytes <= 0) return '0 o';
        const k = 1024;
        const sizes = ['o', 'Ko', 'Mo', 'Go'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    /**
     * Compresse un fichier Image unique via Canvas HTML5.
     * @param {File} file 
     * @param {Object} options { maxDimension: 1920, quality: 0.85 }
     * @returns {Promise<File>}
     */
    function compressImageFile(file, options) {
        options = options || {};
        const maxDimension = options.maxDimension || 1920;
        const quality = options.quality !== undefined ? options.quality : 0.85;

        // Ne traiter que les fichiers images (ignorer les PDFs ou documents)
        const isImage = (file.type && file.type.startsWith('image/')) ||
            /\.(jpe?g|png|webp|heic|heif)$/i.test(file.name);

        if (!isImage || file.type === 'image/svg+xml') {
            return Promise.resolve(file);
        }

        return new Promise((resolve) => {
            const img = new Image();
            let objectUrl = null;

            try {
                objectUrl = URL.createObjectURL(file);
            } catch (err) {
                resolve(file);
                return;
            }

            img.onload = function () {
                if (objectUrl) URL.revokeObjectURL(objectUrl);

                let width = img.naturalWidth || img.width;
                let height = img.naturalHeight || img.height;

                // Si l'image est déjà légère (< 400 Ko) et dans les dimensions cibles, conserver
                if (file.size < 400 * 1024 && width <= maxDimension && height <= maxDimension && file.type === 'image/jpeg') {
                    resolve(file);
                    return;
                }

                // Calcul du redimensionnement proportionnel
                if (width > maxDimension || height > maxDimension) {
                    if (width > height) {
                        height = Math.round((height * maxDimension) / width);
                        width = maxDimension;
                    } else {
                        width = Math.round((width * maxDimension) / height);
                        height = maxDimension;
                    }
                }

                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                if (!ctx) {
                    resolve(file);
                    return;
                }

                // Fond blanc uni pour éviter toute transparence noire lors de la conversion JPEG
                ctx.fillStyle = '#FFFFFF';
                ctx.fillRect(0, 0, width, height);
                ctx.drawImage(img, 0, 0, width, height);

                canvas.toBlob(
                    function (blob) {
                        if (!blob) {
                            resolve(file);
                            return;
                        }

                        // Conserver le fichier d'origine s'il était déjà plus léger et de bonne dimension
                        if (blob.size >= file.size && width === img.naturalWidth && height === img.naturalHeight) {
                            resolve(file);
                            return;
                        }

                        const baseName = file.name.replace(/\.(heic|heif|png|webp|jpeg|jpg)$/i, '');
                        const newName = (baseName || 'photo') + '.jpg';

                        const compressedFile = new File([blob], newName, {
                            type: 'image/jpeg',
                            lastModified: Date.now(),
                        });

                        resolve(compressedFile);
                    },
                    'image/jpeg',
                    quality
                );
            };

            img.onerror = function () {
                if (objectUrl) URL.revokeObjectURL(objectUrl);
                // Repli gracieux vers le fichier original (géré côté serveur par Pillow/pillow-heif)
                resolve(file);
            };

            img.src = objectUrl;
        });
    }

    /**
     * Compresse tous les fichiers présents dans un HTMLInputElement type="file".
     * @param {HTMLInputElement} input 
     * @param {Object} options 
     * @returns {Promise<{originalTotal: number, compressedTotal: number, count: number}>}
     */
    async function compressFileInput(input, options) {
        if (!input || !input.files || input.files.length === 0) {
            return { originalTotal: 0, compressedTotal: 0, count: 0 };
        }

        // Éviter les doubles compressions récursives
        if (input.dataset.compressing === 'true' || input.dataset.compressed === 'true') {
            return { originalTotal: 0, compressedTotal: 0, count: 0 };
        }

        input.dataset.compressing = 'true';

        const files = Array.from(input.files);
        let originalTotal = 0;
        files.forEach(f => originalTotal += f.size);

        // Afficher l'indicateur visuel de compression si un conteneur parent existe
        renderStatusBadge(input, 'compressing', files.length);

        const promises = files.map(f => compressImageFile(f, options));
        const compressedFiles = await Promise.all(promises);

        let compressedTotal = 0;
        compressedFiles.forEach(f => compressedTotal += f.size);

        // Remplacer la FileList via DataTransfer standard
        try {
            const dt = new DataTransfer();
            compressedFiles.forEach(f => dt.items.add(f));
            input.files = dt.files;
            input.dataset.compressed = 'true';
        } catch (dtErr) {
            console.warn('DataTransfer non supporté par ce navigateur :', dtErr);
        } finally {
            input.dataset.compressing = 'false';
        }

        renderStatusBadge(input, 'success', compressedFiles.length, originalTotal, compressedTotal);

        return {
            originalTotal: originalTotal,
            compressedTotal: compressedTotal,
            count: compressedFiles.length
        };
    }

    /**
     * Rendu visuel d'un badge d'état non intrusif pour l'utilisateur.
     */
    function renderStatusBadge(input, state, count, origSize, compSize) {
        // Trouver ou créer l'élément de feedback
        let container = input.closest('.form-group') || input.parentElement;
        if (!container) return;

        let badge = container.querySelector('.image-compress-status');
        if (!badge) {
            badge = document.createElement('div');
            badge.className = 'image-compress-status';
            // Insérer après l'input ou son label
            if (input.nextSibling) {
                container.insertBefore(badge, input.nextSibling);
            } else {
                container.appendChild(badge);
            }
        }

        if (state === 'compressing') {
            badge.className = 'image-compress-status is-compressing';
            badge.innerHTML = '<span class="image-compress-spinner"></span> Optimisation de ' + count + ' photo(s) en cours…';
        } else if (state === 'success') {
            badge.className = 'image-compress-status is-success';
            const gain = origSize > compSize ? ' (' + formatBytes(compSize) + ' au lieu de ' + formatBytes(origSize) + ')' : '';
            badge.innerHTML = '<i data-lucide="sparkles"></i> ' + count + ' photo(s) optimisée(s)' + gain;
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }
    }

    /**
     * Initialisation globale sur tous les inputs photos de la page.
     */
    function initAutoImageCompression() {
        document.addEventListener('change', async function (e) {
            const target = e.target;
            if (target && target.tagName === 'INPUT' && target.type === 'file') {
                const accept = target.getAttribute('accept') || '';
                const isImageInput = accept.includes('image') || target.classList.contains('u-file-compress');
                if (isImageInput && target.files && target.files.length > 0) {
                    if (target.dataset.compressing !== 'true' && target.dataset.compressed !== 'true') {
                        await compressFileInput(target);
                        // Émettre un événement pour signaler que les fichiers compressés sont prêts
                        target.dispatchEvent(new CustomEvent('photos-compressed', { bubbles: true }));
                    }
                }
            }
        });
    }

    // Export des méthodes dans window pour utilisation par inspections.js et annotator
    window.compressImageFile = compressImageFile;
    window.compressFileInput = compressFileInput;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAutoImageCompression);
    } else {
        initAutoImageCompression();
    }
})();
