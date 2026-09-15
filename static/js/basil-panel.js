
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
    openBtn.focus();  
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
