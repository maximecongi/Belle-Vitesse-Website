window.infiniteScrollId = null; // Store requestAnimationFrame ID globally to cancel it

window.initInfiniteScroll = function () {
  const wrapper = document.querySelector('.home-references-wrapper');
  const group = document.querySelector('.home-references-group');

  if (!wrapper || !group) return;

  // Clean up existing loop if restarting
  if (window.infiniteScrollId) {
    cancelAnimationFrame(window.infiniteScrollId);
  }

  // Check if we already duplicated the group to avoid infinite duplication on re-init
  if (!wrapper.querySelector('.duplicated-group')) {
    const clone = group.cloneNode(true);
    clone.classList.add('duplicated-group');
    wrapper.appendChild(clone);
  }

  let x = 0;
  const speed = 1;
  let running = true;

  function loop() {
    const ratio = window.innerWidth / window.innerHeight;

    if (ratio <= 1) {
      // Portrait → animation active
      if (!running) running = true;
      x -= speed;
      if (Math.abs(x) >= group.scrollWidth) {
        x = 0;
      }
      wrapper.style.transform = `translate3d(${x}px, 0, 0)`;
    } else {
      // Paysage → stop
      if (running) {
        wrapper.style.transform = 'translate3d(0,0,0)';
        running = false;
      }
    }

    window.infiniteScrollId = requestAnimationFrame(loop);
  }

  loop();

  window.addEventListener('resize', () => {
    x = 0;
  });
};
