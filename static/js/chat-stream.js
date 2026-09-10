
import { csrfToken } from './api.js';

const FRAME_END = '\n\n';

function parseFrame(frame) {
  let event = 'message';
  const data = [];

  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) data.push(line.slice(5).trim());
  }

  try {
    return { event, data: JSON.parse(data.join('\n') || '{}') };
  } catch {
    return { event, data: {} };
  }
}

/**
 * Streams one turn. `onEvent(name, data)` fires per SSE frame.
 * Resolves when the stream ends; never throws for a server-side failure --
 * those arrive as an `error` event followed by `done`.
 */
export async function streamChat({ message, sessionId, imageId, onEvent, signal }) {
  let response;
  try {
    response = await fetch('/basil/chat/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken(),
      },
      credentials: 'same-origin',
      body: JSON.stringify({
        message,
        session_id: sessionId || undefined,
        image_id: imageId || undefined,
      }),
      signal,
    });
  } catch {
    onEvent('error', { message: 'Lost the connection. Try again?' });
    onEvent('done', {});
    return;
  }

  if (!response.ok || !response.body) {
    let detail = 'Basil could not reply.';
    try {
      const body = await response.json();
      if (body.error) detail = body.error;
    } catch { /* not JSON; the status is enough */ }
    onEvent('error', { message: detail });
    onEvent('done', {});
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // A chunk can hold several frames, or half of one.
      let split;
      while ((split = buffer.indexOf(FRAME_END)) !== -1) {
        const frame = buffer.slice(0, split);
        buffer = buffer.slice(split + FRAME_END.length);
        if (frame.trim()) {
          const { event, data } = parseFrame(frame);
          onEvent(event, data);
        }
      }
    }
  } catch {
    // The stream dropped mid-turn. The caller still gets a terminal event.
    onEvent('error', { message: 'The connection dropped mid-answer.' });
    onEvent('done', {});
  }
}
