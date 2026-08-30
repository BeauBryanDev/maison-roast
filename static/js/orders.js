/**
 * Order deletion from My Orders / order detail.
 *
 * DELETE /api/orders/<pk>/ soft-deletes the order (is_active=False) and returns
 * the stock to the catalog. The server scopes it to the requesting user.
 */

import { request } from './api.js';

function init() {
  const buttons = document.querySelectorAll('[data-delete-order]');
  if (!buttons.length) return;

  buttons.forEach((button) => {
    button.addEventListener('click', async () => {
      const pk = button.dataset.deleteOrder;
      const label = button.dataset.orderNumber || `#${pk}`;

      if (!window.confirm(`Delete order ${label}? This cannot be undone.`)) return;

      button.disabled = true;
      const { ok, status } = await request(`/api/orders/${pk}/`, 'DELETE');

      if (ok || status === 204) {
        // Remove the row/card, or leave the detail page for the list.
        const row = button.closest('[data-order-row]');
        if (row) {
          row.remove();
          if (!document.querySelectorAll('[data-order-row]').length) {
            window.location.reload(); // fall through to the empty state
          }
        } else {
          window.location.href = '/orders/';
        }
      } else {
        button.disabled = false;
        window.alert('That order could not be deleted.');
      }
    });
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
