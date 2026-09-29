/**
 * public.bundle.js — Bundle JavaScript unifié pour le site public Belle Vitesse.
 * Concaténé et validé automatiquement par scripts/build_bundles.py.
 */

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
