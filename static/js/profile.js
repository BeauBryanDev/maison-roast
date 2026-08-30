/**
 * Profile page: GET / PUT / PATCH / DELETE against /api/users/me/.
 *
 * A browser <form> can only send GET and POST, which is why this page is driven
 * by fetch() rather than form submissions.
 */

import { request } from './api.js';

const EDITABLE = ['first_name', 'last_name', 'phone_number', 'address'];

/* --------------------------------------------------------------- helpers -- */

function showStatus(el, message, ok) {
  el.textContent = message;
  el.className = ok
    ? 'mt-6 rounded-lg border-l-4 border-green-700 bg-green-100 p-3 text-sm font-semibold text-green-900'
    : 'mt-6 rounded-lg border-l-4 border-red-700 bg-red-100 p-3 text-sm font-semibold text-red-900';
  el.hidden = false;
}

function clearErrors(scope) {
  scope.querySelectorAll('[data-error]').forEach((el) => {
    el.textContent = '';
  });
}

/**
 * DRF returns {field: ["message", ...]} for validation failures; Django's
 * PasswordChangeForm errors arrive in the same shape.
 */
function showFieldErrors(scope, data) {
  Object.entries(data || {}).forEach(([field, messages]) => {
    const target = scope.querySelector(`[data-error="${field}"]`);
    if (target) {
      target.textContent = Array.isArray(messages) ? messages.join(' ') : String(messages);
    }
  });
}

function readProfileForm(form) {
  const payload = {};
  EDITABLE.forEach((name) => {
    const field = form.elements[name];
    if (field) payload[name] = field.value;
  });
  return payload;
}

/* --------------------------------------------------------------- profile -- */

function initProfileForm() {
  const form = document.getElementById('profile-form');
  const status = document.getElementById('profile-status');
  if (!form || !status) return;

  // Save all -> PUT (full representation)
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearErrors(form);

    const { ok, data } = await request('/api/users/me/', 'PUT', readProfileForm(form));
    if (ok) {
      showStatus(status, 'Your details have been saved.', true);
    } else {
      showFieldErrors(form, data);
      showStatus(status, 'Some details could not be saved.', false);
    }
  });

  // Per-field Save -> PATCH (one key only)
  form.querySelectorAll('[data-patch]').forEach((button) => {
    button.addEventListener('click', async () => {
      const name = button.dataset.patch;
      const field = form.elements[name];
      if (!field) return;

      clearErrors(form);
      const { ok, data } = await request('/api/users/me/', 'PATCH', { [name]: field.value });
      if (ok) {
        showStatus(status, `Saved ${name.replace('_', ' ')}.`, true);
      } else {
        showFieldErrors(form, data);
        showStatus(status, 'That change could not be saved.', false);
      }
    });
  });
}

/* -------------------------------------------------------------- password -- */

function initPasswordForm() {
  const form = document.getElementById('password-form');
  const status = document.getElementById('password-status');
  if (!form || !status) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearErrors(form);

    const { ok, data } = await request('/api/users/me/password/', 'POST', {
      old_password: form.elements.old_password.value,
      new_password1: form.elements.new_password1.value,
      new_password2: form.elements.new_password2.value,
    });

    if (ok) {
      form.reset();
      // The server calls update_session_auth_hash, so the session survives.
      showStatus(status, 'Password updated. You are still signed in.', true);
    } else {
      showFieldErrors(form, data);
      const nonField = data.__all__ || data.detail;
      showStatus(status, nonField || 'Password could not be changed.', false);
    }
  });
}

/* ------------------------------------------------------------ deactivate -- */

function initDeleteForm() {
  const form = document.getElementById('delete-form');
  const status = document.getElementById('delete-status');
  if (!form || !status) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearErrors(form);

    const confirmed = window.confirm(
      'Deactivate your account? You will be signed out and will not be able to sign in again.',
    );
    if (!confirmed) return;

    const { ok, status: code, data } = await request('/api/users/me/', 'DELETE', {
      password: form.elements.password.value,
    });

    if (ok || code === 204) {
      showStatus(status, 'Your account has been deactivated. Signing you out…', true);
      window.setTimeout(() => { window.location.href = '/'; }, 1200);
    } else {
      showFieldErrors(form, data);
      showStatus(status, 'Your account was not deactivated.', false);
    }
  });
}

/* ------------------------------------------------------------------ init -- */

function init() {
  initProfileForm();
  initPasswordForm();
  initDeleteForm();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
