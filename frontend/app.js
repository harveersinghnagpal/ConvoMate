/* ─────────────────────────────────────────────
   ConvoMate – app.js
   WebSocket client + state manager + simulate mode
───────────────────────────────────────────── */

// ═══════════════════════════════════════════════
//  STATE
// ═══════════════════════════════════════════════
const state = {
  ws: null,
  connected: false,
  callActive: false,
  simulating: false,
  simIndex: 0,
  simTimer: null,
  startTime: null,
  durationTimer: null,
  segmentCount: 0,
  currentSentiment: 'Neutral',
  escalated: false,
};

// ═══════════════════════════════════════════════
//  SIMULATE SCRIPT  (demo without Twilio)
// ═══════════════════════════════════════════════
const SIM_SCRIPT = [
  { text: "Hi, I'd like to check on my order status.", sentiment: "Neutral", escalation: "No",  suggestion: "Greet the caller warmly and ask for the order number to pull up details quickly." },
  { text: "I placed the order three days ago and haven't received any shipping confirmation.", sentiment: "Neutral", escalation: "No",  suggestion: "Acknowledge the concern and assure the caller you'll look into the delay immediately." },
  { text: "I'm starting to get a bit frustrated. Can someone tell me what's going on?", sentiment: "Frustrated", escalation: "No",  suggestion: "Empathize: 'I completely understand your frustration. Let me check the tracking details right now.'" },
  { text: "This is unacceptable. I needed this package for an event this weekend!", sentiment: "Angry", escalation: "Yes", suggestion: "Apologize sincerely, take ownership, and offer an immediate resolution such as expedited re-ship or refund." },
  { text: "Nobody is giving me any straight answers. I've called three times already!", sentiment: "Angry", escalation: "Yes", suggestion: "De-escalate: 'I'm so sorry you've had to call multiple times. I will personally ensure this is resolved before we hang up.'" },
  { text: "Fine. What exactly can you actually do for me right now?", sentiment: "Frustrated", escalation: "Yes", suggestion: "Present two clear options: expedited shipping at no charge OR full refund — let the customer choose." },
  { text: "Okay, I'll take the expedited shipping. But I want a confirmation email immediately.", sentiment: "Neutral", escalation: "No",  suggestion: "Confirm the action in plain terms, provide a timeline, and send the email while on the call." },
  { text: "Alright. Thank you for finally sorting this out.", sentiment: "Neutral", escalation: "No",  suggestion: "Close warmly: thank them for their patience and invite feedback to show you value the relationship." },
  { text: "I appreciate it. Goodbye.", sentiment: "Happy", escalation: "No",  suggestion: "End on a positive note: 'Thank you for your business. Have a wonderful day!'" },
];

const SIM_DELAY_MS = 3800; // ms between each simulated turn

// ═══════════════════════════════════════════════
//  DOM REFS
// ═══════════════════════════════════════════════
const $ = id => document.getElementById(id);

const DOM = {
  statusPill:        $('status-pill'),
  statusDot:         $('status-dot'),
  statusText:        $('status-text'),

  btnSimStart:       $('btn-sim-start'),
  btnSimStop:        $('btn-sim-stop'),
  btnSimReset:       $('btn-sim-reset'),

  transcriptBody:    $('transcript-body'),
  transcriptEmpty:   $('transcript-empty'),

  metricSentiment:   $('metric-sentiment-value'),
  metricSentimentIc: $('metric-sentiment-icon'),
  cardSentiment:     $('card-sentiment'),

  metricEscalation:  $('metric-escalation-value'),
  metricEscalIcon:   $('metric-escalation-icon'),
  cardEscalation:    $('card-escalation'),

  metricDuration:    $('metric-duration-value'),
  metricSegments:    $('metric-segments-value'),

  suggestionText:    $('suggestion-text'),
  suggestionBadge:   $('suggestion-badge'),
  escalationBanner:  $('escalation-banner'),
  historyBody:       $('history-body'),

  demoBtnRow:        $('demo-btn-row'),
  demoProgressBar:   $('demo-progress-bar'),
  demoStatus:        $('demo-status'),
  toastContainer:    $('toast-container'),
  apiDocsLink:       $('btn-api-docs'),
};

// ═══════════════════════════════════════════════
//  WEBSOCKET
// ═══════════════════════════════════════════════
function getBackendBaseUrl() {
  if (window.location.protocol === 'file:') {
    return 'http://localhost:8000';
  }

  const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
  const hostname = window.location.hostname || 'localhost';
  const port = window.location.port || '8000';

  return `${protocol}//${hostname}:${port}`;
}

function getWebSocketUrl() {
  const baseUrl = new URL(getBackendBaseUrl());
  baseUrl.protocol = baseUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  baseUrl.pathname = '/ws';
  baseUrl.search = '';
  baseUrl.hash = '';
  return baseUrl.toString();
}

function connectWS() {
  try {
    state.ws = new WebSocket(getWebSocketUrl());

    state.ws.onopen  = () => { state.connected = true; toast('🔗 Connected to ConvoMate backend', 'info'); };
    state.ws.onclose = () => { state.connected = false; setTimeout(connectWS, 4000); };
    state.ws.onerror = () => { state.connected = false; };

    state.ws.onmessage = (ev) => {
      let data;
      try { data = JSON.parse(ev.data); } catch { return; }
      handleServerMessage(data);
    };
  } catch (e) {
    // Backend not running – silently retry (demo mode still works)
    setTimeout(connectWS, 5000);
  }
}

function handleServerMessage(data) {
  switch (data.type) {
    case 'transcript':
      appendTranscript(data.text, data.is_final);
      break;
    case 'analysis':
      updateAnalysis(data);
      break;
    case 'call_start':
      startCallUI();
      break;
    case 'call_end':
      endCallUI();
      break;
    case 'call_error':
      toast(data.message || 'Call stream failed', 'info');
      endCallUI();
      break;
    case 'ping':
      // keep-alive, ignore
      break;
  }
}

// ═══════════════════════════════════════════════
//  TRANSCRIPT
// ═══════════════════════════════════════════════
let _lastPartialEl = null;

function appendTranscript(text, isFinal) {
  if (!text) return;

  // Hide empty state
  if (DOM.transcriptEmpty) DOM.transcriptEmpty.style.display = 'none';

  if (!isFinal) {
    // Update or create partial line
    if (_lastPartialEl) {
      _lastPartialEl.querySelector('.line-text').textContent = text;
    } else {
      _lastPartialEl = createTranscriptLine(text, true);
      DOM.transcriptBody.appendChild(_lastPartialEl);
    }
  } else {
    // Finalise
    if (_lastPartialEl) {
      _lastPartialEl.querySelector('.line-text').classList.remove('partial');
      _lastPartialEl.querySelector('.line-text').textContent = text;
      _lastPartialEl = null;
    } else {
      DOM.transcriptBody.appendChild(createTranscriptLine(text, false));
    }
    state.segmentCount++;
    DOM.metricSegments.textContent = state.segmentCount;
  }

  DOM.transcriptBody.scrollTop = DOM.transcriptBody.scrollHeight;
}

function createTranscriptLine(text, partial) {
  const div = document.createElement('div');
  div.className = 'transcript-line';

  const now = new Date();
  const timeStr = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;

  div.innerHTML = `
    <span class="line-time">${timeStr}</span>
    <span class="line-text${partial ? ' partial' : ''}">${escapeHtml(text)}</span>
  `;
  return div;
}

function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ═══════════════════════════════════════════════
//  ANALYSIS UPDATE
// ═══════════════════════════════════════════════
const SENTIMENT_META = {
  Happy:       { icon: '😊', cls: 'sentiment-happy',      badgeCls: 'badge-happy' },
  Neutral:     { icon: '😐', cls: 'sentiment-neutral',    badgeCls: 'badge-neutral' },
  Frustrated:  { icon: '😤', cls: 'sentiment-frustrated', badgeCls: 'badge-frustrated' },
  Angry:       { icon: '😡', cls: 'sentiment-angry',      badgeCls: 'badge-angry' },
};

function updateAnalysis({ sentiment, escalation, suggestion, transcript }) {
  sentiment  = sentiment  || 'Neutral';
  escalation = escalation || 'No';
  suggestion = suggestion || '';

  state.currentSentiment = sentiment;
  state.escalated = escalation === 'Yes';

  const meta = SENTIMENT_META[sentiment] || SENTIMENT_META.Neutral;

  // ── Sentiment metric card
  DOM.metricSentimentIc.textContent = meta.icon;
  DOM.metricSentiment.textContent   = sentiment;

  // Remove old sentiment classes
  DOM.cardSentiment.className = 'metric-card ' + meta.cls;

  // ── Escalation card
  DOM.metricEscalIcon.textContent   = state.escalated ? '🚨' : '✅';
  DOM.metricEscalation.textContent  = escalation;
  DOM.cardEscalation.className      = 'metric-card' + (state.escalated ? ' escalation-yes' : '');

  // ── Escalation banner
  DOM.escalationBanner.classList.toggle('hidden', !state.escalated);

  // ── Suggestion
  DOM.suggestionText.classList.remove('thinking');
  DOM.suggestionText.innerHTML = suggestion
    ? `<span>${escapeHtml(suggestion)}</span>`
    : `<span class="suggestion-placeholder">Waiting for caller input…</span>`;

  // ── History log
  addHistoryItem(transcript, sentiment, meta.badgeCls);
}

function addHistoryItem(text, sentiment, badgeCls) {
  if (!text) return;
  const item = document.createElement('div');
  item.className = 'history-item';
  item.innerHTML = `
    <span class="history-badge ${badgeCls}">${sentiment}</span>
    <span class="history-snippet">${escapeHtml(text)}</span>
  `;
  DOM.historyBody.appendChild(item);
  DOM.historyBody.scrollTop = DOM.historyBody.scrollHeight;
}

// ═══════════════════════════════════════════════
//  CALL UI STATE
// ═══════════════════════════════════════════════
function startCallUI() {
  state.callActive = true;
  state.startTime  = Date.now();
  state.segmentCount = 0;
  DOM.metricSegments.textContent = '0';

  DOM.statusPill.classList.add('active');
  DOM.statusText.textContent = 'Call Active';

  // Duration timer
  clearInterval(state.durationTimer);
  state.durationTimer = setInterval(() => {
    const s = Math.floor((Date.now() - state.startTime) / 1000);
    const m = Math.floor(s / 60);
    DOM.metricDuration.textContent = `${String(m).padStart(2,'0')}:${String(s % 60).padStart(2,'0')}`;
  }, 1000);
}

function endCallUI() {
  state.callActive = false;
  clearInterval(state.durationTimer);
  DOM.statusPill.classList.remove('active');
  DOM.statusText.textContent = 'Call Ended';
  setTimeout(() => { DOM.statusText.textContent = 'No Active Call'; }, 3000);
}

// ═══════════════════════════════════════════════
//  SIMULATE MODE
// ═══════════════════════════════════════════════
function startSimulation() {
  if (state.simulating) return;
  state.simulating = true;
  state.simIndex = 0;

  // Reset UI
  resetUI();
  startCallUI();
  DOM.btnSimStart.disabled = true;
  DOM.btnSimStop.disabled  = false;
  DOM.demoStatus.textContent = 'Simulating live call…';
  DOM.suggestionText.classList.add('thinking');
  DOM.suggestionText.innerHTML = '<span class="suggestion-placeholder">Analysing…</span>';

  toast('▶ Simulate mode started — watch the dashboard update live', 'info');
  runSimStep();
}

function runSimStep() {
  if (!state.simulating || state.simIndex >= SIM_SCRIPT.length) {
    stopSimulation();
    return;
  }

  const step = SIM_SCRIPT[state.simIndex];
  const progress = ((state.simIndex + 1) / SIM_SCRIPT.length) * 100;
  DOM.demoProgressBar.style.width = `${progress}%`;
  DOM.demoStatus.textContent = `Turn ${state.simIndex + 1} of ${SIM_SCRIPT.length}`;

  // Show as partial first, then finalise with analysis
  appendTranscript(step.text, false);
  setTimeout(() => {
    appendTranscript(step.text, true);
    updateAnalysis({
      transcript: step.text,
      sentiment:  step.sentiment,
      escalation: step.escalation,
      suggestion: step.suggestion,
    });
    DOM.suggestionText.classList.remove('thinking');
  }, 900);

  state.simIndex++;
  state.simTimer = setTimeout(runSimStep, SIM_DELAY_MS);
}

function stopSimulation() {
  state.simulating = false;
  clearTimeout(state.simTimer);
  DOM.btnSimStart.disabled = false;
  DOM.btnSimStop.disabled  = true;
  DOM.demoProgressBar.style.width = '100%';
  DOM.demoStatus.textContent = 'Simulation complete';
  endCallUI();
  toast('⏹ Simulation ended', 'info');
}

function resetUI() {
  // Clear transcript
  DOM.transcriptBody.innerHTML = '';
  DOM.transcriptEmpty && (DOM.transcriptEmpty.style.display = '');
  // Clear history
  DOM.historyBody.innerHTML = '';
  // Reset metrics
  DOM.metricSentiment.textContent  = 'Neutral';
  DOM.metricSentimentIc.textContent = '😐';
  DOM.cardSentiment.className       = 'metric-card';
  DOM.metricEscalation.textContent  = 'No';
  DOM.metricEscalIcon.textContent   = '✅';
  DOM.cardEscalation.className      = 'metric-card';
  DOM.metricDuration.textContent    = '00:00';
  DOM.metricSegments.textContent    = '0';
  DOM.escalationBanner.classList.add('hidden');
  DOM.suggestionText.innerHTML = '<span class="suggestion-placeholder">Waiting for caller input…</span>';
  DOM.demoProgressBar.style.width = '0%';
  DOM.demoStatus.textContent = 'Ready';
  state.segmentCount  = 0;
  state.escalated     = false;
  state.currentSentiment = 'Neutral';
  _lastPartialEl = null;
}

// ═══════════════════════════════════════════════
//  TOAST
// ═══════════════════════════════════════════════
function toast(message, _type = 'info') {
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = message;
  DOM.toastContainer.appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

// ═══════════════════════════════════════════════
//  EVENT LISTENERS
// ═══════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  DOM.btnSimStart.addEventListener('click', startSimulation);
  DOM.btnSimStop.addEventListener('click',  stopSimulation);
  DOM.btnSimReset.addEventListener('click', () => { stopSimulation(); resetUI(); });

  if (DOM.apiDocsLink) {
    DOM.apiDocsLink.href = `${getBackendBaseUrl()}/docs`;
  }

  // Attempt backend WS connection (optional, degrades gracefully)
  connectWS();

  // Initial state
  DOM.btnSimStop.disabled = true;
  DOM.escalationBanner.classList.add('hidden');
  toast('👋 Welcome to ConvoMate! Click "Simulate Call" to see it in action.', 'info');
});
