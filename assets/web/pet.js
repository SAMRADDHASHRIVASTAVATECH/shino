/* Nova's visible front-end: animated sprite, message bubble with quick options,
   and a plain final-output-only chat thread.
   Everything else (brain, senses, apps, music, games, learning) lives behind
   the loopback bridge. Nothing here reasons and nothing is spoken aloud. */
import { createCompanion } from '/companion/companion.js';

const petEl = document.getElementById('pet');
const chatEl = document.getElementById('chat');
const bubbleEl = document.getElementById('bubble');
const optionsEl = document.getElementById('options');
const eyeEl = document.getElementById('eye');
const inputEl = document.getElementById('msg');
const sendEl = document.getElementById('send');

const pet = await createCompanion(petEl);

let lastEventNonce = -1;
let lastStateNonce = -1;
let lastMsgNonce = -1;
let lastOptionsNonce = -1;
let replyTimer = null;
let typingTimer = null;
let lastActionAt = 0;
let typingUntil = 0;   // while you type, backend poses must not override her attention

// Default quick options; the brain can replace them with contextual ones.
const DEFAULT_OPTIONS = [
  { label: 'Hi', text: 'hi' },
  { label: 'Tell me a joke', text: 'tell me a joke' },
  { label: 'What can you do?', text: 'what can you do?' },
  { label: 'Play music', text: 'play some music' },
  { label: 'Teach me', text: 'how do i teach you something?' },
];

function renderOptions(list) {
  optionsEl.textContent = '';
  const items = Array.isArray(list) && list.length ? list : DEFAULT_OPTIONS;
  for (const opt of items) {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = String(opt.label || opt.text || '').slice(0, 34);
    b.addEventListener('click', () => send(String(opt.text || opt.label || '')));
    optionsEl.append(b);
  }
}

function setEyeUI(on) {
  eyeEl.textContent = on ? '◉' : '◎';
  eyeEl.classList.toggle('on', on);
  eyeEl.title = on
    ? 'Screen watching ON — she sees the screen and reacts. Click to stop.'
    : 'Screen watching OFF — normal mode. Click to let her see the screen.';
}

function renderMessages(list) {
  chatEl.textContent = '';
  for (const m of list) {
    const row = document.createElement('div');
    row.className = 'row ' + (m.role === 'user' ? 'user' : 'nova');
    const text = document.createElement('div');
    text.className = 'text';
    text.textContent = String(m.text || '');
    row.append(text);
    chatEl.append(row);
  }
  chatEl.scrollTop = chatEl.scrollHeight;

  // The bubble always shows only her latest final line.
  const lastNova = [...list].reverse().find(m => m.role === 'nova');
  bubbleEl.textContent = lastNova ? String(lastNova.text || '') : '';
}

async function poll() {
  try {
    const res = await fetch('/state', { cache: 'no-store' });
    if (!res.ok) return;
    const s = await res.json();
    let actionThisPoll = false;

    if (typeof s.screenshare === 'boolean') setEyeUI(s.screenshare);

    if (s.event && s.event_nonce !== lastEventNonce) {
      lastEventNonce = s.event_nonce;
      actionThisPoll = true;
      if (Date.now() < typingUntil) {
        // A pending brain event must not yank her gaze away mid-sentence.
      } else {
        lastActionAt = Date.now();
        pet.dispatch(s.event).catch(() => {});
      }
    }
    if (s.pet_state && s.pet_state_nonce !== lastStateNonce) {
      lastStateNonce = s.pet_state_nonce;
      if (Date.now() < typingUntil) {
        // You are mid-sentence: she stays looking at you, like a real person.
        actionThisPoll = true;
      } else {
        actionThisPoll = true;
        lastActionAt = Date.now();
        pet.setState(s.pet_state).catch(() => {});
      }
    }
    if (s.options_nonce !== lastOptionsNonce) {
      lastOptionsNonce = s.options_nonce;
      renderOptions(s.options);
    }
    if (s.messages_nonce !== lastMsgNonce) {
      lastMsgNonce = s.messages_nonce;
      const list = Array.isArray(s.messages) ? s.messages : [];
      renderMessages(list);
      // No spoken audio: show she is "answering" with a short animation.
      if (!actionThisPoll && list.length && list[list.length - 1].role === 'nova') {
        pet.setState('replying').catch(() => {});
        clearTimeout(replyTimer);
        replyTimer = setTimeout(() => pet.setState('idle').catch(() => {}), 1300);
      }
    }
  } catch (_) {
    // Loopback hiccup: keep the last frame, try again next tick.
  }
}

async function send(text) {
  text = String(text || '').trim();
  if (!text) return;
  inputEl.value = '';
  clearTimeout(typingTimer);
  typingUntil = 0;   // hand control back to the brain's sprite states
  try {
    await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
  } catch (_) {
    // The next poll will still show the brain's real reply if it arrived.
  }
}

eyeEl.addEventListener('click', async () => {
  const on = !eyeEl.classList.contains('on');
  try {
    const r = await fetch('/screenshare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ on }),
    });
    const d = await r.json();
    setEyeUI(!!d.screenshare);
  } catch (_) {
    setEyeUI(on);
  }
});

sendEl.addEventListener('click', () => send(inputEl.value));
inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); send(inputEl.value); }
});

/* While you type she pays attention, like someone sitting next to you. */
inputEl.addEventListener('focus', () => {
  typingUntil = Date.now() + 2500;
  pet.setState('listening').catch(() => {});
});
inputEl.addEventListener('input', () => {
  typingUntil = Date.now() + 2500;
  pet.setState('awaiting_input').catch(() => {});
  clearTimeout(typingTimer);
  typingTimer = setTimeout(() => {
    typingUntil = 0;
    if (Date.now() - lastActionAt > 1500) {
      pet.setState('idle').catch(() => {});
    }
  }, 2200);
});

renderOptions(null);
setEyeUI(false);
inputEl.focus();

setInterval(poll, 130);
poll();
