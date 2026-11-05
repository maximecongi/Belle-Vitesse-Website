/**
 * vehicle-safety-rules.js — Contrôleur de bascule bilingue FR / EN pour le portail public des consignes de sécurité.
 */

function initSafetyPortalLangSwitcher() {
    const langBtns = document.querySelectorAll('.safety-lang-btn');
    if (!langBtns.length) return;

    function setLanguage(lang) {
        if (lang === 'en') {
            document.body.classList.add('lang-en');
            document.documentElement.setAttribute('lang', 'en');
        } else {
            document.body.classList.remove('lang-en');
            document.documentElement.setAttribute('lang', 'fr');
        }

        langBtns.forEach(btn => {
            if (btn.getAttribute('data-set-lang') === lang) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        try {
            localStorage.setItem('bv_safety_lang', lang);
        } catch (e) {
            // Mode navigation privée ou localStorage restreint
        }
    }

    langBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            const chosenLang = this.getAttribute('data-set-lang');
            setLanguage(chosenLang);
        });
    });

    // Restaurer la préférence si présente
    try {
        const saved = localStorage.getItem('bv_safety_lang');
        if (saved === 'en') {
            setLanguage('en');
        }
    } catch (e) {}
}

function initSafetyPortal() {
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
    initSafetyPortalLangSwitcher();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSafetyPortal);
} else {
    initSafetyPortal();
}
