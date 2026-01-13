document.addEventListener("DOMContentLoaded", function () {
    const buttons = document.querySelectorAll('.config-btn');
    const image = document.getElementById('configurator-image');

    if (buttons.length > 0 && image) {
        buttons.forEach(button => {
            button.addEventListener('click', function () {
                // Update active state
                buttons.forEach(btn => {
                    btn.classList.remove('active');
                    btn.classList.add('inactive');
                });
                this.classList.remove('inactive');
                this.classList.add('active');

                // Update image
                const newSrc = this.getAttribute('data-image');
                const newAlt = this.getAttribute('data-label');

                // Optional: valid newSrc check
                if (newSrc) {
                    image.src = newSrc;
                    image.alt = newAlt;
                }
            });
        });
    }
});
