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
            // 🚀 Add loading state
            messageDiv.className = 'newsletter-message';
            messageDiv.textContent = 'Subscribing...';
            messageDiv.classList.add('show');
            if (button) button.disabled = true;

            try {
                const formData = new FormData();
                formData.append('email', email);

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
});

// Language switching (works with Swup — no full reload)
function switchLang(lang) {
    // 1. Set session via fetch
    fetch('/set_lang/' + lang).then(() => {
        // 2. Immediately update header lang selector
        document.querySelectorAll('.header-lang-link').forEach(el => {
            el.classList.toggle('active', el.textContent.trim().toLowerCase() === lang);
        });

        // 3. Update <html lang>
        document.documentElement.setAttribute('lang', lang);

        // 4. Re-fetch current page with new lang and swap #swup content + header menus
        fetch(window.location.href).then(r => r.text()).then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            // Swap #swup content (the main area Swup manages)
            const newSwup = doc.querySelector('#swup');
            const currentSwup = document.querySelector('#swup');
            if (newSwup && currentSwup) {
                currentSwup.innerHTML = newSwup.innerHTML;
            }

            // Swap header menus (mobile + desktop) for translated labels
            const newHeaderMenu = doc.querySelector('.header-menu');
            const currentHeaderMenu = document.querySelector('.header-menu');
            if (newHeaderMenu && currentHeaderMenu) {
                // Preserve mobile menu checkbox state
                const wasChecked = document.getElementById('active')?.checked;
                currentHeaderMenu.innerHTML = newHeaderMenu.innerHTML;
                const cb = document.getElementById('active');
                if (cb) cb.checked = wasChecked;
            }

            // Re-initialize content scripts
            initContent();
            initDropdowns();
        });
    });
}

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    initDropdowns(); // Run once for the header
    initContent();   // Run for the initial content
});
