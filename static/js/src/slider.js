window.initSliders = function () {
    var splides = document.querySelectorAll('.splide');
    if (splides.length) {
        for (var i = 0; i < splides.length; i++) {
            new Splide(splides[i], {
                type: 'loop',
            }).mount();
        }
    }
};

// Auto-init on fresh load might be handled by script.js orchestrator, 
// but keeping it here for safety if script.js runs later? 
// Better to let script.js handle it to avoid double init if possible,
// OR check if already initialized. For simplicity, we'll let it be defined here
// and called by script.js.