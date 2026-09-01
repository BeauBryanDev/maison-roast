/**
 * Image upload for the Basil rail. POST /basil/upload-image/ -> {image_id}.
 *
 * multipart, so no Content-Type header -- the browser must set the boundary.
 */

import { csrfToken } from './api.js';

// Mirrors MASTER_SPEC 8.2, enforced server-side too. Checked here only to fail
// fast with a readable message instead of after a 5 MB round trip.
export const ACCEPTED = ['image/jpeg', 'image/png'];
export const MAX_BYTES = 5 * 1024 * 1024;

export function describeRejection(file) {
  if (!ACCEPTED.includes(file.type)) return 'Only JPEG or PNG photos, sorry.';
  if (file.size > MAX_BYTES) return 'That photo is over 5 MB.';
  return null;
}

/** @returns {Promise<{ok: boolean, imageId?: string, error?: string}>} */
export async function uploadImage(file) {
  const rejection = describeRejection(file);
  if (rejection) return { ok: false, error: rejection };

  const form = new FormData();
  form.append('image', file);

  let response;
  try {
    response = await fetch('/basil/upload-image/', {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken() },
      credentials: 'same-origin',
      body: form,
    });
  } catch {
    return { ok: false, error: 'Could not reach the shop. Try again?' };
  }

  let data = {};
  try {
    data = await response.json();
  } catch { /* non-JSON error page */ }

  if (!response.ok) {
    return { ok: false, error: data.error || 'That upload did not work.' };
  }
  return { ok: true, imageId: data.image_id };
}
