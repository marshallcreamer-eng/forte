/* ── Forte by Automatey — Frontend ─────────────────────────────────────── */

// ── State ─────────────────────────────────────────────────────────────────
let activeEvent     = null;   // {id, title, desc, date, category}
let lastEventText   = '';     // last text sent to generate — used by Regenerate
let importedEvents  = [];     // events waiting for review
let contentType     = 'photo'; // text | photo | video

function setContentType(type, btn) {
  contentType = type;
  // Update all ct-toggle buttons on the page
  document.querySelectorAll('.ct-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.type === type);
  });
}

// ── Dashboard helpers ─────────────────────────────────────────────────────

function openEventFromDash(id, title, desc, dateStr, category) {
  activeEvent = { id, title, desc, date: dateStr, category };
  const panel = document.getElementById('genPanel');

  document.getElementById('genTitle').textContent   = title;
  document.getElementById('genDate').textContent    = formatDate(dateStr);
  document.getElementById('genDesc').textContent    = desc || '';
  const catEl = document.getElementById('genCategory');
  if (catEl) { catEl.textContent = capFirst(category); catEl.className = `gen-event-category ${category}`; }

  const resultsEl = document.getElementById('genResults');
  if (resultsEl) resultsEl.innerHTML = '';
  const toneEl = document.getElementById('genToneOverride');
  if (toneEl) toneEl.value = '';
  const genBtn = document.getElementById('btnGenerate');
  if (genBtn) { genBtn.disabled = false; genBtn.textContent = 'Generate drafts'; }

  // On dashboard: slide panel open. On calendar: panel is always open.
  if (panel) panel.classList.add('open');
}

function copyDraftById(draftId, content, btn) {
  _copyText(content);
  _flashCopied(btn, 'Copy');
}

async function markPosted(draftId, btn) {
  try {
    const resp = await fetch(`/api/drafts/${draftId}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'posted' }),
    });
    if (!resp.ok) throw new Error((await resp.json()).error);

    btn.textContent = '✓ Posted';
    btn.disabled = true;

    // Update copy row item (dashboard this-week view)
    const copyItem = btn.closest('.ec-copy-item');
    if (copyItem) {
      copyItem.classList.remove('draft_ready','needs_post','scheduled');
      copyItem.classList.add('posted');
    }

    // Update existing-draft card (calendar event detail view)
    const existingDraft = btn.closest('.gen-existing-draft');
    if (existingDraft) {
      const statusEl = existingDraft.querySelector('.gen-existing-status');
      if (statusEl) { statusEl.textContent = 'Posted ✓'; statusEl.className = 'gen-existing-status status-badge posted'; }
    }

    // Update dashboard compact status badge if present
    const badge = document.getElementById(`sb-${draftId}`);
    if (badge) { badge.textContent = 'Posted ✓'; badge.className = 'status-badge posted'; }

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

function _setPanelOpen(open) {
  const layout = document.querySelector('.cal-layout');
  if (layout) layout.classList.toggle('panel-open', open);
}

function showEmptyState() {
  ['genEmptyState','genEventState','genDayState'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = id === 'genEmptyState' ? '' : 'none';
  });
  _setPanelOpen(false);
  activeEvent = null;
}

// ── Day click ─────────────────────────────────────────────────────────────

function openDay(evt, cell) {
  const dateStr = cell.dataset.date;
  if (!dateStr) return;

  // Read events from data attributes on the cell (set by Jinja2)
  const evCount = parseInt(cell.dataset.evCount || '0');
  const cellEvents = [];
  for (let i = 0; i < evCount; i++) {
    cellEvents.push({
      id:       cell.dataset[`ev${i}Id`],
      title:    cell.dataset[`ev${i}Title`],
      desc:     cell.dataset[`ev${i}Desc`],
      category: cell.dataset[`ev${i}Category`],
      date:     dateStr,
    });
  }

  const friendlyDate = formatDate(dateStr);

  document.getElementById('genDayDate').textContent = friendlyDate;
  document.getElementById('genDaySub').textContent  = cellEvents.length
    ? `${cellEvents.length} event${cellEvents.length > 1 ? 's' : ''} — click one or describe something new below`
    : 'Nothing scheduled — let\'s create something';

  const container = document.getElementById('genDayEvents');
  container.innerHTML = '';
  const divider = document.getElementById('genDayDivider');

  if (cellEvents.length) {
    cellEvents.forEach(ev => {
      const row = document.createElement('div');
      row.className = 'gen-day-event-row';
      row.innerHTML = `
        <div class="gen-day-event-name">${escHtml(ev.title)}</div>
        <span class="gen-day-event-cat ${ev.category}">${capFirst(ev.category)}</span>`;
      row.onclick = () => openEventFromData(ev);
      container.appendChild(row);
    });
    divider.style.display = '';
  } else {
    divider.style.display = 'none';
  }

  const ta = document.getElementById('genDayFreeformText');
  if (ta) { ta.value = ''; ta.placeholder = `What's happening at BPA on ${friendlyDate.split(',')[0]}?`; }

  const results = document.getElementById('genDayFreeformResults');
  if (results) results.innerHTML = '';

  // Highlight selected day
  document.querySelectorAll('.cal-cell.selected').forEach(c => c.classList.remove('selected'));
  cell.classList.add('selected');

  ['genEmptyState','genEventState'].forEach(id => {
    const el = document.getElementById(id); if (el) el.style.display = 'none';
  });
  const dayState = document.getElementById('genDayState');
  if (dayState) dayState.style.display = '';
  _setPanelOpen(true);
}

// Open event from data object (used by day-click event list)
async function openEventFromData(ev) {
  // Build a fake chip-like element and reuse openEvent
  const fake = {
    dataset: { id: ev.id, title: ev.title, desc: ev.desc, date: ev.date, category: ev.category }
  };
  await openEvent(fake);
}

async function generateDayFreeform() {
  const text = document.getElementById('genDayFreeformText')?.value.trim();
  if (!text) { showToast('Describe what\'s happening first.'); return; }

  const platforms = Array.from(
    document.querySelectorAll('#dayFreeformPlatGrid .plat-card.active input')
  ).map(cb => cb.value);
  if (!platforms.length) { showToast('Select at least one platform.'); return; }

  const tone    = document.getElementById('genDayFreeformTone')?.value.trim();
  const btn     = document.getElementById('btnDayFreeformGenerate');
  const results = document.getElementById('genDayFreeformResults');

  btn.disabled = true; btn.textContent = 'Generating…';
  results.innerHTML = `<div class="gen-loading"><div class="gen-spinner"></div><div class="gen-loading-text">Writing in BPA's tone of voice…</div></div>`;

  try {
    lastEventText = text;
    const resp = await fetch('/api/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_text: text, tone_override: tone, platforms, content_type: contentType }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error);
    renderDraftCards(results, data);
  } catch (err) {
    results.innerHTML = `<div style="color:var(--red);padding:16px;font-size:13px;">${_friendlyError(err.message)}</div>`;
  }
  btn.disabled = false; btn.textContent = 'Generate posts';
}

// ── Event click (with existing drafts) ───────────────────────────────────

async function openEvent(el) {
  activeEvent = {
    id:       parseInt(el.dataset.id),
    title:    el.dataset.title,
    desc:     el.dataset.desc,
    date:     el.dataset.date,
    category: el.dataset.category,
  };

  document.getElementById('genTitle').textContent  = activeEvent.title;
  document.getElementById('genDate').textContent   = formatDate(activeEvent.date);
  document.getElementById('genDesc').textContent   = activeEvent.desc || '';
  const catEl = document.getElementById('genCategory');
  catEl.textContent = capFirst(activeEvent.category);
  catEl.className   = `gen-event-category ${activeEvent.category}`;

  document.getElementById('genResults').innerHTML   = '';
  document.getElementById('genToneOverride').value  = '';
  document.getElementById('btnGenerate').disabled   = false;
  document.getElementById('btnGenerate').textContent = 'Generate new drafts';

  // Switch to event state
  ['genEmptyState','genDayState'].forEach(id => {
    const el2 = document.getElementById(id); if (el2) el2.style.display = 'none';
  });
  const eventState = document.getElementById('genEventState');
  if (eventState) eventState.style.display = '';
  _setPanelOpen(true);

  // Fetch and show existing drafts
  const existingEl = document.getElementById('genExistingDrafts');
  if (existingEl) {
    existingEl.innerHTML = '<div class="gen-loading" style="padding:12px 0"><div class="gen-spinner" style="width:20px;height:20px;border-width:2px"></div></div>';
    try {
      const resp = await fetch(`/api/drafts/${activeEvent.id}`);
      const drafts = await resp.json();
      if (drafts.length) {
        renderExistingDrafts(existingEl, drafts);
        const lbl = document.getElementById('genNewDraftLabel');
        if (lbl) lbl.textContent = 'Generate new drafts';
      } else {
        existingEl.innerHTML = '';
      }
    } catch (_) { existingEl.innerHTML = ''; }
  }
}

function renderExistingDrafts(container, drafts) {
  const platformLabels = { facebook:'Facebook', instagram:'Instagram', linkedin:'LinkedIn', x:'X / Twitter', classdojo:'ClassDojo', email:'Newsletter' };
  const statusLabels   = { draft_ready:'Draft ready', posted:'Posted ✓', scheduled:'Scheduled', needs_post:'Needs post' };

  container.innerHTML = `<div class="gen-existing-header">Previously generated</div>`;

  // Group by platform, keep latest
  const byPlatform = {};
  drafts.forEach(d => { if (!byPlatform[d.platform]) byPlatform[d.platform] = d; });

  const order = ['facebook','instagram','linkedin','x','classdojo','email'];
  order.filter(p => byPlatform[p]).forEach(platform => {
    const d = byPlatform[platform];
    const div = document.createElement('div');
    div.className = 'gen-existing-draft';
    div.innerHTML = `
      <div class="gen-existing-top">
        <div class="gen-existing-platform">
          <span style="width:8px;height:8px;border-radius:50%;background:var(--dot-${platform}, #888);display:inline-block"></span>
          ${platformLabels[platform] || platform}
        </div>
        <span class="gen-existing-status status-badge ${d.status}">${statusLabels[d.status] || d.status}</span>
      </div>
      <div class="gen-existing-content">${escHtml(d.content)}</div>
      <div class="gen-existing-actions">
        <button class="btn-copy-small" onclick="copyDraftById(${d.id}, ${JSON.stringify(d.content)}, this)">Copy</button>
        ${d.status !== 'posted' ? `<button class="btn-mark-posted" onclick="markPosted(${d.id}, this)">✓ Mark posted</button>` : ''}
      </div>`;
    container.appendChild(div);
  });
}

function closePanel() {
  // Dashboard: remove .open slide-in class
  const panel = document.getElementById('genPanel');
  if (panel) panel.classList.remove('open');
  // Calendar: reset state divs + remove .panel-open from layout
  showEmptyState();
}

// ── Freeform generator (empty state) ─────────────────────────────────────

async function generateFreeform() {
  const text = document.getElementById('genFreeformText')?.value.trim();
  if (!text) { showToast('Describe what\'s happening first.'); return; }

  const platforms = Array.from(
    document.querySelectorAll('#freeformPlatGrid .plat-card.active input')
  ).map(cb => cb.value);
  if (!platforms.length) { showToast('Select at least one platform.'); return; }

  const tone    = document.getElementById('genFreeformTone')?.value.trim();
  const btn     = document.getElementById('btnFreeformGenerate');
  const results = document.getElementById('genFreeformResults');

  btn.disabled    = true;
  btn.textContent = 'Generating…';
  results.innerHTML = `<div class="gen-loading"><div class="gen-spinner"></div><div class="gen-loading-text">Writing in BPA's tone of voice…</div></div>`;

  try {
    const resp = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_text: text, tone_override: tone, platforms, content_type: contentType }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error);
    renderDraftCards(results, data);
  } catch (err) {
    results.innerHTML = `<div style="color:var(--red);padding:16px;font-size:13px;">${_friendlyError(err.message)}</div>`;
  }

  btn.disabled    = false;
  btn.textContent = 'Generate posts';
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
    if (activeEvent) lastEventText = `${activeEvent.title}. ${activeEvent.desc || ''}`.trim();

    const resp = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_id:      activeEvent.id,
        tone_override: tone,
        platforms,
        content_type:  contentType,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Generation failed');

    renderDraftCards(results, data);

  } catch (err) {
    results.innerHTML = `<div style="color:var(--red);padding:16px;font-size:13px;">${_friendlyError(err.message)}</div>`;
  }

  btn.disabled    = false;
  btn.textContent = 'Regenerate all';
}

// ── Shared draft card renderer ────────────────────────────────────────────

function renderDraftCards(container, data) {
  container.innerHTML = '';

  if (data.photo_brief) {
    const brief = document.createElement('div');
    brief.className = 'photo-brief-panel';
    brief.innerHTML = `<div class="photo-brief-header">📷 Photo brief — what to capture</div><div class="photo-brief-body">${escHtml(data.photo_brief)}</div>`;
    container.appendChild(brief);
  }

  const order = ['facebook', 'instagram', 'linkedin', 'x', 'classdojo', 'email'];
  const meta  = {
    facebook:  { label: 'Facebook',    canva: 'facebook_post' },
    instagram: { label: 'Instagram',   canva: 'instagram_post' },
    linkedin:  { label: 'LinkedIn',    canva: null },
    x:         { label: 'X / Twitter', canva: null },
    classdojo: { label: 'ClassDojo',   canva: null },
    email:     { label: 'Newsletter',  canva: null },
  };
  const bestTimes = data.best_times || {};

  order.filter(p => p in (data.drafts || {})).forEach(platform => {
    const content  = data.drafts[platform];
    const m        = meta[platform];
    const bt       = bestTimes[platform];
    const card     = document.createElement('div');
    card.className = 'draft-card';

    const canvaBtn = m.canva
      ? `<button class="btn-canva" onclick="designInCanva('${platform}', '${m.canva}', this)">🎨 Canva</button>`
      : '';
    const btHtml = bt
      ? `<div class="draft-best-time">⏰ ${bt.days} · ${bt.time} <span class="bt-note">${bt.note}</span></div>`
      : '';

    card.innerHTML = `
      <div class="draft-card-header">
        <div class="draft-platform-name plat-dot-${platform}">${m.label}</div>
        <div class="draft-card-actions">
          ${canvaBtn}
          <button class="btn-regen" onclick="regenSingle('${platform}', this)">Regenerate</button>
          <button class="btn-copy" onclick="copyDraft(this)">Copy</button>
        </div>
      </div>
      <div class="draft-content">${escHtml(content)}</div>
      ${btHtml}
      <div class="draft-char-count">${content.length} chars</div>`;
    container.appendChild(card);
  });
}

async function regenSingle(platform, btn) {
  const card    = btn.closest('.draft-card');
  const contentEl = card.querySelector('.draft-content');

  btn.textContent   = '…';
  btn.disabled      = true;
  contentEl.style.opacity = '0.4';

  // Use event_id if we have an active event, otherwise fall back to lastEventText
  const toneEl  = document.getElementById('genToneOverride') || document.getElementById('genFreeformTone');
  const tone    = toneEl ? toneEl.value.trim() : '';
  const payload = activeEvent
    ? { event_id: activeEvent.id, tone_override: tone, platforms: [platform], content_type: contentType }
    : { event_text: lastEventText, tone_override: tone, platforms: [platform], content_type: contentType };

  try {
    const resp = await fetch('/api/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Generation failed');
    const newContent = data.drafts[platform];
    contentEl.textContent = newContent;
    const cc = card.querySelector('.draft-char-count');
    if (cc) cc.textContent = `${newContent.length} chars`;
  } catch (err) {
    showToast('Regenerate failed: ' + err.message);
  }

  btn.textContent         = 'Regenerate';
  btn.disabled            = false;
  contentEl.style.opacity = '1';
}

// ── Copy to Clipboard ─────────────────────────────────────────────────────
// Uses execCommand fallback — required when accessed via LAN IP (non-HTTPS)

function _copyText(text) {
  // Always use execCommand — works on HTTP LAN connections unlike navigator.clipboard
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.cssText = 'position:fixed;top:0;left:0;width:2em;height:2em;opacity:0.01;border:none;outline:none;';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try { document.execCommand('copy'); } catch (_) {}
  document.body.removeChild(ta);
}

function _flashCopied(btn, originalLabel) {
  btn.textContent = '✓ Copied!';
  btn.classList.add('copied');
  setTimeout(() => { btn.textContent = originalLabel; btn.classList.remove('copied'); }, 2000);
}

function copyDraft(btn) {
  const content = btn.closest('.draft-card').querySelector('.draft-content').textContent;
  _copyText(content);
  _flashCopied(btn, 'Copy');
}

// ── Canva Design ──────────────────────────────────────────────────────────

function designInCanva(platform, canvaType, btn) {
  const content = btn.closest('.draft-card').querySelector('.draft-content').textContent;
  _copyText(content);

  const urls = {
    facebook_post:  'https://www.canva.com/create/facebook-posts/',
    instagram_post: 'https://www.canva.com/create/instagram-posts/',
    flyer:          'https://www.canva.com/create/flyers/',
  };
  const url = urls[canvaType] || 'https://www.canva.com/';

  // Use a real link element — avoids popup blockers
  const a = document.createElement('a');
  a.href = url; a.target = '_blank'; a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  showToast('Text copied — paste it into your Canva design!');
}

function designInCanvaByPlatform(platform, content) {
  _copyText(content);
  const urls = {
    facebook:  'https://www.canva.com/create/facebook-posts/',
    instagram: 'https://www.canva.com/create/instagram-posts/',
  };
  const a = document.createElement('a');
  a.href = urls[platform] || 'https://www.canva.com/';
  a.target = '_blank'; a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  showToast('Text copied — paste it into your Canva design!');
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
  const customInput = document.getElementById('evCategoryCustom');
  if (customInput) { customInput.style.display = 'none'; customInput.value = ''; }
}

function toggleCustomCategory(select) {
  const customInput = document.getElementById('evCategoryCustom');
  if (!customInput) return;
  customInput.style.display = select.value === 'custom' ? '' : 'none';
  if (select.value === 'custom') customInput.focus();
}

async function saveEvent() {
  const id    = document.getElementById('editEventId').value;
  const title = document.getElementById('evTitle').value.trim();
  const date  = document.getElementById('evDate').value;
  const selectEl = document.getElementById('evCategory');
  const cat   = selectEl.value === 'custom'
    ? (document.getElementById('evCategoryCustom')?.value.trim().toLowerCase().replace(/\s+/g,'_') || 'community')
    : selectEl.value;
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

function _friendlyError(msg) {
  if (msg && (msg.includes('429') || msg.includes('quota') || msg.includes('RESOURCE_EXHAUSTED')))
    return '⏱ Hit the API rate limit — please wait 10–15 seconds and try again.';
  if (msg && msg.includes('API key'))
    return '🔑 API key issue — check the GEMINI_API_KEY in your server config.';
  return `Something went wrong: ${msg}`;
}

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
