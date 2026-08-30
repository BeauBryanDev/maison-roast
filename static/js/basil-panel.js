/**
 * Basil rail: open/close, persistence, and stretching the page when closed.
 *
 * This is the layout shell only. The agent itself (SSE streaming, tool calls,
 * image upload) is MASTER_SPEC.md §5/§10.3 work and arrives later as chat.js,
 * chat_stream.js and upload.js.
 */

const STORAGE_KEY = 'maisonroast.basil-rail';

/**
 * localStorage throws in some contexts (private windows, blocked site data),
 * so every access is guarded. A failure just means the rail defaults to open.
 */
function readState() {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeState(value) {
  try {
    window.localStorage.setItem(STORAGE_KEY, value);
  } catch {
    /* not persisted this session -- not worth bothering the user about */
  }
}

function apply(state) {
  const rail = document.getElementById('basil-rail');
  const reopen = document.getElementById('rail-open');
  if (!rail || !reopen) return;

  const closed = state === 'closed';
  document.body.dataset.rail = closed ? 'closed' : 'open';

  // The rail is `hidden lg:flex` in markup: removing it from the flex row is
  // what lets <main> (flex-1) stretch to the full width. Toggling a class
  // rather than style.display keeps the lg: breakpoint behaviour intact.
  rail.classList.toggle('lg:flex', !closed);
  rail.classList.toggle('lg:hidden', closed);
  reopen.hidden = !closed;
}

function init() {
  const closeBtn = document.getElementById('rail-close');
  const openBtn = document.getElementById('rail-open');
  if (!closeBtn || !openBtn) return;

  apply(readState());

  closeBtn.addEventListener('click', () => {
    apply('closed');
    writeState('closed');
    openBtn.focus(); // keep keyboard users somewhere sensible
  });

  openBtn.addEventListener('click', () => {
    apply('open');
    writeState('open');
    closeBtn.focus();
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
