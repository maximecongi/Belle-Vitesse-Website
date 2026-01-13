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
    if (typeof window.initSliders === 'function') {
        window.initSliders();
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
    // Add other content initializers here (e.g. InfiniteScroll)
}

// Swup Initialization
const swup = new Swup();

swup.hooks.on('content:replace', () => {
    initContent();
    // Header is now persistent, so we don't re-run initDropdowns()

    // Close mobile menu
    const menuCheckbox = document.getElementById('active');
    if (menuCheckbox) {
        menuCheckbox.checked = false;
    }
});

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    initDropdowns(); // Run once for the header
    initContent();   // Run for the initial content
});
