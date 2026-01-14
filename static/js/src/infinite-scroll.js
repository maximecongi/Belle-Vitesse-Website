(() => {
  const wrapper = document.querySelector('.home-references-wrapper');
  const group = document.querySelector('.home-references-group');

  if (!wrapper || !group) return;

  // DUPLICATION
  const clone = group.cloneNode(true);
  clone.classList.add('duplicated-group');
  wrapper.appendChild(clone);

  let x = 0;
  const speed = 1;
  let rafId = null;
  let contentWidth = 0;

  function computeWidth() {
    contentWidth = group.getBoundingClientRect().width;
  }

  function isPortrait() {
    return window.matchMedia('(orientation: portrait)').matches;
  }

  function animate() {
    x -= speed;

    if (Math.abs(x) >= contentWidth) {
      x = 0;
    }

    wrapper.style.transform = `translate3d(${x}px, 0, 0)`;
    rafId = requestAnimationFrame(animate);
  }

  function start() {
    if (rafId) return;
    animate();
  }

  function stop() {
    if (!rafId) return;
    cancelAnimationFrame(rafId);
    rafId = null;
    wrapper.style.transform = 'translate3d(0,0,0)';
    x = 0;
  }

  function checkOrientation() {
    computeWidth();

    if (isPortrait()) {
      start();
    } else {
      stop();
    }
  }


  window.addEventListener('load', () => {
    computeWidth();
    checkOrientation();
  });

  window.addEventListener('resize', () => {
    stop();
    checkOrientation();
  });

  window.addEventListener('orientationchange', () => {
    setTimeout(checkOrientation, 300);
  });
})();
