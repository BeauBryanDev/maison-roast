/**
 * Site-wide behaviour: mobile navigation, scroll reveal, product-image fallback.
 *
 * Vanilla ES module, no framework -- MASTER_SPEC.md §3 rules out React, Vue,
 * Alpine and HTMX for this project.
 */

/* ------------------------------------------------------------------ nav ---- */

function initMobileNav() {
  const toggle = document.getElementById('nav-toggle');
  const panel = document.getElementById('mobile-nav');
  if (!toggle || !panel) return;

  toggle.addEventListener('click', () => {
    const open = panel.hidden;
    panel.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  });
}

/* --------------------------------------------------------------- reveal ---- */

function initScrollReveal() {
  const targets = document.querySelectorAll('.reveal');
  if (!targets.length) return;

  // No IntersectionObserver, or the user asked for reduced motion: show
  // everything immediately. Content must never be left invisible.
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduced || !('IntersectionObserver' in window)) {
    targets.forEach((el) => el.classList.add('is-visible'));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target); // reveal once, then stop watching
      });
    },
    { rootMargin: '0px 0px -10% 0px', threshold: 0.05 },
  );

  targets.forEach((el) => observer.observe(el));
}

/* ------------------------------------------------------- image fallback ---- */

/**
 * Product images are external URLs (Product.product_image is a URLField), so
 * they rot. On error we hide the broken <img> and reveal the local placeholder
 * that sits behind it, keeping the card's shape intact.
 */
function initImageFallback() {
  document.querySelectorAll('img[data-fallback]').forEach((img) => {
    const fail = () => {
      img.style.visibility = 'hidden';
      const frame = img.closest('.img-frame');
      const placeholder = frame && frame.querySelector('.img-fallback');
      if (placeholder) placeholder.hidden = false;
    };

    // complete && naturalWidth === 0 means it already failed before this ran.
    if (img.complete && img.naturalWidth === 0) fail();
    img.addEventListener('error', fail);
  });
}

/* ----------------------------------------------------------------- init ---- */

function init() {
  initMobileNav();
  initScrollReveal();
  initImageFallback();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
