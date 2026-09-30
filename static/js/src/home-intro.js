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
