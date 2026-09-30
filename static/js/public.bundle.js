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
    if (typeof window.initHomeIntro === 'function') {
        window.initHomeIntro(true);
    }
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

/* ── js/src/home-intro.js ── */
/**
 * home-intro.js — Animation d'accueil cinématographique Belle Vitesse.
 * Séquence :
 *   1. Fond noir pur avec logo Belle Vitesse complet ("BELLE" + "V" + "ITESSE")
 *   2. "BELLE" et "ITESSE" se rétractent vers le centre dans le "V"
 *   3. Le "V" grossit massivement (zoom immersif) jusqu'à dépasser l'écran et laisse place à la vidéo
 *   4. Vidéo du hero en plein écran (100svh, header et slogans repliés, scroll strictement verrouillé)
 *   5. Au bout de 3 secondes, affichage de l'animation de défilement (.icon-scroll)
 *   6. Au scroll : verrouillage strict du défilement. La page reste fixée à scrollY=0
 *      pendant que les éléments reprennent leur place (vidéo 90svh, menu, slogan, boutons).
 *   7. Déverrouillage naturel une fois les éléments posés.
 */

(function () {
    let introState = 'idle'; // 'idle' | 'running' | 'settling' | 'done'
    let currentTriggerSettle = null;
    let scrollPromptTimer = null;
    let autoSettleTimer = null;
    let retractTimer = null;
    let zoomTimer = null;
    let fadeTimer = null;
    let finishTimer = null;

    function handleScrollIconAction(e) {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        if (introState === 'running' && typeof currentTriggerSettle === 'function') {
            currentTriggerSettle();
        } else if (introState === 'done') {
            const target = document.getElementById('testimonials') || document.getElementById('solutions');
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            } else {
                window.scrollBy({ top: window.innerHeight * 0.85, behavior: 'smooth' });
            }
        }
    }

    function bindScrollIcon(scrollIcon) {
        if (!scrollIcon || scrollIcon.dataset.scrollBound) return;
        scrollIcon.dataset.scrollBound = 'true';
        scrollIcon.addEventListener('click', handleScrollIconAction);
        scrollIcon.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                handleScrollIconAction(e);
            }
        });
    }

    function initHomeIntro(fromSwup = false) {
        const homeBanner = document.querySelector('.home-hero-banner');
        const introLoader = document.getElementById('intro-loader');

        if (!homeBanner || !introLoader) {
            return;
        }

        const scrollIcon = homeBanner.querySelector('.icon-scroll');
        if (scrollIcon) {
            bindScrollIcon(scrollIcon);
        }

        // Si l'intro est déjà active ou en transition
        if (introState === 'running' || introState === 'settling') {
            return;
        }

        if (introState === 'done' || fromSwup) {
            introState = 'done';
            if (autoSettleTimer) clearTimeout(autoSettleTimer);
            if (scrollPromptTimer) clearTimeout(scrollPromptTimer);
            introLoader.classList.add('is-hidden');
            document.documentElement.classList.remove('hero-intro-locked');
            document.body.classList.remove('hero-intro-mode', 'hero-intro-locked', 'hero-intro-settling');
            if (scrollIcon) {
                scrollIcon.classList.add('is-visible');
            }
            return;
        }

        // Démarrage de l'animation d'accueil
        introState = 'running';

        if ('scrollRestoration' in history) {
            history.scrollRestoration = 'manual';
        }
        window.scrollTo(0, 0);

        // Verrouillage strict sur html et body dès le départ
        document.documentElement.classList.add('hero-intro-locked');
        document.body.classList.add('hero-intro-mode', 'hero-intro-locked');

        function triggerSettle() {
            if (introState !== 'running') return;
            introState = 'settling';

            if (scrollPromptTimer) {
                clearTimeout(scrollPromptTimer);
                scrollPromptTimer = null;
            }
            if (autoSettleTimer) {
                clearTimeout(autoSettleTimer);
                autoSettleTimer = null;
            }

            if (scrollIcon) {
                scrollIcon.classList.add('is-visible');
            }

            // Déclencher la chorégraphie CSS des éléments
            document.body.classList.add('hero-intro-settling');
            window.scrollTo({ top: 0, left: 0, behavior: 'instant' });

            // Durée de l'animation CSS (~850ms)
            const SETTLE_ANIMATION_MS = 850;

            function finalizeSettle() {
                if (introState === 'done') return;
                introState = 'done';
                currentTriggerSettle = null;

                // Fin de l'animation : déverrouillage propre et immédiat
                document.documentElement.classList.remove('hero-intro-locked');
                document.body.classList.remove('hero-intro-mode', 'hero-intro-locked', 'hero-intro-settling');
                detachScrollListeners();
            }

            setTimeout(finalizeSettle, SETTLE_ANIMATION_MS);
        }

        currentTriggerSettle = triggerSettle;

        function onUserScroll(e) {
            if (introState === 'running') {
                if (e.cancelable) e.preventDefault();

                // Détection molette descendante
                if (e.type === 'wheel') {
                    if (e.deltaY > 2) {
                        triggerSettle();
                    }
                    return;
                }

                // Touches flèche bas / page down / espace
                if (e.type === 'keydown') {
                    if (['ArrowDown', 'PageDown', ' '].includes(e.key)) {
                        triggerSettle();
                    }
                    return;
                }
            }

            if (introState === 'settling') {
                if (e.cancelable) e.preventDefault();
                window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
                return;
            }
        }

        let touchStartY = 0;
        function onTouchStart(e) {
            if (e.touches && e.touches.length > 0) {
                touchStartY = e.touches[0].clientY;
            }
        }

        function onTouchMove(e) {
            if (introState === 'running') {
                if (e.cancelable) e.preventDefault();

                if (e.touches && e.touches.length > 0) {
                    const currentY = e.touches[0].clientY;
                    // Glissement vers le haut (veut scroller vers le bas)
                    if (touchStartY - currentY > 20) {
                        triggerSettle();
                    }
                }
                return;
            }

            if (introState === 'settling') {
                if (e.cancelable) e.preventDefault();
                return;
            }
        }

        function onWindowScroll() {
            // Filet de sécurité garantissant scrollY = 0 tant que l'intro n'est pas terminée
            if (introState === 'running' || introState === 'settling') {
                if (window.scrollY !== 0) {
                    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
                }
            }
        }

        function attachScrollListeners() {
            window.addEventListener('wheel', onUserScroll, { passive: false });
            window.addEventListener('keydown', onUserScroll, { passive: false });
            window.addEventListener('touchstart', onTouchStart, { passive: true });
            window.addEventListener('touchmove', onTouchMove, { passive: false });
            window.addEventListener('scroll', onWindowScroll, { passive: true });

            if (homeBanner) {
                homeBanner.addEventListener('click', triggerSettle);
            }
        }

        function detachScrollListeners() {
            window.removeEventListener('wheel', onUserScroll);
            window.removeEventListener('keydown', onUserScroll);
            window.removeEventListener('touchstart', onTouchStart);
            window.removeEventListener('touchmove', onTouchMove);
            window.removeEventListener('scroll', onWindowScroll);

            if (homeBanner) {
                homeBanner.removeEventListener('click', triggerSettle);
            }
        }

        function startVideoAndEnableScroll() {
            introLoader.classList.add('is-hidden');
            attachScrollListeners();

            // Après 3 secondes en plein écran (si pas de scroll préalable) :
            // apparition synchronisée de l'icône de défilement et des éléments (header, slogan, boutons)
            autoSettleTimer = setTimeout(() => {
                if (introState === 'running') {
                    triggerSettle();
                }
            }, 3000);
        }

        function skipIntroLoader() {
            if (introLoader.classList.contains('is-hidden')) return;
            clearTimeout(retractTimer);
            clearTimeout(zoomTimer);
            clearTimeout(fadeTimer);
            clearTimeout(finishTimer);
            clearTimeout(scrollPromptTimer);
            clearTimeout(autoSettleTimer);

            introLoader.classList.add('is-fading');
            setTimeout(startVideoAndEnableScroll, 300);
        }

        introLoader.addEventListener('click', skipIntroLoader);

        // Étape 1 : À 750ms, rétraction de "BELLE" et "ITESSE" vers le centre
        retractTimer = setTimeout(() => {
            if (introState !== 'running') return;
            introLoader.classList.add('is-retracting');
        }, 750);

        // Étape 2 : À 1300ms, le "V" grossit jusqu'à remplir/dépasser l'écran
        zoomTimer = setTimeout(() => {
            if (introState !== 'running') return;
            introLoader.classList.add('is-zooming');
        }, 1800);

        // Étape 3 : À 1750ms, fondu de sortie du loader pour laisser place à la vidéo
        fadeTimer = setTimeout(() => {
            if (introState !== 'running') return;
            introLoader.classList.add('is-fading');
        }, 2250);

        // Étape 4 : À 2200ms, disparition complète du loader et début de l'état plein écran
        finishTimer = setTimeout(() => {
            if (introState !== 'running') return;
            startVideoAndEnableScroll();
        }, 2700);
    }

    window.initHomeIntro = initHomeIntro;

    // Déclenchement automatique au chargement initial du DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => initHomeIntro(false));
    } else {
        initHomeIntro(false);
    }
})();
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
