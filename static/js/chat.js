/**
 * Confluence AI Assistant & Telemetry Inspector Module
 * Controls the slide-over chat drawer, grounded streaming/formatting, alert banners, and raw telemetry inspection.
 */

let groundingPayloadCache = {};
let payloadCounter = 0;

// -------------------------------------------------------------------------
// Chat Drawer Toggle Controls
// -------------------------------------------------------------------------
function openChatDrawer(initialQuery) {
  const drawer = document.getElementById('chatDrawer');
  const backdrop = document.getElementById('drawerBackdrop');
  if (drawer) drawer.classList.add('active');
  if (backdrop) backdrop.classList.add('active');
  document.body.style.overflow = 'hidden';

  const input = document.getElementById('queryInput');
  if (initialQuery) {
    submitQuery(initialQuery);
  } else if (input) {
    setTimeout(() => input.focus(), 250);
  }
}

function closeChatDrawer() {
  const drawer = document.getElementById('chatDrawer');
  const backdrop = document.getElementById('drawerBackdrop');
  if (drawer) drawer.classList.remove('active');
  if (backdrop) backdrop.classList.remove('active');
  document.body.style.overflow = '';
}

// -------------------------------------------------------------------------
// Text Formatting Utilities
// -------------------------------------------------------------------------
function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatMarkdown(text) {
  if (!text) return '';
  let safe = escapeHtml(text);

  // Bold text
  safe = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

  // Bullet lists & paragraphs
  const lines = safe.split('\n');
  let inList = false;
  let out = '';

  for (let line of lines) {
    let trimmed = line.trim();
    if (trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
      if (!inList) {
        out += '<ul>';
        inList = true;
      }
      out += `<li>${trimmed.substring(2)}</li>`;
    } else {
      if (inList) {
        out += '</ul>';
        inList = false;
      }
      if (trimmed.length > 0) {
        out += `<p>${line}</p>`;
      }
    }
  }
  if (inList) out += '</ul>';
  return out;
}

// -------------------------------------------------------------------------
// Message Stream Rendering
// -------------------------------------------------------------------------
function appendUserMessage(text) {
  const stream = document.getElementById('chatStream');
  if (!stream) return;

  const row = document.createElement('div');
  row.className = 'message-row user';
  row.innerHTML = `
    <div class="message-bubble">
      <p>${escapeHtml(text)}</p>
    </div>
    <div class="avatar user">You</div>
  `;
  stream.appendChild(row);
  scrollToDrawerBottom();
}

function appendAssistantMessage(data) {
  const stream = document.getElementById('chatStream');
  if (!stream) return;

  const row = document.createElement('div');
  row.className = 'message-row assistant';

  let alertHtml = '';
  if (data.active_alerts && data.active_alerts.length > 0) {
    for (const alert of data.active_alerts) {
      const isCritical = (alert.severity || '').toLowerCase() === 'critical';
      const severityTag = (alert.severity || 'WARNING').toUpperCase();
      const title = alert.title || alert.id || 'Hazard Alert';
      const msg = alert.message || alert.description || '';

      alertHtml += `
        <div class="alert-banner ${isCritical ? 'critical' : 'warning'}">
          <svg viewBox="0 0 24 24"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>
          <div>
            <span class="alert-severity-tag">${escapeHtml(severityTag)} ALERT</span>
            <div class="alert-title">${escapeHtml(title)}</div>
            <div style="font-size:0.8rem; margin-top:2px;">${escapeHtml(msg)}</div>
          </div>
        </div>
      `;
    }
  }

  let footerHtml = '';
  if (data.location_matched && data.grounding_data) {
    payloadCounter++;
    const payloadKey = `payload_${payloadCounter}`;
    groundingPayloadCache[payloadKey] = {
      location: data.location_matched,
      coordinates: data.coordinates,
      alerts: data.active_alerts,
      snapshot: data.grounding_data
    };

    footerHtml = `
      <div class="message-footer">
        <span style="display:inline-flex; align-items:center; gap:4px; color:var(--color-primary-hover); font-weight:600;">
          <svg style="width:12px; height:12px; fill:currentColor;" viewBox="0 0 24 24">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
          </svg>
          ${escapeHtml(data.location_matched)}
        </span>
        <button type="button" class="inspect-btn" onclick="openInspector('${payloadKey}')">
          <span>View Grounding Context</span>
        </button>
      </div>
    `;
  }

  row.innerHTML = `
    <div class="avatar assistant">
      <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
    </div>
    <div class="message-bubble">
      ${alertHtml}
      <div>${formatMarkdown(data.answer)}</div>
      ${footerHtml}
    </div>
  `;

  stream.appendChild(row);
  scrollToDrawerBottom();
}

function scrollToDrawerBottom() {
  const drawerBody = document.getElementById('drawerBody');
  if (drawerBody) {
    drawerBody.scrollTo({ top: drawerBody.scrollHeight, behavior: 'smooth' });
  }
}

// -------------------------------------------------------------------------
// Query Execution & API Integration
// -------------------------------------------------------------------------
async function submitQuery(query) {
  if (!query || !query.trim()) return;

  const input = document.getElementById('queryInput');
  const sendBtn = document.getElementById('sendBtn');
  const loading = document.getElementById('loadingRow');

  if (input) {
    input.value = '';
    input.disabled = true;
  }
  if (sendBtn) sendBtn.disabled = true;

  appendUserMessage(query);
  if (loading) loading.style.display = 'flex';
  scrollToDrawerBottom();

  try {
    const resp = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: query })
    });

    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || errData.message || `Server responded with HTTP ${resp.status}`);
    }

    const data = await resp.json();
    if (loading) loading.style.display = 'none';
    appendAssistantMessage(data);
  } catch (err) {
    if (loading) loading.style.display = 'none';
    appendAssistantMessage({
      answer: `**Request Error:** ${err.message}. Please ensure the Confluence API is active.`,
      active_alerts: [],
      location_matched: null,
      grounding_data: null
    });
  } finally {
    if (input) {
      input.disabled = false;
      input.focus();
    }
    if (sendBtn) sendBtn.disabled = false;
  }
}

function handleFormSubmit(e) {
  e.preventDefault();
  const input = document.getElementById('queryInput');
  if (input && input.value) {
    submitQuery(input.value);
  }
}

// -------------------------------------------------------------------------
// Grounding Context Inspector Modal
// -------------------------------------------------------------------------
function openInspector(payloadKey) {
  const item = groundingPayloadCache[payloadKey];
  if (!item) return;

  const modal = document.getElementById('inspectorModal');
  const summary = document.getElementById('modalSummary');
  const viewer = document.getElementById('modalJsonViewer');

  if (summary) {
    const alertCount = (item.alerts || []).length;
    summary.innerHTML = `
      <div>Station: <strong>${escapeHtml(item.location)}</strong></div>
      <div>Coordinates: <strong>${item.coordinates ? item.coordinates.lat + '° N, ' + item.coordinates.lon + '° E' : 'N/A'}</strong></div>
      <div>Active Alerts: <strong>${alertCount}</strong></div>
      <div>Sources: <strong>7 Real-Time Confluent Feeds</strong></div>
    `;
  }

  if (viewer) {
    viewer.textContent = JSON.stringify(item.snapshot, null, 2);
  }

  if (modal) modal.classList.add('active');
}

function closeInspector() {
  const modal = document.getElementById('inspectorModal');
  if (modal) modal.classList.remove('active');
}

function closeInspectorOnBackdrop(e) {
  if (e.target && e.target.id === 'inspectorModal') {
    closeInspector();
  }
}

function copyModalJson() {
  const viewer = document.getElementById('modalJsonViewer');
  if (!viewer) return;
  const text = viewer.textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector('.copy-raw-btn');
    if (btn) {
      const orig = btn.textContent;
      btn.textContent = 'Copied to Clipboard';
      setTimeout(() => { btn.textContent = orig; }, 1500);
    }
  });
}
