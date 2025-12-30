document.addEventListener('DOMContentLoaded', function () {
    var splide = new Splide('.splide', {
        type: 'loop',
        perPage: 2,
        focus  : 0,
        omitEnd: true,
    });

    splide.mount();
});