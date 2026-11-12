/**
 * Formulaire projet — mise en page à sections
 * - Récapitulatif latéral mis à jour en direct (dates, matériel, référents, lieux)
 * - Navigation entre sections avec surlignage de la section visible
 * - Indicateur « Modifications non enregistrées » dans l'en-tête
 */
(function () {
    'use strict';

    const DAYS = ['dim.', 'lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.'];
    const MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];

    function parseIso(iso) {
        if (!iso || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null;
        const [y, m, d] = iso.split('-').map(Number);
        return new Date(y, m - 1, d);
    }

    function dayLabel(iso) {
        const d = parseIso(iso);
        return d ? `${DAYS[d.getDay()]} ${d.getDate()}` : '';
    }

    function rangeLabel(startIso, endIso) {
        const a = parseIso(startIso);
        const b = parseIso(endIso);
        if (!a) return '—';
        if (!b || startIso === endIso) return `${a.getDate()} ${MONTHS[a.getMonth()]}`;
        if (a.getMonth() === b.getMonth() && a.getFullYear() === b.getFullYear()) {
            return `${a.getDate()} → ${b.getDate()} ${MONTHS[b.getMonth()]}`;
        }
        return `${a.getDate()} ${MONTHS[a.getMonth()]} → ${b.getDate()} ${MONTHS[b.getMonth()]}`;
    }

    function shortName(full) {
        const parts = (full || '').trim().split(/\s+/);
        if (parts.length < 2) return parts[0] || '';
        return `${parts[0].charAt(0)}. ${parts.slice(1).join(' ')}`;
    }

    function valueOf(id) {
        const el = document.getElementById(id);
        return el ? (el.value || '') : '';
    }

    function setText(id, text) {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = text || '—';
        el.classList.toggle('is-empty', !text);
    }

    function init() {
        const form = document.getElementById('projectMainForm');
        const recap = document.getElementById('pfRecap');
        if (!form || !recap) return;

        // ── Récapitulatif ────────────────────────────────────────────
        function renderDates() {
            const isPunctual = valueOf('date_mode_input') === 'punctual';
            let shootDates = [];
            try { shootDates = JSON.parse(valueOf('shoot_dates_input') || '[]') || []; } catch (e) { shootDates = []; }
            shootDates = shootDates.filter(Boolean).sort();

            const dep = valueOf('departure_date_input');
            const ret = valueOf('return_date_input');
            const shootStart = isPunctual ? (shootDates[0] || '') : valueOf('shoot_start_input');
            const shootEnd = isPunctual ? (shootDates[shootDates.length - 1] || '') : (valueOf('shoot_end_input') || shootStart);

            const all = [dep, shootStart, shootEnd, ret].filter(Boolean).sort();
            setText('pfRecapDates', all.length ? rangeLabel(all[0], all[all.length - 1]) : '');

            const pills = document.getElementById('pfRecapDatePills');
            if (!pills) return;
            const items = [];
            if (dep) items.push(['dep', 'truck', dayLabel(dep)]);
            if (isPunctual && shootDates.length) {
                // Dates ponctuelles : seulement le nombre de jours de tournage
                const n = shootDates.length;
                items.push(['shoot', 'clapperboard', `${n} date${n > 1 ? 's' : ''}`]);
            } else if (shootStart) {
                items.push(['shoot', 'clapperboard', dayLabel(shootStart)]);
            }
            if (ret) items.push(['ret', 'package-check', dayLabel(ret)]);
            pills.innerHTML = items.map(([type, icon, label]) =>
                `<span class="pf-recap-pill is-${type}"><i data-lucide="${icon}"></i>${label}</span>`
            ).join('');
            pills.hidden = items.length === 0;
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                try { window.lucide.createIcons({ root: pills }); } catch (e) { /* icônes facultatives */ }
            }
        }

        function checkedNames(selector) {
            return Array.from(form.querySelectorAll(selector))
                .map(input => {
                    const card = input.closest('label');
                    const nameEl = card && card.querySelector('[data-pf-item-name]');
                    return nameEl ? nameEl.textContent.trim() : '';
                })
                .filter(Boolean);
        }

        function renderRecap() {
            renderDates();

            const material = checkedNames('input[name="vehicle_ids"]:checked, input[name="head_ids"]:checked');
            setText('pfRecapMaterial', material.join(' · '));

            const selectedNames = name => Array.from(form.querySelectorAll(`select[name="${name}"] option:checked`))
                .map(opt => shortName(opt.textContent.trim()))
                .filter(Boolean);
            setText('pfRecapReferents', selectedNames('bv_referent_ids').join(' · '));
            setText('pfRecapTechnicians', selectedNames('bv_technician_ids').join(' · '));

            let locations = [];
            try { locations = JSON.parse(valueOf('shooting_locations_input') || '[]') || []; } catch (e) { locations = []; }
            const names = locations.map(l => (l && l.name ? String(l.name).trim() : '')).filter(Boolean);
            const locEl = document.getElementById('pfRecapLocations');
            if (locEl) {
                locEl.textContent = names.length === 0 ? 'Aucun'
                    : (names.length > 2 ? `${names.length} lieux` : names.join(' · '));
                locEl.classList.toggle('is-empty', names.length === 0);
            }
        }

        // ── Avancement : une section est « remplie » selon des critères minimaux ──
        function renderProgress() {
            let shootDates = [];
            try { shootDates = JSON.parse(valueOf('shoot_dates_input') || '[]') || []; } catch (e) { shootDates = []; }
            let locations = [];
            try { locations = JSON.parse(valueOf('shooting_locations_input') || '[]') || []; } catch (e) { locations = []; }
            const nameInput = form.querySelector('input[name="name"]');

            const done = {
                projet: Boolean(nameInput && nameInput.value.trim()) && Boolean(valueOf('productionSelect')),
                dates: Boolean(valueOf('departure_date_input') && valueOf('return_date_input'))
                    || shootDates.filter(Boolean).length > 0
                    || Boolean(valueOf('shoot_start_input')),
                materiel: form.querySelector('input[name="vehicle_ids"]:checked, input[name="head_ids"]:checked') !== null,
                equipe: form.querySelector('select[name="bv_referent_ids"] option:checked, select[name="bv_technician_ids"] option:checked') !== null,
                lieux: locations.some(l => l && String(l.name || '').trim()),
            };

            document.querySelectorAll('.pf-nav-link[data-pf-step]').forEach(link => {
                const isDone = Boolean(done[link.dataset.pfStep]);
                link.classList.toggle('is-done', isDone);
                link.title = isDone ? 'Section remplie' : 'Section à compléter';
            });
        }

        let recapTimer = null;
        function scheduleRecap() {
            clearTimeout(recapTimer);
            recapTimer = setTimeout(() => {
                renderRecap();
                renderProgress();
            }, 60);
        }

        ['input', 'change', 'click'].forEach(evt => form.addEventListener(evt, scheduleRecap));
        // Select2 déclenche « change » via jQuery, invisible pour les écouteurs natifs
        if (window.jQuery) window.jQuery(form).on('change', 'select', scheduleRecap);
        renderRecap();
        renderProgress();
        // Les lieux et Select2 s'initialisent après ce script : second passage une fois la page prête
        setTimeout(scheduleRecap, 400);

        // ── Modifications non enregistrées ───────────────────────────
        const indicator = document.getElementById('pfDirtyIndicator');
        const serialize = () => new URLSearchParams(new FormData(form)).toString();
        let baseline = null;

        function checkDirty() {
            if (!indicator || baseline === null) return;
            indicator.classList.toggle('is-visible', serialize() !== baseline);
        }

        // Instantané pris après l'initialisation des composants (calendrier, Select2, lieux)
        setTimeout(() => {
            baseline = serialize();
            ['input', 'change', 'click'].forEach(evt => form.addEventListener(evt, () => setTimeout(checkDirty, 80)));
            if (window.jQuery) window.jQuery(form).on('change', 'select', () => setTimeout(checkDirty, 80));
        }, 700);

        form.addEventListener('submit', () => {
            if (indicator) indicator.classList.remove('is-visible');
        });

        // ── Navigation entre sections ────────────────────────────────
        const links = Array.from(document.querySelectorAll('.pf-nav-link'));
        const sections = Array.from(document.querySelectorAll('[data-pf-section]'));

        function setActive(id) {
            links.forEach(link => link.classList.toggle('is-active', link.getAttribute('href') === `#${id}`));
        }

        links.forEach(link => {
            link.addEventListener('click', (e) => {
                const target = document.querySelector(link.getAttribute('href'));
                if (!target) return;
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                setActive(target.id);
            });
        });

        // Section active = dernière dont le haut a dépassé le tiers de l'écran ;
        // en bas de page, la dernière section l'emporte (elle peut être trop courte pour remonter jusque-là).
        function updateActiveFromScroll() {
            if (!sections.length) return;
            const doc = document.documentElement;
            const atBottom = window.innerHeight + window.scrollY >= doc.scrollHeight - 4;
            if (atBottom) {
                setActive(sections[sections.length - 1].id);
                return;
            }
            const threshold = window.innerHeight * 0.33;
            let current = sections[0];
            sections.forEach(section => {
                if (section.getBoundingClientRect().top <= threshold) current = section;
            });
            setActive(current.id);
        }

        let scrollTicking = false;
        window.addEventListener('scroll', () => {
            if (scrollTicking) return;
            scrollTicking = true;
            window.requestAnimationFrame(() => {
                scrollTicking = false;
                updateActiveFromScroll();
            });
        }, { passive: true });
        window.addEventListener('resize', updateActiveFromScroll);
        updateActiveFromScroll();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
