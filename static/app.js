/* ── Forte by Automatey — Frontend ─────────────────────────────────────── */

// ── State ─────────────────────────────────────────────────────────────────
let activeEvent    = null;   // {id, title, desc, date, category}
let importedEvents = [];     // events waiting for review

// ── Dashboard helpers ─────────────────────────────────────────────────────

function openEventFromDash(id, title, desc, dateStr, category) {
  activeEvent = { id, title, desc, date: dateStr, category };
  const panel = document.getElementById('genPanel');
  document.getElementById('genTitle').textContent   = title;
  document.getElementById('genDate').textContent    = formatDate(dateStr);
  document.getElementById('genDesc').textContent    = desc || '';
  const catEl = document.getElementById('genCategory');
  catEl.textContent = capFirst(category);
  catEl.className   = `gen-event-category ${category}`;
  document.getElementById('genResults').innerHTML  = '';
  document.getElementById('genToneOverride').value = '';
  document.getElementById('btnGenerate').disabled  = false;
  document.getElementById('btnGenerate').textContent = 'Generate drafts';
  panel.classList.add('open');
}

async function copyDraftById(draftId, content, btn) {
  navigator.clipboard.writeText(content).catch(() => {
    const ta = document.createElement('textarea');
    ta.value = content; document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
  });
  btn.textContent = '✓ Copied!';
  btn.classList.add('copied');
  setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
}

async function markPosted(draftId, btn) {
  try {
    const resp = await fetch(`/api/drafts/${draftId}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'posted' }),
    });
    if (!resp.ok) throw new Error((await resp.json()).error);
    btn.textContent = 'Posted';
    btn.disabled = true;
    const badge = document.getElementById(`sb-${draftId}`);
    if (badge) {
      badge.textContent = 'Posted ✓';
      badge.className = 'status-badge posted';
    }
    showToast('Marked as posted!');
  } catch (err) {
    showToast('Error: ' + err.message);
  }
}

function designInCanvaByPlatform(platform, content) {
  navigator.clipboard.writeText(content).catch(() => {});
  const urls = {
    facebook:  'https://www.canva.com/create/facebook-posts/',
    instagram: 'https://www.canva.com/create/instagram-posts/',
  };
  window.open(urls[platform] || 'https://www.canva.com/', '_blank');
  showToast('Post text copied — paste it into your Canva design!');
}

// ── Event Panel ───────────────────────────────────────────────────────────

function openEvent(el) {
  activeEvent = {
    id:       parseInt(el.dataset.id),
    title:    el.dataset.title,
    desc:     el.dataset.desc,
    date:     el.dataset.date,
    category: el.dataset.category,
  };

  const panel = document.getElementById('genPanel');
  document.getElementById('genTitle').textContent    = activeEvent.title;
  document.getElementById('genDate').textContent     = formatDate(activeEvent.date);
  document.getElementById('genDesc').textContent     = activeEvent.desc || '';
  const catEl = document.getElementById('genCategory');
  catEl.textContent  = capFirst(activeEvent.category);
  catEl.className    = `gen-event-category ${activeEvent.category}`;

  document.getElementById('genResults').innerHTML = '';
  document.getElementById('genToneOverride').value = '';
  document.getElementById('btnGenerate').disabled  = false;
  document.getElementById('btnGenerate').textContent = 'Generate drafts';

  panel.classList.add('open');
}

function closePanel() {
  document.getElementById('genPanel').classList.remove('open');
  activeEvent = null;
}

// ── Generate Drafts ───────────────────────────────────────────────────────

async function generateDrafts() {
  if (!activeEvent) return;

  const platforms = Array.from(
    document.querySelectorAll('.plat-card.active input')
  ).map(cb => cb.value);

  if (!platforms.length) {
    showToast('Select at least one platform.'); return;
  }

  const tone  = document.getElementById('genToneOverride').value.trim();
  const btn   = document.getElementById('btnGenerate');
  const results = document.getElementById('genResults');

  btn.disabled     = true;
  btn.textContent  = 'Generating…';
  results.innerHTML = `
    <div class="gen-loading">
      <div class="gen-spinner"></div>
      <div class="gen-loading-text">Writing in BPA's tone of voice…</div>
    </div>`;

  try {
    const resp = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_id:      activeEvent.id,
        tone_override: tone,
        platforms,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Generation failed');

    results.innerHTML = '';

    // Photo brief block
    if (data.photo_brief) {
      const brief = document.createElement('div');
      brief.className = 'photo-brief-panel';
      brief.innerHTML = `
        <div class="photo-brief-header">📷 Photo brief — what to capture</div>
        <div class="photo-brief-body">${escHtml(data.photo_brief)}</div>
      `;
      results.appendChild(brief);
    }

    const platformOrder = ['facebook', 'instagram', 'linkedin', 'x', 'classdojo', 'email'];
    const platformMeta = {
      facebook:  { label: 'Facebook',    icon: 'f',   canva: 'facebook_post' },
      instagram: { label: 'Instagram',   icon: '📷',  canva: 'instagram_post' },
      linkedin:  { label: 'LinkedIn',    icon: 'in',  canva: null },
      x:         { label: 'X / Twitter', icon: '𝕏',  canva: null },
      classdojo: { label: 'ClassDojo',   icon: '🏫',  canva: null },
      email:     { label: 'Newsletter',  icon: '✉️',  canva: null },
    };
    const bestTimes = data.best_times || {};

    platformOrder.filter(p => p in data.drafts).forEach(platform => {
      const content   = data.drafts[platform];
      const meta      = platformMeta[platform];
      const bt        = bestTimes[platform];
      const card      = document.createElement('div');
      card.className  = 'draft-card';

      const canvaBtn = meta.canva
        ? `<button class="btn-canva" onclick="designInCanva('${platform}', '${meta.canva}', this)" title="Create a graphic in Canva">🎨 Canva</button>`
        : '';
      const btHtml = bt
        ? `<div class="draft-best-time">⏰ Best time: ${bt.days} · ${bt.time} <span class="bt-note">(${bt.note})</span></div>`
        : '';

      card.innerHTML = `
        <div class="draft-card-header">
          <div class="draft-platform-name">
            <span class="plat-icon">${meta.icon}</span> ${meta.label}
          </div>
          <div class="draft-card-actions">
            ${canvaBtn}
            <button class="btn-regen" onclick="regenSingle('${platform}', this)">↺ Redo</button>
            <button class="btn-copy" onclick="copyDraft(this)">Copy</button>
          </div>
        </div>
        <div class="draft-content">${escHtml(content)}</div>
        ${btHtml}
        <div class="draft-char-count">${content.length} chars</div>
      `;
      results.appendChild(card);
    });

  } catch (err) {
    results.innerHTML = `<div style="color:var(--red);padding:16px;font-size:13px;">Error: ${err.message}</div>`;
  }

  btn.disabled    = false;
  btn.textContent = 'Regenerate all';
}

async function regenSingle(platform, btn) {
  if (!activeEvent) return;
  const tone  = document.getElementById('genToneOverride').value.trim();
  const card  = btn.closest('.draft-card');
  const content = card.querySelector('.draft-content');
  const origText = btn.textContent;

  btn.textContent = '…';
  btn.disabled    = true;
  content.style.opacity = '0.4';

  try {
    const resp = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_id: activeEvent.id,
        tone_override: tone,
        platforms: [platform],
      }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error);
    const newContent = data.drafts[platform];
    content.textContent = newContent;
    card.querySelector('.draft-char-count').textContent = `${newContent.length} chars`;
  } catch (err) {
    showToast('Redo failed: ' + err.message);
  }

  btn.textContent       = origText;
  btn.disabled          = false;
  content.style.opacity = '1';
}

// ── Copy to Clipboard ─────────────────────────────────────────────────────

function copyDraft(btn) {
  const content = btn.closest('.draft-card').querySelector('.draft-content').textContent;
  navigator.clipboard.writeText(content).then(() => {
    btn.textContent = '✓ Copied!';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = 'Copy';
      btn.classList.remove('copied');
    }, 2000);
  }).catch(() => {
    // Fallback for older browsers
    const ta = document.createElement('textarea');
    ta.value = content;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    btn.textContent = '✓ Copied!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
  });
}

// ── Canva Design ──────────────────────────────────────────────────────────

function designInCanva(platform, canvaType, btn) {
  const content = btn.closest('.draft-card').querySelector('.draft-content').textContent;
  // Copy text first so they can paste it into Canva
  navigator.clipboard.writeText(content).catch(() => {});

  // Open Canva with the appropriate template type
  const urls = {
    facebook_post:  'https://www.canva.com/create/facebook-posts/',
    instagram_post: 'https://www.canva.com/create/instagram-posts/',
    flyer:          'https://www.canva.com/create/flyers/',
  };
  const url = urls[canvaType] || 'https://www.canva.com/';
  window.open(url, '_blank');

  showToast('Post text copied — paste it into your Canva design!');
}

// ── Platform Toggles ──────────────────────────────────────────────────────

document.querySelectorAll('.plat-card').forEach(label => {
  label.addEventListener('click', () => {
    const cb = label.querySelector('input');
    cb.checked = !cb.checked;
    label.classList.toggle('active', cb.checked);
  });
});

// ── Add / Edit Event Modal ────────────────────────────────────────────────

document.getElementById('addEventBtn').addEventListener('click', () => {
  document.getElementById('editEventId').value = '';
  document.getElementById('eventModalTitle').textContent = 'Add event';
  document.getElementById('evTitle').value    = '';
  document.getElementById('evDate').value     = '';
  document.getElementById('evCategory').value = 'community';
  document.getElementById('evDesc').value     = '';
  document.getElementById('eventModalOverlay').classList.add('open');
});

function openEditModal() {
  if (!activeEvent) return;
  document.getElementById('editEventId').value     = activeEvent.id;
  document.getElementById('eventModalTitle').textContent = 'Edit event';
  document.getElementById('evTitle').value         = activeEvent.title;
  document.getElementById('evDate').value          = activeEvent.date;
  document.getElementById('evCategory').value      = activeEvent.category;
  document.getElementById('evDesc').value          = activeEvent.desc || '';
  document.getElementById('eventModalOverlay').classList.add('open');
}

function closeEventModal() {
  document.getElementById('eventModalOverlay').classList.remove('open');
}

async function saveEvent() {
  const id    = document.getElementById('editEventId').value;
  const title = document.getElementById('evTitle').value.trim();
  const date  = document.getElementById('evDate').value;
  const cat   = document.getElementById('evCategory').value;
  const desc  = document.getElementById('evDesc').value.trim();

  if (!title || !date) { showToast('Title and date are required.'); return; }

  const body = { title, date, category: cat, description: desc };
  const url  = id ? `/api/events/${id}` : '/api/events';
  const method = id ? 'PUT' : 'POST';

  try {
    const resp = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error((await resp.json()).error);
    closeEventModal();
    showToast(id ? 'Event updated — refreshing…' : 'Event added — refreshing…');
    setTimeout(() => location.reload(), 800);
  } catch (err) {
    showToast('Error: ' + err.message);
  }
}

async function deleteEvent() {
  if (!activeEvent) return;
  if (!confirm(`Delete "${activeEvent.title}"? This cannot be undone.`)) return;
  try {
    const resp = await fetch(`/api/events/${activeEvent.id}`, { method: 'DELETE' });
    if (!resp.ok) throw new Error((await resp.json()).error);
    closePanel();
    showToast('Event deleted — refreshing…');
    setTimeout(() => location.reload(), 800);
  } catch (err) {
    showToast('Error: ' + err.message);
  }
}

// ── File Import ───────────────────────────────────────────────────────────

document.getElementById('importBtn').addEventListener('click', () => {
  document.getElementById('importOverlay').classList.add('open');
});

function closeImport() {
  document.getElementById('importOverlay').classList.remove('open');
  document.getElementById('importProgress').style.display = 'none';
  document.getElementById('importDropZone').style.display = '';
}

// Drag-and-drop
const dropZone = document.getElementById('importDropZone');

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));

dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleImportFile(file);
});

document.getElementById('importFileInput').addEventListener('change', e => {
  if (e.target.files[0]) handleImportFile(e.target.files[0]);
});

async function handleImportFile(file) {
  document.getElementById('importDropZone').style.display = 'none';
  document.getElementById('importProgress').style.display = 'flex';

  const fd = new FormData();
  fd.append('file', file);

  try {
    const resp = await fetch('/api/import', { method: 'POST', body: fd });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error);

    importedEvents = data.events || [];
    closeImport();
    openReview(importedEvents);
  } catch (err) {
    closeImport();
    showToast('Import error: ' + err.message);
  }
}

// ── Import Review Modal ───────────────────────────────────────────────────

function openReview(events) {
  const list = document.getElementById('reviewList');
  const sub  = document.getElementById('reviewSub');
  sub.textContent = `Found ${events.length} event${events.length !== 1 ? 's' : ''} — deselect any you don't want to add.`;
  list.innerHTML = '';

  events.forEach((ev, i) => {
    const item = document.createElement('div');
    item.className = 'review-item';
    item.innerHTML = `
      <input type="checkbox" id="rev-${i}" checked>
      <div class="review-item-info">
        <div class="review-item-title">
          ${escHtml(ev.title)}
          <span class="review-item-cat ${ev.category || 'community'}">${capFirst(ev.category || 'community')}</span>
        </div>
        <div class="review-item-meta">${formatDate(ev.date)}${ev.description ? ' · ' + ev.description.substring(0, 80) : ''}</div>
      </div>
    `;
    list.appendChild(item);
  });

  document.getElementById('reviewOverlay').classList.add('open');
}

function closeReview() {
  document.getElementById('reviewOverlay').classList.remove('open');
}

async function confirmImport() {
  const checkboxes = document.querySelectorAll('#reviewList input[type="checkbox"]');
  const selected   = importedEvents.filter((_, i) => checkboxes[i]?.checked);

  if (!selected.length) { showToast('No events selected.'); return; }

  try {
    const resp = await fetch('/api/import/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ events: selected }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error);
    closeReview();
    showToast(`${data.added} event${data.added !== 1 ? 's' : ''} added — refreshing…`);
    setTimeout(() => location.reload(), 900);
  } catch (err) {
    showToast('Error: ' + err.message);
  }
}

// ── Utilities ─────────────────────────────────────────────────────────────

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}

function formatDate(isoStr) {
  if (!isoStr) return '';
  const [y, m, d] = isoStr.split('-').map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
}

function capFirst(str) {
  return str ? str.charAt(0).toUpperCase() + str.slice(1) : '';
}

function escHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Close panel when clicking outside on mobile
document.getElementById('calMain').addEventListener('click', e => {
  if (!e.target.closest('.cal-event') && document.getElementById('genPanel').classList.contains('open')) {
    // Don't close on desktop — let users keep reading while navigating
  }
});
