window.initSplide = function () {
    var splides = document.querySelectorAll('.splide');
    if (splides.length) {
        for (var i = 0; i < splides.length; i++) {
            new Splide(splides[i], {
                type: 'loop',
            }).mount();
        }
    }
};