/**
 * Favourites -- browser-only, no database.
 *
 * The store is a list of product ids in localStorage. Nothing about a product
 * is copied in: the favourites page re-reads the catalog from the public API,
 * so a price change or a sold-out item shows the truth rather than a snapshot
 * taken when the heart was clicked.
 *
 * Every localStorage access is wrapped -- it throws in private windows.
 */

import { initImageFallback } from './main.js';

const KEY = 'maison.favourites';

export function read() {
  try {
    const raw = window.localStorage.getItem(KEY);
    const ids = raw ? JSON.parse(raw) : [];
    return Array.isArray(ids) ? ids.map(String) : [];
  } catch {
    return [];
  }
}

function write(ids) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(ids));
  } catch {
    /* private window, or storage full -- the page still works, it just forgets */
  }
}

export function has(id) {
  return read().includes(String(id));
}

/** @returns {boolean} true if the product is a favourite after the toggle. */
export function toggle(id) {
  const wanted = String(id);
  const ids = read();
  const at = ids.indexOf(wanted);

  if (at === -1) {
    ids.push(wanted);
    write(ids);
    return true;
  }
  ids.splice(at, 1);
  write(ids);
  return false;
}

function paint(button, on) {
  button.setAttribute('aria-pressed', on ? 'true' : 'false');
}

/**
 * Wire every heart on the page.
 *
 * Clicking an unsaved product saves it and goes to the favourites page, which
 * is what was asked for. Clicking a saved one only unsaves it -- navigating
 * away from a card the visitor just removed would strand them.
 */
export function wireHearts(root = document) {
  const buttons = root.querySelectorAll('[data-favourite]');

  buttons.forEach((button) => {
    paint(button, has(button.dataset.favourite));

    button.addEventListener('click', (event) => {
      event.preventDefault();
      const nowSaved = toggle(button.dataset.favourite);
      paint(button, nowSaved);

      if (nowSaved && !button.dataset.favouriteStay) {
        window.location.href = '/favourites/';
      } else if (!nowSaved && button.dataset.favouriteStay) {
        // On the favourites page itself the card has to leave with the heart.
        button.closest('[data-favourite-card]')?.remove();
        refreshEmptyState();
      }
    });
  });
}

/* ------------------------------------------------------------------ *
 * The favourites page                                                 *
 * ------------------------------------------------------------------ */

function esc(value) {
  const div = document.createElement('div');
  div.textContent = value == null ? '' : String(value);
  return div.innerHTML;
}

function card(product, fallbackIcon) {
  const buyable = product.available && product.stock > 0;
  const image = product.product_image
    ? `<img src="${esc(product.product_image)}" alt="${esc(product.name)}" loading="lazy" data-fallback>`
    : '';

  return `
    <article class="panel-dark flex flex-col overflow-hidden transition hover:-translate-y-1"
             data-favourite-card="${esc(product.id)}">
      <div class="img-frame">
        <button type="button" class="btn-heart" data-favourite="${esc(product.id)}"
                data-favourite-stay="1" aria-pressed="true"
                aria-label="Remove ${esc(product.name)} from my favourites">
          <img src="${esc(fallbackIcon.heart)}" alt="" aria-hidden="true">
        </button>
        ${image}
        <span class="img-fallback"${product.product_image ? ' hidden' : ''}>
          <img src="${esc(fallbackIcon.pot)}" alt="" class="h-20 w-20" aria-hidden="true">
        </span>
        ${buyable ? '' : `
        <span class="absolute bottom-3 left-3 rounded-full bg-red-800/90 px-3 py-1 text-xs uppercase tracking-wider text-crema">
          Out of Stock
        </span>`}
      </div>

      <div class="flex flex-1 flex-col p-5">
        <h2 class="font-display text-xl font-bold text-crema">
          <a href="/products/${esc(product.slug)}/" class="transition hover:text-gold-400">${esc(product.name)}</a>
        </h2>
        <p class="mt-2 line-clamp-2 text-sm leading-relaxed text-crema/70">${esc(product.description)}</p>
        <div class="mt-4 flex items-baseline justify-between">
          <span class="font-display text-2xl text-terracotta-400">$${esc(product.price)}</span>
          <span class="text-xs uppercase tracking-wider text-crema/50">${esc(product.stock)} in stock</span>
        </div>
        <div class="mt-5 flex gap-2">
          <a href="/products/${esc(product.slug)}/" class="btn-ghost flex-1 text-xs">Details</a>
          ${buyable
            ? `<a href="/orders/add_product_order/?product_id=${esc(product.id)}"
                  class="btn-terracotta flex-1 px-4 py-2 text-xs">Buy Now</a>`
            : `<span class="inline-flex flex-1 items-center justify-center rounded-full bg-roast-600 px-4 py-2 text-xs uppercase tracking-wider text-crema/50">
                 Unavailable
               </span>`}
        </div>
      </div>
    </article>`;
}

function refreshEmptyState() {
  const grid = document.getElementById('favourites-grid');
  const empty = document.getElementById('favourites-empty');
  if (!grid || !empty) return;

  const count = grid.querySelectorAll('[data-favourite-card]').length;
  grid.hidden = count === 0;
  empty.hidden = count !== 0;

  const label = document.getElementById('favourites-count');
  if (label) {
    label.textContent = count === 1 ? '1 saved item' : `${count} saved items`;
  }
}

async function renderFavourites(page) {
  const grid = document.getElementById('favourites-grid');
  const loading = document.getElementById('favourites-loading');
  const failed = document.getElementById('favourites-error');
  const ids = read();

  if (ids.length === 0) {
    if (loading) loading.hidden = true;
    refreshEmptyState();
    return;
  }

  let products = [];
  try {
    const response = await fetch('/api/products/', {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
    });
    if (!response.ok) throw new Error(String(response.status));
    products = await response.json();
  } catch {
    if (loading) loading.hidden = true;
    if (failed) failed.hidden = false;
    return;
  }

  const icons = { heart: page.dataset.heartIcon, pot: page.dataset.potIcon };
  const wanted = new Set(ids);
  const chosen = products.filter((p) => wanted.has(String(p.id)));

  // A product deleted from the catalog is dropped from the store rather than
  // left behind as an id that can never render.
  const alive = new Set(chosen.map((p) => String(p.id)));
  if (alive.size !== ids.length) write(ids.filter((id) => alive.has(id)));

  // Keep the order the visitor saved them in.
  chosen.sort((a, b) => ids.indexOf(String(a.id)) - ids.indexOf(String(b.id)));

  if (loading) loading.hidden = true;
  grid.innerHTML = chosen.map((p) => card(p, icons)).join('');
  wireHearts(grid);
  // These cards were injected after main.js ran, so they need wiring too.
  initImageFallback(grid);
  refreshEmptyState();
}

const page = document.getElementById('favourites-page');
if (page) {
  renderFavourites(page);
} else {
  wireHearts();
}
