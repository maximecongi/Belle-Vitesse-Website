/**
 * public.bundle.js — Bundle JavaScript unifié pour le site public Belle Vitesse.
 * Concaténé et validé automatiquement par scripts/build_bundles.py.
 */

/* ── js/src/common/image-compressor.js ── */
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
;

/* ── js/src/initialization.js ── */
function initDropdowns() {
    const dropdowns = document.querySelectorAll('.menu-item-dropdown');

    dropdowns.forEach(dropdown => {
        const links = dropdown.querySelectorAll('.dropdown-left a');
        const previewImage = dropdown.querySelector('.dropdown-image-preview');

        if (!previewImage) return;

        links.forEach(link => {
            link.addEventListener('mouseenter', () => {
                const imageUrl = link.getAttribute('data-image');
                if (imageUrl) {
                    previewImage.src = imageUrl;
                    previewImage.classList.add('show');
                } else {
                    previewImage.classList.remove('show');
                    previewImage.src = '';
                }
            });
        });

        const wrapper = dropdown.querySelector('.dropdown-wrapper');
        if (wrapper) {
            wrapper.addEventListener('mouseleave', () => {
                const defaultSrc = previewImage.getAttribute('data-default-src');
                if (defaultSrc) {
                    previewImage.src = defaultSrc;
                    previewImage.classList.add('show');
                } else {
                    previewImage.classList.remove('show');
                }
            });
        }
    });
}

function initContent() {
    // Re-initialize components that are inside the #swup container
    if (typeof window.initSplide === 'function') {
        window.initSplide();
    }
    if (typeof window.initFilterSliders === 'function') {
        window.initFilterSliders();
    }
    if (typeof window.initMap === 'function') {
        window.initMap();
    }
    if (typeof window.initCountUp === 'function') {
        window.initCountUp();
    }
    // Re-initialize Alpine.js for the new content
    if (window.Alpine) {
        window.Alpine.initTree(document.body);
    }
    if (typeof window.initConfigurator === 'function') {
        window.initConfigurator();
    }
    if (typeof window.initInfiniteScroll === 'function') {
        window.initInfiniteScroll();
    }
    initNewsletterForm();
    initVideos();
}

function initVideos() {
    const videos = document.querySelectorAll('video[autoplay]');
    videos.forEach(video => {
        video.play().catch(error => {
            console.log("Autoplay prevented:", error);
        });
    });
}

function initNewsletterForm() {
    const forms = document.querySelectorAll('.newsletter-form');

    forms.forEach(form => {
        // Find the specific message div and input for this form
        const container = form.closest('.newsletter');
        const messageDiv = container ? container.querySelector('.newsletter-message') : null;
        const input = form.querySelector('input[name="email"]');
        const button = form.querySelector('button[type="submit"]');

        if (!input || !messageDiv) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const email = input.value;
            const isFr = window.location.pathname.startsWith('/fr/');
            
            // 🚀 Add loading state
            messageDiv.className = 'newsletter-message';
            messageDiv.textContent = isFr ? 'Inscription en cours...' : 'Subscribing...';
            messageDiv.classList.add('show');
            if (button) button.disabled = true;

            try {
                const formData = new FormData(form);
                formData.set('email', email);
                formData.set('lang', isFr ? 'fr' : 'en');

                const response = await fetch('/subscribe', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                messageDiv.textContent = data.message;
                messageDiv.classList.add('show');
                if (response.ok) {
                    messageDiv.classList.add('success');
                    form.reset();
                } else {
                    messageDiv.classList.add('error');
                }

                if (button) button.disabled = false;

                // Hide after 3 seconds
                setTimeout(() => {
                    messageDiv.classList.remove('show');
                    // Optional: clear text after fade out finishes
                    setTimeout(() => {
                        if (!messageDiv.classList.contains('show')) {
                            messageDiv.textContent = '';
                        }
                    }, 500);
                }, 3000);

            } catch (error) {
                console.error('Error:', error);
                messageDiv.textContent = 'An error occurred. Please try again.';
                messageDiv.className = 'newsletter-message error show';
                if (button) button.disabled = false;

                setTimeout(() => {
                    messageDiv.classList.remove('show');
                }, 3000);
            }
        });
    });
}

// Swup Initialization
const swup = new Swup({
    plugins: [new SwupPreloadPlugin()]
});

swup.hooks.on('content:replace', () => {
    initContent();
    // Header is now persistent, so we don't re-run initDropdowns()

    // Close mobile menu
    const menuCheckbox = document.getElementById('active');
    if (menuCheckbox) {
        menuCheckbox.checked = false;
    }

    // Update language selector links to match the current page
    updateLangLinks();
});

function updateLangLinks() {
    const path = window.location.pathname;
    document.querySelectorAll('.header-lang-link').forEach(link => {
        const linkText = link.textContent.trim().toLowerCase(); // 'en' or 'fr'
        // Replace the lang prefix in current path: /en/... → /fr/... or vice versa
        const newPath = path.replace(/^\/(en|fr)\//, '/' + linkText + '/');
        link.setAttribute('href', newPath);
        // Update active state
        const currentLang = path.match(/^\/(en|fr)\//)?.[1];
        link.classList.toggle('active', linkText === currentLang);
    });
}

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    initDropdowns(); // Run once for the header
    initContent();   // Run for the initial content
});
;

/* ── js/src/splide.js ── */
window.initSplide = function () {
    var splides = document.querySelectorAll('.splide');
    if (splides.length) {
        for (var i = 0; i < splides.length; i++) {
            new Splide(splides[i], {
                type: 'loop',
            }).mount();
        }
    }
};
;

/* ── js/src/countup.js ── */
document.documentElement.classList.add('js')

window.initCountUp = function () {
  const ease = t => 1 - Math.pow(1 - t, 7)

  const observer = new IntersectionObserver(entries => {
    entries.forEach(({ isIntersecting, target }) => {
      if (!isIntersecting || target.dataset.done) return
      target.dataset.done = true
      target.classList.add('is-visible')

      const end = Number(target.dataset.target)
      const decimals = (target.dataset.target.split('.')[1] || '').length
      const startValue = end * 0.5
      const startTime = performance.now()
      const duration = 1500

      const tick = now => {
        const t = Math.min((now - startTime) / duration, 1)
        const value = startValue + ease(t) * (end - startValue)

        target.textContent = value.toFixed(decimals)

        if (t < 1) requestAnimationFrame(tick)
        else target.textContent = end.toFixed(decimals)
      }

      requestAnimationFrame(tick)
      observer.unobserve(target)
    })
  }, { threshold: 0.6 })

  document.querySelectorAll('.count-up').forEach(el => observer.observe(el))
}
;

/* ── js/src/configurator.js ── */
window.initConfigurator = function () {
    const buttons = document.querySelectorAll('.config-btn');
    const image = document.getElementById('configurator-image');

    if (buttons.length > 0 && image) {
        buttons.forEach(button => {
            // Remove existing event listeners to avoid duplicates if re-initialized (though simple replacement avoids this issue usually)
            // A clearer way is to clone node or just rely on Swup replacing the DOM entirely.
            // Since Swup replaces #swup content, the buttons are new elements, so we don't need to worry about duplicate listeners on the same element.

            button.addEventListener('click', function () {
                // Update active state
                const allButtons = document.querySelectorAll('.config-btn'); // Re-query directly to be safe
                allButtons.forEach(btn => {
                    btn.classList.remove('active');
                    btn.classList.add('inactive');
                });
                this.classList.remove('inactive');
                this.classList.add('active');

                // Update image
                const newSrc = this.getAttribute('data-image');
                const newAlt = this.getAttribute('data-label');
                const currentImage = document.getElementById('configurator-image');

                // Optional: valid newSrc check
                if (newSrc && currentImage) {
                    currentImage.src = newSrc;
                    currentImage.alt = newAlt;
                }
            });
        });
    }
};

document.addEventListener("DOMContentLoaded", function () {
    // We let initialization.js handle the calling of initConfigurator via initContent
});
;

/* ── js/src/infinite-scroll.js ── */
window.infiniteScrollId = null; // Store requestAnimationFrame ID globally to cancel it

window.initInfiniteScroll = function () {
  const wrapper = document.querySelector('.home-references-wrapper');
  const group = document.querySelector('.home-references-group');

  if (!wrapper || !group) return;

  // Clean up existing loop if restarting
  if (window.infiniteScrollId) {
    cancelAnimationFrame(window.infiniteScrollId);
  }

  // Check if we already duplicated the group to avoid infinite duplication on re-init
  if (!wrapper.querySelector('.duplicated-group')) {
    const clone = group.cloneNode(true);
    clone.classList.add('duplicated-group');
    wrapper.appendChild(clone);
  }

  let x = 0;
  const speed = 1.5;
  let running = true;

  function loop() {
    const ratio = window.innerWidth / window.innerHeight;

    if (ratio <= 1) {
      // Portrait → animation active
      if (!running) running = true;
      x -= speed;
      // Use offsetWidth for layout-bound width, which includes padding/borders if box-sizing is border-box
      // effectively matching the visual cycle.
      if (Math.abs(x) >= group.offsetWidth) {
        x = 0;
      }
      wrapper.style.transform = `translate3d(${x}px, 0, 0)`;
    } else {
      // Paysage → stop
      if (running) {
        wrapper.style.transform = 'translate3d(0,0,0)';
        running = false;
      }
    }

    window.infiniteScrollId = requestAnimationFrame(loop);
  }

  loop();
};
;

/* ── js/src/filtersliders.js ── */
(() => {
    // =========================
    // INIT
    // =========================

    let sliders = [];
    let vehicles = [];

    window.initFilterSliders = function () {
        const sliderContainers = document.querySelectorAll(".slider-container");
        vehicles = Array.from(document.querySelectorAll(
            ".categories-solutions-categories-categorywrapper"
        ));

        sliders = [];

        sliderContainers.forEach((container) => {
            sliders.push(initSlider(container));
        });

        // premier filtrage APRÈS init complète
        applyFilters();
    };

    // =========================
    // SLIDER SETUP
    // =========================

    function initSlider(container) {
        const slider = container.querySelector(".js-slider");
        const output = container.querySelector(".slider__value");

        if (!slider || !output) return null;

        const update = () => {
            const value = parseInt(slider.value, 10);

            output.textContent = value;
            updateDescription(container, value);

            applyFilters();
        };

        slider.addEventListener("input", update);

        // init affichage (sans filtrer encore)
        output.textContent = slider.value;
        updateDescription(container, parseInt(slider.value, 10));

        return {
            filterKey: container.dataset.filterKey,
            getValue: () => parseInt(slider.value, 10)
        };
    }

    // =========================
    // AND FILTER LOGIC
    // =========================

    function applyFilters() {
        vehicles.forEach((vehicle) => {
            const isVisible = sliders.every((slider) => {
                if (!slider) return true;
                const { filterKey, getValue } = slider;
                const vehicleValue = parseInt(vehicle.dataset[filterKey], 10);

                if (Number.isNaN(vehicleValue)) return true;

                return getValue() <= vehicleValue;
            });

            if (isVisible) {
                show(vehicle);
            } else {
                hide(vehicle);
            }
        });
    }

    // =========================
    // DESCRIPTION HANDLER
    // =========================

    function updateDescription(container, value) {
        const descEl = container.querySelector(".slider__description");
        if (!descEl) return;

        const descriptions = JSON.parse(container.dataset.descriptions || "[]");

        let text = "";

        descriptions.forEach(([min, desc]) => {
            if (value >= min) {
                text = desc;
            }
        });

        descEl.textContent = text;
    }

    // =========================
    // ANIMATION HELPERS
    // =========================

    function hide(el) {
        if (el.classList.contains("filterslider-is-hidden")) return;

        el.classList.add("filterslider-is-hiding");

        el.addEventListener(
            "transitionend",
            () => {
                el.classList.remove("filterslider-is-hiding");
                el.classList.add("filterslider-is-hidden");
            },
            { once: true }
        );
    }

    function show(el) {
        if (!el.classList.contains("filterslider-is-hidden")) return;

        el.classList.remove("filterslider-is-hidden");
        el.classList.add("filterslider-is-showing");

        // force reflow
        el.offsetHeight;

        el.classList.remove("filterslider-is-showing");
    }

    // =========================
    // ANIMATION BUTTON
    // =========================

    document.addEventListener("DOMContentLoaded", () => {
        const filterSliders = document.querySelector(".filtersliders-container");
        if (!filterSliders) return;

        if (filterSliders.classList.contains("filterslider-is-open")) {
            filterSliders.style.maxHeight = filterSliders.scrollHeight + "px";
        } else {
            filterSliders.style.maxHeight = "0px";
        }
    });
    window.addEventListener("resize", () => {
        const filterSliders = document.querySelector(".filtersliders-container");
        if (!filterSliders) return;

        if (filterSliders.classList.contains("filterslider-is-open")) {
            filterSliders.style.maxHeight = filterSliders.scrollHeight + "px";
        }
    });
    document.addEventListener("click", (e) => {
        const button = e.target.closest(".slider-dropdown-button");
        if (!button) return;

        const filterSliders = document.querySelector(".filtersliders-container");
        if (!filterSliders) return;

        const isOpen = filterSliders.classList.contains("filterslider-is-open");

        if (isOpen) {
            // CLOSE
            filterSliders.style.maxHeight = "0px";
            filterSliders.classList.remove("filterslider-is-open");
        } else {
            // OPEN
            filterSliders.style.maxHeight = filterSliders.scrollHeight + "px";
            filterSliders.classList.add("filterslider-is-open");
        }
    });
})();
;

/* ── js/src/public/sign-cgl.js ── */
/**
 * sign-cgl.js — Contrôleur public pour la signature des Conditions Générales de Location (CGL).
 * 
 * Fonctionnalités :
 * - Synchronisation en temps réel des champs légaux dans le texte contractuel
 * - Autocomplétion d'adresse via l'API adresse.data.gouv.fr
 * - Capture et scellement de la signature électronique via SignaturePad
 * - Validation des conditions obligatoires et soumission asynchrone sécurisée
 */

document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('cgl-form');
    if (!form) return;

    // ── 1. Synchronisation temps réel des mentions légales ─────────────────────
    const fieldsToSync = [
        { inputId: 'cgl_production_name', textId: 'cgl_text_production_name', defaultText: '…' },
        { inputId: 'cgl_representative', textId: 'cgl_text_representative', defaultText: '…' },
        { inputId: 'cgl_address', textId: 'cgl_text_address', defaultText: '…' },
        { inputId: 'cgl_siret', textId: 'cgl_text_siret', defaultText: '…' },
        { inputId: 'cgl_vat_number', textId: 'cgl_text_vat', defaultText: '…' },
        // Synchronisation Annexe 2
        { inputId: 'cgl_production_name', textId: 'cgl_text_annexe2_production_name', defaultText: '…' },
        { inputId: 'cgl_siret', textId: 'cgl_text_annexe2_siret', defaultText: '—' },
        { inputId: 'cgl_vat_number', textId: 'cgl_text_annexe2_vat', defaultText: '—' },
        { inputId: 'cgl_representative', textId: 'cgl_text_annexe2_representative', defaultText: '—' },
        { inputId: 'cgl_representative', textId: 'cgl_text_annexe2_sign_name', defaultText: '—' },
        { inputId: 'cgl_representative_role', textId: 'cgl_text_annexe2_role', defaultText: 'Représentant légal' },
        { inputId: 'cgl_representative_role', textId: 'cgl_text_annexe2_sign_role', defaultText: 'Représentant légal' },
        { inputId: 'cgl_address', textId: 'cgl_text_annexe2_address', defaultText: '—' },
        { inputId: 'cgl_phone', textId: 'cgl_text_annexe2_phone', defaultText: '—' },
        { inputId: 'cgl_email', textId: 'cgl_text_annexe2_email', defaultText: '—' },
        { inputId: 'cgl_city', textId: 'cgl_text_annexe2_city', defaultText: '—' },
        { inputId: 'cgl_order_ref', textId: 'cgl_text_annexe2_order_ref', defaultText: '—' },
    ];

    function updateCglContractText() {
        fieldsToSync.forEach(function (item) {
            const inputEl = document.getElementById(item.inputId);
            const textEl = document.getElementById(item.textId);
            if (inputEl && textEl) {
                const val = inputEl.value.trim();
                textEl.textContent = val || item.defaultText;
            }
        });

        // Synchronisation combinée de la forme juridique et du pays (Annexe 2)
        const legalFormEl = document.getElementById('cgl_legal_form');
        const legalCountryEl = document.getElementById('cgl_legal_country');
        const legalTextEl = document.getElementById('cgl_text_annexe2_legal_form');
        if (legalTextEl) {
            const formVal = legalFormEl ? legalFormEl.value.trim() : '';
            let countryVal = '';
            if (legalCountryEl) {
                if (legalCountryEl.tagName === 'SELECT' && legalCountryEl.selectedIndex >= 0) {
                    const opt = legalCountryEl.options[legalCountryEl.selectedIndex];
                    countryVal = (opt && opt.value) ? opt.text.trim() : '';
                } else {
                    countryVal = legalCountryEl.value.trim();
                }
            }
            if (formVal && countryVal) {
                legalTextEl.textContent = `${formVal} (${countryVal})`;
            } else if (formVal || countryVal) {
                legalTextEl.textContent = formVal || countryVal;
            } else {
                legalTextEl.textContent = '—';
            }
        }
    }

    fieldsToSync.forEach(function (item) {
        const inputEl = document.getElementById(item.inputId);
        if (inputEl) {
            inputEl.addEventListener('input', updateCglContractText);
        }
    });
    const formInput = document.getElementById('cgl_legal_form');
    if (formInput) formInput.addEventListener('input', updateCglContractText);
    const countryInput = document.getElementById('cgl_legal_country');
    if (countryInput) {
        countryInput.addEventListener('input', updateCglContractText);
        countryInput.addEventListener('change', updateCglContractText);

        const defaultCountry = (countryInput.getAttribute('data-default-country') || '').trim().toLowerCase();
        if (defaultCountry) {
            for (let i = 0; i < countryInput.options.length; i++) {
                const opt = countryInput.options[i];
                if (opt.value.toLowerCase() === defaultCountry || opt.text.toLowerCase() === defaultCountry) {
                    countryInput.selectedIndex = i;
                    break;
                }
            }
        }
    }

    updateCglContractText();

    // ── 2. Autocomplétion d'adresse ──────────────────────────────────────────
    const addressInput = document.getElementById('cgl_address');
    const suggestionsContainer = document.getElementById('cgl_address_suggestions');
    let lastSelectedAddress = '';

    if (addressInput && suggestionsContainer) {
        addressInput.addEventListener('input', async function () {
            const query = addressInput.value.trim();
            if (query === lastSelectedAddress || query.length < 3) {
                suggestionsContainer.classList.add('u-d-none');
                suggestionsContainer.innerHTML = '';
                return;
            }
            try {
                const res = await fetch('https://api-adresse.data.gouv.fr/search/?q=' + encodeURIComponent(query) + '&limit=5');
                const data = await res.json();
                if (data.features && data.features.length > 0) {
                    suggestionsContainer.innerHTML = '';
                    data.features.forEach(function (feature) {
                        const div = document.createElement('div');
                        div.className = 'suggestion-item';
                        div.textContent = feature.properties.label;
                        div.addEventListener('click', function () {
                            lastSelectedAddress = feature.properties.label;
                            addressInput.value = feature.properties.label;
                            suggestionsContainer.classList.add('u-d-none');
                            suggestionsContainer.innerHTML = '';
                            updateCglContractText();
                        });
                        suggestionsContainer.appendChild(div);
                    });
                    suggestionsContainer.classList.remove('u-d-none');
                } else {
                    suggestionsContainer.classList.add('u-d-none');
                    suggestionsContainer.innerHTML = '';
                }
            } catch (err) {
                console.error('Erreur API adresse:', err);
            }
        });

        document.addEventListener('click', function (e) {
            if (!addressInput.contains(e.target) && !suggestionsContainer.contains(e.target)) {
                suggestionsContainer.classList.add('u-d-none');
            }
        });
    }

    // ── 3. Contrôleur SignaturePad ───────────────────────────────────────────
    let signaturePad = null;
    if (typeof BelleVitesseSignaturePad !== 'undefined') {
        signaturePad = new BelleVitesseSignaturePad('cgl-signature-canvas', {
            clearBtnId: 'cgl-btn-clear',
        });
    }

    // ── 4. Bouton de soumission et scellement ─────────────────────────────────
    const btnSign = document.getElementById('cgl-btn-sign');
    if (!btnSign) return;

    btnSign.addEventListener('click', async function (e) {
        e.preventDefault();
        if (typeof hideFeedback === 'function') hideFeedback();

        // Vérification des champs requis
        const requiredFieldIds = [
            'cgl_production_name',
            'cgl_legal_form',
            'cgl_legal_country',
            'cgl_representative',
            'cgl_representative_role',
            'cgl_siret',
            'cgl_address',
            'cgl_phone',
            'cgl_email',
            'cgl_city',
            'cgl_order_ref',
            'cgl_insurance_company',
            'cgl_insurance_policy'
        ];
        let hasMissing = false;

        requiredFieldIds.forEach(function (id) {
            const el = document.getElementById(id);
            if (!el || !el.value.trim()) {
                hasMissing = true;
                if (el) el.classList.add('is-invalid');
            } else {
                if (el) el.classList.remove('is-invalid');
            }
        });

        if (hasMissing) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez renseigner toutes les informations obligatoires de la production et de son assurance.', 'error');
            }
            return;
        }

        // Vérification de la case d'acceptation
        const acceptTerms = document.getElementById('cgl_accept_terms');
        if (!acceptTerms || !acceptTerms.checked) {
            if (typeof showFeedback === 'function') {
                showFeedback('Vous devez déclarer avoir pris connaissance et accepter les CGL et l\'Annexe 2.', 'error');
            }
            return;
        }

        // Vérification de la signature
        if (!signaturePad || signaturePad.isEmpty()) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez apposer votre signature manuscrite dans le cadre prévu.', 'error');
            }
            return;
        }

        // Préparation du FormData
        const formData = new FormData(form);
        // Correspondance des champs pour le modèle Waiver backend
        formData.set('production_name', document.getElementById('cgl_production_name').value.trim());
        formData.set('representative', document.getElementById('cgl_representative').value.trim());
        formData.set('siret', document.getElementById('cgl_siret').value.trim());
        formData.set('address', document.getElementById('cgl_address').value.trim());
        const vatEl = document.getElementById('cgl_vat_number');
        if (vatEl) formData.set('vat_number', vatEl.value.trim());

        const roleEl = document.getElementById('cgl_representative_role');
        if (roleEl) formData.set('representative_role', roleEl.value.trim());
        const legalFormEl = document.getElementById('cgl_legal_form');
        if (legalFormEl) formData.set('legal_form', legalFormEl.value.trim());
        const legalCountryEl = document.getElementById('cgl_legal_country');
        if (legalCountryEl) {
            let countryVal = legalCountryEl.value.trim();
            if (legalCountryEl.tagName === 'SELECT' && legalCountryEl.selectedIndex >= 0) {
                const opt = legalCountryEl.options[legalCountryEl.selectedIndex];
                if (opt && opt.value) countryVal = opt.text.trim();
            }
            formData.set('legal_country', countryVal);
        }
        const phoneEl = document.getElementById('cgl_phone');
        if (phoneEl) formData.set('phone', phoneEl.value.trim());
        const emailEl = document.getElementById('cgl_email');
        if (emailEl) formData.set('email', emailEl.value.trim());
        const cityEl = document.getElementById('cgl_city');
        if (cityEl) formData.set('city', cityEl.value.trim());
        const orderRefEl = document.getElementById('cgl_order_ref');
        if (orderRefEl) formData.set('order_ref', orderRefEl.value.trim());
        const insCoEl = document.getElementById('cgl_insurance_company');
        if (insCoEl) formData.set('insurance_company', insCoEl.value.trim());
        const insPolEl = document.getElementById('cgl_insurance_policy');
        if (insPolEl) formData.set('insurance_policy', insPolEl.value.trim());

        const insFileEl = document.getElementById('cgl_insurance_file');
        if (insFileEl && insFileEl.files && insFileEl.files[0]) {
            formData.set('production_insurance', insFileEl.files[0]);
        }

        formData.set('signature_data', signaturePad.toDataURL('image/png'));

        // Récupération du token CSRF
        const csrfInput = document.getElementById('csrf_token') || form.querySelector('input[name="csrf_token"]');
        const csrfToken = csrfInput ? csrfInput.value : '';

        btnSign.disabled = true;
        const originalHtml = btnSign.innerHTML;
        btnSign.innerHTML = '<i data-lucide="loader-2" class="u-spin"></i> <span>Scellement électronique en cours…</span>';
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }

        try {
            const response = await fetch(window.location.href, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                },
                body: formData,
            });

            let result = null;
            try {
                result = await response.json();
            } catch (parseErr) {
                console.warn('Réponse non-JSON reçue:', parseErr);
            }

            if (response.ok && result && result.success) {
                if (typeof showFeedback === 'function') {
                    showFeedback('<i data-lucide="circle-check-big"></i> CGL signées et scellées avec succès. Vous recevrez le document certifié par e-mail.', 'success');
                }
                btnSign.innerHTML = '<i data-lucide="circle-check-big"></i> <span>Document signé ✓</span>';
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
                if (signaturePad && signaturePad.canvas) {
                    signaturePad.canvas.classList.add('u-pointer-none');
                }
                setTimeout(function () {
                    window.location.reload();
                }, 2500);
            } else {
                const errMsg = (result && (result.error || result.message)) || ('Erreur lors de la signature (code ' + response.status + ').');
                if (typeof showFeedback === 'function') {
                    showFeedback(errMsg, 'error');
                }
                btnSign.disabled = false;
                btnSign.innerHTML = originalHtml;
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
            }
        } catch (err) {
            console.error('Erreur réseau CGL:', err);
            if (typeof showFeedback === 'function') {
                showFeedback('Erreur de connexion. Veuillez vérifier votre accès internet et réessayer.', 'error');
            }
            btnSign.disabled = false;
            btnSign.innerHTML = originalHtml;
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }
    });

    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
});
;

/* ── js/src/public/sign-safety-rules.js ── */
/**
 * sign-safety-rules.js — Contrôleur public pour la signature des Règles de Sécurité Universelles (BVSR).
 * 
 * Fonctionnalités harmonisées avec sign-cgl.js :
 * - Capture et scellement de la signature électronique via SignaturePad
 * - Validation fluide des champs obligatoires (nom, prénom, e-mail, rôle, engagements)
 * - Soumission asynchrone sécurisée sans friction
 * - Feedback unifié et actualisation automatique de l'état scellé
 */

document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('safety-rules-form');
    if (!form) return;

    // ── 1. Initialisation du SignaturePad ──────────────────────────────────
    let signaturePad = null;
    if (typeof BelleVitesseSignaturePad !== 'undefined') {
        signaturePad = new BelleVitesseSignaturePad('safety-signature-canvas', {
            clearBtnId: 'safety-btn-clear',
        });
    }

    // ── 2. Gestion de l'affichage du champ "Rôle personnalisé" ────────────
    const roleSelect = document.getElementById('safety_signer_role');
    const roleCustomGroup = document.getElementById('safety_role_custom_group');
    if (roleSelect && roleCustomGroup) {
        roleSelect.addEventListener('change', function () {
            if (roleSelect.value === 'other') {
                roleCustomGroup.classList.remove('u-d-none');
            } else {
                roleCustomGroup.classList.add('u-d-none');
            }
        });
    }

    // ── 3. Bouton de soumission et signature ──────────────────────────────
    const btnSign = document.getElementById('safety-btn-sign');
    if (!btnSign) return;

    btnSign.addEventListener('click', async function (e) {
        e.preventDefault();
        if (typeof hideFeedback === 'function') hideFeedback();

        // A. Validation des champs d'identité
        const firstNameInput = document.getElementById('safety_first_name');
        const lastNameInput = document.getElementById('safety_last_name');
        const emailInput = document.getElementById('safety_email');

        const firstName = firstNameInput ? firstNameInput.value.trim() : '';
        const lastName = lastNameInput ? lastNameInput.value.trim() : '';
        const email = emailInput ? emailInput.value.trim() : '';

        if (!firstName || !lastName) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez renseigner votre prénom et votre nom.', 'error');
            }
            if (!firstName && firstNameInput) {
                firstNameInput.classList.add('is-invalid');
                firstNameInput.focus();
            } else if (!lastName && lastNameInput) {
                lastNameInput.classList.add('is-invalid');
                lastNameInput.focus();
            }
            return;
        }

        if (firstNameInput) firstNameInput.classList.remove('is-invalid');
        if (lastNameInput) lastNameInput.classList.remove('is-invalid');

        if (!email || !email.includes('@')) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez renseigner une adresse e-mail valide pour recevoir votre exemplaire scellé.', 'error');
            }
            if (emailInput) {
                emailInput.classList.add('is-invalid');
                emailInput.focus();
            }
            return;
        }

        if (emailInput) emailInput.classList.remove('is-invalid');

        // B. Validation des engagements obligatoires
        const ackRules = document.getElementById('ack_rules');
        const ackAuthority = document.getElementById('ack_authority');

        if (ackRules && !ackRules.checked) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez confirmer avoir pris connaissance des règles de sécurité en cochant la case requise.', 'error');
            }
            ackRules.focus();
            return;
        }

        if (ackAuthority && !ackAuthority.checked) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez confirmer votre droit et devoir d’interruption (Stop Work Authority) en cochant la case requise.', 'error');
            }
            ackAuthority.focus();
            return;
        }

        // C. Validation de la signature manuscrite
        if (!signaturePad || signaturePad.isEmpty()) {
            if (typeof showFeedback === 'function') {
                showFeedback('Veuillez apposer votre signature manuscrite dans le cadre prévu.', 'error');
            }
            const canvas = document.getElementById('safety-signature-canvas');
            if (canvas) canvas.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }

        // D. Préparation du FormData
        const formData = new FormData(form);
        const signatureData = signaturePad.toDataURL('image/png');
        formData.set('signature_data', signatureData);

        // Récupération du token CSRF
        const csrfInput = document.getElementById('csrf_token') || form.querySelector('input[name="csrf_token"]');
        const csrfToken = csrfInput ? csrfInput.value : '';

        // État de chargement
        btnSign.disabled = true;
        const originalHtml = btnSign.innerHTML;
        btnSign.innerHTML = '<i data-lucide="loader-2" class="u-spin"></i> <span>Scellement électronique en cours…</span>';
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }

        try {
            const response = await fetch(window.location.href, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: formData,
            });

            let result = null;
            try {
                result = await response.json();
            } catch (parseErr) {
                console.warn('Réponse non-JSON reçue:', parseErr);
            }

            if (response.ok && result && result.success) {
                if (typeof showFeedback === 'function') {
                    showFeedback('<i data-lucide="circle-check-big"></i> Engagement signé et scellé avec succès. Vous recevrez le document certifié par e-mail.', 'success');
                }
                btnSign.innerHTML = '<i data-lucide="circle-check-big"></i> <span>Document signé ✓</span>';
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
                if (signaturePad && signaturePad.canvas) {
                    signaturePad.canvas.classList.add('u-pointer-none');
                }
                setTimeout(function () {
                    window.location.reload();
                }, 2200);
            } else {
                const errMsg = (result && (result.error || result.message)) || ('Erreur lors de la signature (code ' + response.status + ').');
                if (typeof showFeedback === 'function') {
                    showFeedback(errMsg, 'error');
                }
                btnSign.disabled = false;
                btnSign.innerHTML = originalHtml;
                if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
            }
        } catch (err) {
            console.error('Erreur réseau signature BVSR:', err);
            if (typeof showFeedback === 'function') {
                showFeedback('Erreur de connexion. Veuillez vérifier votre accès internet et réessayer.', 'error');
            }
            btnSign.disabled = false;
            btnSign.innerHTML = originalHtml;
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }
    });

    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
});
;
