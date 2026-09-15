// Renders the small subset of markdown Basil actually emits, as real DOM
// nodes. The system prompt bans markdown and the model writes it anyway, so
// the rail formats it rather than showing raw asterisks to the customer.

const INLINE = /\*\*(?!\s)([\s\S]+?)(?<!\s)\*\*|\*(?!\s)([^*\n]+?)(?<!\s)\*|`([^`\n]+)`/g;

const BULLET = /^\s*[-*•]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;
const HEADING = /^\s*#{1,6}\s+(.*)$/;

// Inline spans -> a fragment of text nodes, <strong>, <em> and <code>.
function inline(text) {
  const frag = document.createDocumentFragment();
  let last = 0;

  for (const m of text.matchAll(INLINE)) {
    if (m.index > last) {
      frag.appendChild(document.createTextNode(text.slice(last, m.index)));
    }

    const [tag, content] = m[1] !== undefined ? ['strong', m[1]]
      : m[2] !== undefined ? ['em', m[2]]
      : ['code', m[3]];

    const el = document.createElement(tag);
    // Bold nests italics often enough to be worth one level of recursion;
    // code is literal by definition.
    el.appendChild(tag === 'code' ? document.createTextNode(content) : inline(content));
    if (tag === 'code') el.className = 'rounded bg-espresso/60 px-1 text-[0.9em]';
    frag.appendChild(el);

    last = m.index + m[0].length;
  }

  if (last < text.length) {
    frag.appendChild(document.createTextNode(text.slice(last)));
  }
  return frag;
}

function listItem(text) {
  const li = document.createElement('li');
  li.appendChild(inline(text));
  return li;
}

// Group consecutive list lines into one <ul>/<ol>; everything else is a <p>.
function blocks(text) {
  const frag = document.createDocumentFragment();
  const lines = text.split('\n');
  let list = null;
  let paragraph = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const p = document.createElement('p');
    p.appendChild(inline(paragraph.join('\n')));
    frag.appendChild(p);
    paragraph = [];
  };

  const flushList = () => {
    if (list) frag.appendChild(list);
    list = null;
  };

  for (const line of lines) {
    const heading = HEADING.exec(line);
    const bullet = BULLET.exec(line);
    const numbered = NUMBERED.exec(line);

    if (heading) {
      flushParagraph();
      flushList();
      const el = document.createElement('p');
      el.className = 'font-display text-[1.05em] text-crema';
      el.appendChild(inline(heading[1]));
      frag.appendChild(el);
      continue;
    }

    if (bullet || numbered) {
      flushParagraph();
      const wanted = bullet ? 'UL' : 'OL';
      if (list && list.tagName !== wanted) flushList();
      if (!list) {
        list = document.createElement(wanted.toLowerCase());
        list.className = bullet
          ? 'list-disc space-y-1 pl-5'
          : 'list-decimal space-y-1 pl-5';
      }
      list.appendChild(listItem((bullet || numbered)[1]));
      continue;
    }

    flushList();
    if (line.trim() === '') flushParagraph();
    else paragraph.push(line);
  }

  flushParagraph();
  flushList();
  return frag;
}

/** Replace el's contents with `text` rendered as markdown. */
export function renderMarkdown(el, text) {
  el.replaceChildren();
  el.classList.add('space-y-2');
  el.appendChild(blocks(String(text ?? '')));
}
