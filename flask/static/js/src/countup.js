document.documentElement.classList.add('js')

window.initCountUp = function () {
  const ease = t => 1 - Math.pow(1 - t, 7)

  const observer = new IntersectionObserver(entries => {
    entries.forEach(({ isIntersecting, target }) => {
      if (!isIntersecting || target.dataset.done) return
      target.dataset.done = true
      target.classList.add('is-visible')

      const end = Number(target.dataset.target)
      const decimals = (target.dataset.target.split('.')[1] || '').length
      const startValue = end * 0.5
      const startTime = performance.now()
      const duration = 1500

      const tick = now => {
        const t = Math.min((now - startTime) / duration, 1)
        const value = startValue + ease(t) * (end - startValue)

        target.textContent = value.toFixed(decimals)

        if (t < 1) requestAnimationFrame(tick)
        else target.textContent = end.toFixed(decimals)
      }

      requestAnimationFrame(tick)
      observer.unobserve(target)
    })
  }, { threshold: 0.6 })

  document.querySelectorAll('.count-up').forEach(el => observer.observe(el))
}
