(() => {
    // =========================
    // INIT
    // =========================

    let sliders = [];
    let vehicles = [];

    window.initFilterSliders = function () {
        const sliderContainers = document.querySelectorAll(".slider-container");
        vehicles = Array.from(document.querySelectorAll(
            ".categories-solutions-categories-categorywrapper"
        ));

        sliders = [];

        sliderContainers.forEach((container) => {
            sliders.push(initSlider(container));
        });

        // premier filtrage APRÈS init complète
        applyFilters();
    };

    // =========================
    // SLIDER SETUP
    // =========================

    function initSlider(container) {
        const slider = container.querySelector(".js-slider");
        const output = container.querySelector(".slider__value");

        if (!slider || !output) return null;

        const update = () => {
            const value = parseInt(slider.value, 10);

            output.textContent = value;
            updateDescription(container, value);

            applyFilters();
        };

        slider.addEventListener("input", update);

        // init affichage (sans filtrer encore)
        output.textContent = slider.value;
        updateDescription(container, parseInt(slider.value, 10));

        return {
            filterKey: container.dataset.filterKey,
            getValue: () => parseInt(slider.value, 10)
        };
    }

    // =========================
    // AND FILTER LOGIC
    // =========================

    function applyFilters() {
        vehicles.forEach((vehicle) => {
            const isVisible = sliders.every((slider) => {
                if (!slider) return true;
                const { filterKey, getValue } = slider;
                const vehicleValue = parseInt(vehicle.dataset[filterKey], 10);

                if (Number.isNaN(vehicleValue)) return false;

                return getValue() <= vehicleValue;
            });

            if (isVisible) {
                show(vehicle);
            } else {
                hide(vehicle);
            }
        });
    }

    // =========================
    // DESCRIPTION HANDLER
    // =========================

    function updateDescription(container, value) {
        const descEl = container.querySelector(".slider__description");
        if (!descEl) return;

        const descriptions = JSON.parse(container.dataset.descriptions || "[]");

        let text = "";

        descriptions.forEach(([min, desc]) => {
            if (value >= min) {
                text = desc;
            }
        });

        descEl.textContent = text;
    }

    // =========================
    // ANIMATION HELPERS
    // =========================

    function hide(el) {
        if (el.classList.contains("filterslider-is-hidden")) return;

        el.classList.add("filterslider-is-hiding");

        el.addEventListener(
            "transitionend",
            () => {
                el.classList.remove("filterslider-is-hiding");
                el.classList.add("filterslider-is-hidden");
            },
            { once: true }
        );
    }

    function show(el) {
        if (!el.classList.contains("filterslider-is-hidden")) return;

        el.classList.remove("filterslider-is-hidden");
        el.classList.add("filterslider-is-showing");

        // force reflow
        el.offsetHeight;

        el.classList.remove("filterslider-is-showing");
    }

    // =========================
    // ANIMATION BUTTON
    // =========================

    document.addEventListener("click", (e) => {
        const button = e.target.closest(".slider-dropdown-button");
        if (!button) return;

        const filterssliders = document.querySelector(".filtersliders-container");
        if (!filterssliders) return;

        const isOpen = filterssliders.classList.contains("filterslider-is-open");

        if (isOpen) {
            // CLOSE
            filterssliders.style.maxHeight = "0px";
            filterssliders.classList.remove("filterslider-is-open");
        } else {
            // OPEN
            filterssliders.style.maxHeight = filterssliders.scrollHeight + "px";
            filterssliders.classList.add("filterslider-is-open");
        }
    });
})();
