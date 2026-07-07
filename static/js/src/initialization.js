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
                const formData = new FormData();
                formData.append('email', email);
                formData.append('lang', isFr ? 'fr' : 'en');

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
