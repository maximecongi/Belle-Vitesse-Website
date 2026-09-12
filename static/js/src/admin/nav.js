/**
 * nav.js — Gestion de la navigation, persistance sidebar et liens actifs.
 */

function restoreNavState() {
    document.querySelectorAll('.admin-nav-group').forEach(group => {
        const id = group.dataset.navGroup;
        if (!id) return;
        const state = localStorage.getItem(`nav-group-${id}`);
        if (state === 'open') {
            group.classList.add('open');
        } else if (state === 'closed') {
            group.classList.remove('open');
        } else if (group.classList.contains('default-open')) {
            group.classList.add('open');
        }
    });
}

function updateActiveNavLink() {
    const currentPath = window.location.pathname;
    let bestMatch = null;
    let maxLen = -1;

    const navItems = document.querySelectorAll('.admin-nav-item');
    navItems.forEach(link => {
        link.classList.remove('active');
        const href = link.getAttribute('href');
        if (!href || href === '#' || href === '') return;

        if (href === currentPath) {
            bestMatch = link;
            maxLen = 999;
        } else if (currentPath.startsWith(href) && href !== '/admin/dashboard' && href !== '/admin') {
            if (href.length > maxLen) {
                maxLen = href.length;
                bestMatch = link;
            }
        }
    });

    if (bestMatch) {
        bestMatch.classList.add('active');
    }
}

// Global click listener pour sidebar triggers et fermeture dropdowns/tooltips
if (!window._adminNavClickAttached) {
    window._adminNavClickAttached = true;
    document.addEventListener('click', e => {
        const trigger = e.target.closest('.admin-nav-group-trigger');
        if (trigger) {
            const group = trigger.closest('.admin-nav-group');
            group.classList.toggle('open');

            const id = group.dataset.navGroup;
            if (id) {
                localStorage.setItem(`nav-group-${id}`, group.classList.contains('open') ? 'open' : 'closed');
            }
        }

        // Fermeture des menus déroulants et tooltips en cliquant en dehors
        if (!e.target.closest('.badge-select') && !e.target.closest('.rich-select') && !e.target.closest('.admin-tooltip-container')) {
            document.querySelectorAll('.badge-select.open, .rich-select.open, .admin-tooltip-container.open')
                .forEach(s => s.classList.remove('open'));
        }

        const tooltipTrigger = e.target.closest('.note-tooltip-trigger');
        if (tooltipTrigger) {
            const container = tooltipTrigger.closest('.admin-tooltip-container');
            const wasOpen = container.classList.contains('open');
            document.querySelectorAll('.admin-tooltip-container.open').forEach(c => c.classList.remove('open'));
            if (!wasOpen) {
                container.classList.add('open');
            }
        }
    });
}

// ── Gestion du tiroir latéral escamotable pour tablette & mobile ─
function initSidebarDrawer() {
    const sidebar = document.getElementById('adminSidebar');
    const toggle = document.getElementById('adminSidebarToggle');
    const backdrop = document.getElementById('adminSidebarBackdrop');
    const closeBtn = document.getElementById('adminSidebarClose');

    if (!sidebar || !toggle) return;

    function openSidebar() {
        sidebar.classList.add('is-open');
        if (backdrop) backdrop.classList.add('is-active');
        toggle.setAttribute('aria-expanded', 'true');
        document.body.classList.add('u-overflow-hidden');
        if (window.bvIpadBridge) window.bvIpadBridge.triggerHaptic('light');
    }

    function closeSidebar() {
        sidebar.classList.remove('is-open');
        if (backdrop) backdrop.classList.remove('is-active');
        toggle.setAttribute('aria-expanded', 'false');
        document.body.classList.remove('u-overflow-hidden');
    }

    toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        if (sidebar.classList.contains('is-open')) {
            closeSidebar();
        } else {
            openSidebar();
        }
    });

    if (backdrop) {
        backdrop.addEventListener('click', closeSidebar);
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', closeSidebar);
    }

    // Fermer avec Échap
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar.classList.contains('is-open')) {
            closeSidebar();
        }
    });

    // Fermer le tiroir lors du clic sur un lien nav (sur tablette)
    sidebar.querySelectorAll('.admin-nav-item').forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 1200) {
                closeSidebar();
            }
        });
    });

    // Support du geste de balayage (swipe vers la gauche) pour fermer le tiroir
    let touchStartX = 0;
    sidebar.addEventListener('touchstart', (e) => {
        touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });

    sidebar.addEventListener('touchend', (e) => {
        const touchEndX = e.changedTouches[0].screenX;
        if (touchStartX - touchEndX > 50) {
            closeSidebar();
        }
    }, { passive: true });
}

function initNav() {
    restoreNavState();
    updateActiveNavLink();
    initSidebarDrawer();
}

window.initNav = initNav;
window.restoreNavState = restoreNavState;
window.updateActiveNavLink = updateActiveNavLink;

// Support Swup et initialisation directe
document.addEventListener('swup:contentReplaced', restoreNavState);
document.addEventListener('swup:contentReplaced', updateActiveNavLink);
document.addEventListener('swup:transitionEnd', updateActiveNavLink);

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNav);
} else {
    initNav();
}

