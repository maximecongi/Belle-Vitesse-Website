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
