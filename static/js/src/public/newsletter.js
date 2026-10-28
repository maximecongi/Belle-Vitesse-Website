/**
 * newsletter.js — Gestion de la soumission asynchrone des inscriptions newsletter.
 */

function initNewsletter() {
    const forms = document.querySelectorAll('.newsletter-form');
    if (!forms.length) return;

    forms.forEach(form => {
        if (form._hasNewsletterListener) return;
        form._hasNewsletterListener = true;

        const container = form.closest('.newsletter');
        const messageDiv = container ? container.querySelector('.newsletter-message') : null;
        const input = form.querySelector('input[name="email"]');

        if (!input || !messageDiv) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const email = input.value;
            messageDiv.className = 'newsletter-message';
            messageDiv.textContent = 'Subscribing...';
            messageDiv.classList.add('show');

            try {
                const formData = new FormData(form);
                formData.set('email', email);
                formData.set('lang', 'en');

                const response = await fetch('/subscribe', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                messageDiv.textContent = data.message;
                if (response.ok) {
                    messageDiv.className = 'newsletter-message success show';
                    form.reset();
                } else {
                    messageDiv.className = 'newsletter-message error show';
                }

                setTimeout(() => {
                    messageDiv.classList.remove('show');
                }, 5000);

            } catch (error) {
                console.error('Error:', error);
                messageDiv.textContent = 'An error occurred. Please try again.';
                messageDiv.className = 'newsletter-message error show';
            }
        });
    });
}

window.initNewsletter = initNewsletter;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNewsletter);
} else {
    initNewsletter();
}
document.addEventListener('swup:contentReplaced', initNewsletter);

