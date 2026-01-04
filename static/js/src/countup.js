document.documentElement.classList.add('js')

document.addEventListener('DOMContentLoaded', () => {
  const ease = t => 1 - Math.pow(1 - t, 3)

  const observer = new IntersectionObserver(entries => {
    entries.forEach(({ isIntersecting, target }) => {
      if (!isIntersecting || target.dataset.done) return
      target.dataset.done = true
      target.classList.add('is-visible')

      const end = +target.dataset.target
      const start = performance.now()
      const duration = 1500

      const tick = now => {
        const t = Math.min((now - start) / duration, 1)
        target.textContent = Math.floor(ease(t) * end).toLocaleString('fr-FR')
        if (t < 1) requestAnimationFrame(tick)
        else target.textContent = end.toLocaleString('fr-FR')
      }

      requestAnimationFrame(tick)
      observer.unobserve(target)
    })
  }, { threshold: 0.6 })

  document.querySelectorAll('.count-up').forEach(el => observer.observe(el))
})
