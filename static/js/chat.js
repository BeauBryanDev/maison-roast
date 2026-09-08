/**
 * Basil chat in the rail: composer, streamed replies, image drop zone.
 */

import { streamChat } from './chat-stream.js';
import { uploadImage, describeRejection } from './upload.js';

const SESSION_KEY = 'basil.session';
const LOG_KEY = 'basil.log';
const CACHE_LIMIT = 60;

const rail = document.getElementById('basil-rail');
const log = document.getElementById('basil-log');
const form = document.getElementById('basil-form');
const input = document.getElementById('basil-input');
const send = document.getElementById('basil-send');
const filePicker = document.getElementById('basil-file');
const attach = document.getElementById('basil-attach');
const dropZone = document.getElementById('basil-drop');
const status = document.getElementById('basil-status');
const greeting = document.getElementById('basil-greeting');

// Every page ships the rail markup, but a template could drop it.
if (rail && log && form && input) {
  let sessionId = readSession();
  let transcript = [];
  let pending = null; // {imageId, url} waiting to ride along with the next message
  let busy = false;

  // session id  

  function readSession() {
    try {
      return localStorage.getItem(SESSION_KEY) || '';
    } catch {
      return ''; // private windows throw on access
    }
  }

  function writeSession(id) {
    sessionId = id;
    try {
      localStorage.setItem(SESSION_KEY, id);
    } catch { /* nothing to do; the turn still works */ }
  }

  function forgetSession() {
    sessionId = '';
    transcript = [];
    try {
      localStorage.removeItem(SESSION_KEY);
      localStorage.removeItem(LOG_KEY);
    } catch { /* ignore */ }
  }

  //  local cache of the transcript  
  // The DB stays the source of truth. This only makes the rail redraw
  // instantly on a page change instead of blank until the fetch lands.

  function readCache() {
    try {
      const raw = JSON.parse(localStorage.getItem(LOG_KEY) || 'null');
      if (!raw || raw.sessionId !== sessionId) return [];
      return Array.isArray(raw.messages) ? raw.messages : [];
    } catch {
      return [];
    }
  }

  function saveCache() {
    try {
      localStorage.setItem(LOG_KEY, JSON.stringify({
        sessionId,
        messages: transcript.slice(-CACHE_LIMIT),
      }));
    } catch { /* private window, or quota: the server still has it */ }
  }

  function remember(message) {
    transcript.push(message);
    saveCache();
  }

  function draw(messages) {
    log.replaceChildren();
    for (const message of messages) {
      // A blob: URL from this tab dies on navigation, so only a real path
      // from the server is worth redrawing.
      if (message.image_url) thumbnail(message.image_url);
      if (message.text) bubble(message.role).textContent = message.text;
    }
    scrollToEnd();
  }

  //   rendering  

  function scrollToEnd() {
    log.scrollTop = log.scrollHeight;
  }

  function bubble(role) {
    const el = document.createElement('div');
    el.className = role === 'user'
      ? 'ml-auto max-w-[85%] rounded-xl rounded-br-none bg-terracotta/90 p-3 text-sm leading-relaxed text-crema'
      : 'max-w-[90%] rounded-xl rounded-tl-none bg-roast p-3 text-sm leading-relaxed';
    log.appendChild(el);
    scrollToEnd();
    return el;
  }

  function note(text, tone = 'muted') {
    const el = document.createElement('p');
    el.className = tone === 'error'
      ? 'text-center text-xs text-terracotta'
      : 'text-center text-xs text-crema/50';
    el.textContent = text;
    log.appendChild(el);
    scrollToEnd();
  }

  function thumbnail(url, alt = 'Photo you sent') {
    const wrap = document.createElement('div');
    wrap.className = 'ml-auto max-w-[60%] overflow-hidden rounded-xl border border-gold/30';
    const img = document.createElement('img');
    img.src = url;
    img.alt = alt;
    img.className = 'block w-full';
    wrap.appendChild(img);
    log.appendChild(wrap);
    scrollToEnd();
  }

  function setStatus(text) {
    if (status) status.textContent = text;
  }

  function setBusy(value) {
    busy = value;
    input.disabled = value;
    if (send) send.disabled = value;
    if (attach) attach.disabled = value;
    setStatus(value ? 'Thinking…' : 'Online');
  }

  //  the turn 

  async function sendTurn(text, imageId, isRetry = false) {
    setBusy(true);

    let reply = null;
    let failed = null;

    await streamChat({
      message: text,
      sessionId,
      imageId,
      onEvent(event, data) {
        if (event === 'session') {
          writeSession(data.session_id);
        } else if (event === 'token') {
          if (!reply) reply = bubble('assistant');
          reply.textContent += data.text;
          scrollToEnd();
        } else if (event === 'tool_start') {
          setStatus(toolLabel(data.name));
        } else if (event === 'tool_end') {
          setStatus('Thinking…');
        } else if (event === 'error') {
          failed = data.message;
        }
      },
    });

    // A stale id in localStorage (server session rotated, or another account
    // signed in here) -- start a fresh conversation once rather than dead-end.
    if (failed === 'Unknown chat session.' && !isRetry) {
      forgetSession();
      return sendTurn(text, imageId, true);
    }

    if (reply) remember({ role: 'assistant', text: reply.textContent });
    if (failed) note(failed, 'error');
    setBusy(false);
    input.focus();
    return undefined;
  }

  function toolLabel(name) {
    const labels = {
      search_menu: 'Checking the menu…',
      get_product_details: 'Looking that up…',
      check_product_availability: 'Checking the case…',
      create_order: 'Writing up your order…',
      read_orders: 'Finding your orders…',
      vision_identify: 'Looking at your photo…',
    };
    return labels[name] || 'One sec…';
  }

  // -- restoring the conversation ------------------------------------------

  async function restore() {
    // Two layers, on purpose. localStorage paints the transcript immediately
    // on a page change; the DB is the source of truth (MASTER_SPEC 2.5) and
    // corrects it a moment later. The cache alone would drift -- it cannot
    // see a turn sent from another tab or another device.
    const cached = readCache();
    if (cached.length) {
      transcript = cached;
      greeting?.remove();
      draw(transcript);
    }

    let data;
    try {
      const response = await fetch('/basil/history/', {
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!response.ok) return;
      data = await response.json();
    } catch {
      return; // offline: the cache we already drew is the best we have
    }

    // A different session means this browser is looking at someone else's
    // thread -- a sign-in, a sign-out, or a cleared server session.
    if (data.session_id && data.session_id !== sessionId) {
      writeSession(data.session_id);
    }

    if (!data.messages.length) {
      if (cached.length) { // the server has nothing: the cache is stale
        transcript = [];
        saveCache();
        draw(transcript);
        if (greeting) log.appendChild(greeting);
      }
      return;
    }

    greeting?.remove();
    transcript = data.messages;
    saveCache();
    draw(transcript);
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (busy) return;

    const text = input.value.trim();
    const image = pending;
    if (!text && !image) return;

    greeting?.remove();
    input.value = '';
    if (image) {
      thumbnail(image.url);
      clearPending();
    }
    if (text) bubble('user').textContent = text;

    // The blob: URL is not cached -- it dies with this page. The next restore
    // picks the photo up from the server with a real path.
    remember({ role: 'user', text });

    sendTurn(text, image ? image.imageId : '');
  });

  //   images  

  function clearPending() {
    if (pending) URL.revokeObjectURL(pending.url);
    pending = null;
    input.placeholder = 'Ask Basil anything…';
  }

  async function stageFile(file) {
    if (!file || busy) return;

    const rejection = describeRejection(file);
    if (rejection) {
      note(rejection, 'error');
      return;
    }

    setStatus('Uploading your photo…');
    const result = await uploadImage(file);
    setStatus('Online');

    if (!result.ok) {
      note(result.error, 'error');
      return;
    }

    clearPending();
    pending = { imageId: result.imageId, url: URL.createObjectURL(file) };
    input.placeholder = 'Photo ready — add a note, or just send.';
    input.focus();
  }

  if (attach && filePicker) {
    attach.addEventListener('click', () => filePicker.click());
    filePicker.addEventListener('change', () => {
      stageFile(filePicker.files[0]);
      filePicker.value = ''; // so the same file can be picked twice
    });
  }

  // Drag and drop over the whole rail. dragover must be cancelled or the
  // browser navigates to the dropped file instead.
  let dragDepth = 0;

  rail.addEventListener('dragenter', (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    dragDepth += 1;
    if (dropZone) dropZone.hidden = false;
  });

  rail.addEventListener('dragover', (event) => {
    if (hasFiles(event)) event.preventDefault();
  });

  rail.addEventListener('dragleave', () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0 && dropZone) dropZone.hidden = true;
  });

  rail.addEventListener('drop', (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    dragDepth = 0;
    if (dropZone) dropZone.hidden = true;
    stageFile(event.dataTransfer.files[0]);
  });

  input.addEventListener('paste', (event) => {
    const item = [...(event.clipboardData?.items || [])]
      .find((entry) => entry.kind === 'file');
    if (!item) return;
    event.preventDefault();
    stageFile(item.getAsFile());
  });

  function hasFiles(event) {
    return [...(event.dataTransfer?.types || [])].includes('Files');
  }

  setStatus('Online');
  restore();
}
