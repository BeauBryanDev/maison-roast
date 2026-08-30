/**
 * Shared fetch helper for the JSON API.
 *
 * The API uses DRF's SessionAuthentication, which enforces CSRF on every unsafe
 * method. Miss the X-CSRFToken header and the request comes back as a 403 that
 * looks nothing like a CSRF problem -- so it is centralised here.
 */

export function csrfToken() {
  const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
  if (input) return input.value;

  // Fallback: read the cookie directly (set whenever a page rendered {% csrf_token %}).
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : '';
}

/**
 * @returns {Promise<{ok: boolean, status: number, data: object}>}
 *   `data` is the parsed JSON body, or {} for 204/empty responses.
 */
export async function request(url, method, body) {
  const options = {
    method,
    headers: {
      'X-CSRFToken': csrfToken(),
      'X-Requested-With': 'XMLHttpRequest',
    },
    credentials: 'same-origin',
  };

  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }

  const response = await fetch(url, options);

  let data = {};
  if (response.status !== 204) {
    try {
      data = await response.json();
    } catch {
      data = {}; // non-JSON error page; the status still tells us what happened
    }
  }

  return { ok: response.ok, status: response.status, data };
}
