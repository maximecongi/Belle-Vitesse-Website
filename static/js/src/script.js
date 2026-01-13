document.addEventListener('DOMContentLoaded', () => {
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

        // Optional: Reset image when leaving the dropdown wrapper
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
});
