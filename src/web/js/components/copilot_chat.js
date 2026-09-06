/**
 * AERO SRE Copilot Chat Drawer Component
 * Incident-grounded SRE chat assistant with strict separation of Evidence, Inference, and Recommendations.
 */

import { api } from '../api.js';
import { store } from '../state.js';

const QUICK_PROMPTS = [
  'What caused this incident?',
  'Show the strongest evidence.',
  'What changed before the incident?',
  'What should I verify before remediation?',
  'What evidence is still missing?'
];

/**
 * Initialize Copilot Drawer DOM and event listeners.
 */
export function initCopilotDrawer() {
  let backdrop = document.getElementById('copilot-backdrop');
  let drawer = document.getElementById('copilot-drawer');

  if (!backdrop) {
    backdrop = document.createElement('div');
    backdrop.id = 'copilot-backdrop';
    backdrop.className = 'copilot-backdrop';
    document.body.appendChild(backdrop);
    backdrop.addEventListener('click', closeCopilotDrawer);
  }

  if (!drawer) {
    drawer = document.createElement('div');
    drawer.id = 'copilot-drawer';
    drawer.className = 'copilot-drawer';
    document.body.appendChild(drawer);
  }

  renderDrawerStructure(drawer);
}

const MIN_DRAWER_WIDTH = 380;
const DEFAULT_DRAWER_WIDTH = 500;
const EXPANDED_DRAWER_WIDTH = 860;
let currentDrawerWidth = DEFAULT_DRAWER_WIDTH;

/**
 * Render the static skeleton of the Copilot drawer.
 */
function renderDrawerStructure(drawer) {
  const state = store.getState();
  const scenarioKey = state.activeScenarioKey || 'oom_kill';
  const scenarioData = state.activeScenarioData;
  const svc = scenarioData?.incident?.metadata?.service_name || scenarioKey;

  // Apply current width if custom
  if (currentDrawerWidth && currentDrawerWidth !== DEFAULT_DRAWER_WIDTH) {
    drawer.style.width = `${currentDrawerWidth}px`;
  }

  drawer.innerHTML = `
    <!-- Left Boundary Drag Handle for Resizing -->
    <div class="copilot-resize-handle" id="copilot-resize-handle" title="Drag to resize drawer" aria-label="Resize drawer"></div>

    <!-- Header -->
    <div class="copilot-header">
      <div class="copilot-header-title-group">
        <div class="copilot-eyebrow">
          <span>⚡ AERO SRE COPILOT</span>
          <span class="badge badge-healthy font-mono" style="font-size: 9.5px;">Grounded</span>
        </div>
        <div class="copilot-title">Incident Investigation Assistant</div>
      </div>
      <div class="copilot-header-actions">
        <button type="button" class="copilot-icon-btn" id="btn-copilot-expand" title="Expand / Restore width (Toggle)">
          ⤢
        </button>
        <button type="button" class="copilot-icon-btn" id="btn-copilot-clear" title="Clear conversation history">
          🗑️
        </button>
        <button type="button" class="copilot-icon-btn" id="btn-copilot-close" title="Close Copilot drawer (Esc)">
          ✕
        </button>
      </div>
    </div>

    <!-- Active Scenario Context Bar -->
    <div class="copilot-context-bar">
      <div class="copilot-context-service font-mono">
        <span>Active Incident:</span>
        <span style="color: var(--accent-color);">${escapeHtml(svc)}</span>
        <span style="color: var(--text-muted); font-size: 10px;">(${escapeHtml(scenarioKey)})</span>
      </div>
      <span class="badge badge-info" style="font-size: 10px;">Advisory Only</span>
    </div>

    <!-- Quick Suggested Prompts -->
    <div class="copilot-quick-prompts" id="copilot-quick-prompts">
      ${QUICK_PROMPTS.map((p) => `
        <button type="button" class="prompt-pill" data-prompt="${escapeHtml(p)}">${escapeHtml(p)}</button>
      `).join('')}
    </div>

    <!-- Messages Container -->
    <div class="copilot-messages-container" id="copilot-messages-container">
      <!-- Conversation injected here -->
    </div>

    <!-- Input Area -->
    <div class="copilot-input-area">
      <div class="copilot-input-wrapper">
        <textarea
          id="copilot-textarea"
          class="copilot-textarea"
          placeholder="Ask AERO about root cause, evidence, or next steps..."
          rows="1"
          aria-label="SRE Copilot query input"
        ></textarea>
        <button type="button" class="btn-copilot-send" id="btn-copilot-send" title="Send question">
          <span>Ask</span>
          <span>⚡</span>
        </button>
      </div>
      <div class="copilot-input-hint">
        <span>Grounded strictly in active telemetry</span>
        <span>Enter to send · Shift+Enter for new line</span>
      </div>
    </div>
  `;

  // Bind Event Listeners
  const btnClose = drawer.querySelector('#btn-copilot-close');
  if (btnClose) btnClose.addEventListener('click', closeCopilotDrawer);

  const btnClear = drawer.querySelector('#btn-copilot-clear');
  if (btnClear) {
    btnClear.addEventListener('click', () => {
      store.setState({ copilotMessages: [] });
      renderMessages();
    });
  }

  const btnExpand = drawer.querySelector('#btn-copilot-expand');
  if (btnExpand) {
    btnExpand.addEventListener('click', () => {
      const maxW = Math.min(EXPANDED_DRAWER_WIDTH, Math.floor(window.innerWidth * 0.90));
      if (currentDrawerWidth >= maxW - 30) {
        // Restore to default
        currentDrawerWidth = DEFAULT_DRAWER_WIDTH;
      } else {
        // Expand
        currentDrawerWidth = maxW;
      }
      drawer.style.width = `${currentDrawerWidth}px`;
    });
  }

  // Setup Drag Resizing
  setupDrawerResize(drawer);

  const quickPrompts = drawer.querySelectorAll('.prompt-pill');
  quickPrompts.forEach((btn) => {
    btn.addEventListener('click', () => {
      const text = btn.getAttribute('data-prompt');
      if (text) submitUserMessage(text);
    });
  });

  const textarea = drawer.querySelector('#copilot-textarea');
  const btnSend = drawer.querySelector('#btn-copilot-send');

  if (textarea && btnSend) {
    btnSend.addEventListener('click', () => {
      const text = textarea.value.trim();
      if (text) {
        textarea.value = '';
        submitUserMessage(text);
      }
    });

    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const text = textarea.value.trim();
        if (text) {
          textarea.value = '';
          submitUserMessage(text);
        }
      }
    });
  }

  // Initial render of messages
  renderMessages();
}

/**
 * Setup smooth horizontal drag resizing on the left boundary of the drawer.
 */
function setupDrawerResize(drawer) {
  const handle = drawer.querySelector('#copilot-resize-handle');
  if (!handle) return;

  let isDragging = false;
  let startX = 0;
  let startWidth = DEFAULT_DRAWER_WIDTH;

  const onPointerDown = (e) => {
    e.preventDefault();
    isDragging = true;
    startX = e.clientX;
    startWidth = drawer.getBoundingClientRect().width;

    handle.classList.add('active');
    drawer.classList.add('is-resizing');
    document.body.classList.add('copilot-resizing');

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    window.addEventListener('pointercancel', onPointerUp);
  };

  const onPointerMove = (e) => {
    if (!isDragging) return;
    const delta = startX - e.clientX;
    const maxAllowed = Math.min(1150, Math.floor(window.innerWidth * 0.92));
    const minAllowed = Math.min(MIN_DRAWER_WIDTH, Math.floor(window.innerWidth * 0.85));
    const newWidth = Math.max(minAllowed, Math.min(maxAllowed, Math.round(startWidth + delta)));
    
    currentDrawerWidth = newWidth;
    drawer.style.width = `${newWidth}px`;
  };

  const onPointerUp = () => {
    if (!isDragging) return;
    isDragging = false;
    handle.classList.remove('active');
    drawer.classList.remove('is-resizing');
    document.body.classList.remove('copilot-resizing');

    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  handle.addEventListener('pointerdown', onPointerDown);
}

/**
 * Toggle open / close drawer state.
 */
export function toggleCopilotDrawer() {
  const state = store.getState();
  if (state.copilotOpen) {
    closeCopilotDrawer();
  } else {
    openCopilotDrawer();
  }
}

/**
 * Open Copilot Drawer.
 */
export function openCopilotDrawer() {
  initCopilotDrawer();
  const backdrop = document.getElementById('copilot-backdrop');
  const drawer = document.getElementById('copilot-drawer');
  if (backdrop) backdrop.classList.add('open');
  if (drawer) {
    drawer.classList.add('open');
    renderDrawerStructure(drawer);
    const textarea = drawer.querySelector('#copilot-textarea');
    if (textarea) setTimeout(() => textarea.focus(), 150);
  }
  store.setState({ copilotOpen: true });
}

/**
 * Close Copilot Drawer.
 */
export function closeCopilotDrawer() {
  const backdrop = document.getElementById('copilot-backdrop');
  const drawer = document.getElementById('copilot-drawer');
  if (backdrop) backdrop.classList.remove('open');
  if (drawer) drawer.classList.remove('open');
  store.setState({ copilotOpen: false });
}

/**
 * Reset Copilot chat state upon scenario switch.
 */
export function resetCopilotChat() {
  store.setState({
    copilotMessages: [],
    copilotLoading: false,
    copilotError: null
  });
  const drawer = document.getElementById('copilot-drawer');
  if (drawer) {
    renderDrawerStructure(drawer);
  }
}

/**
 * Submit user message and fetch grounded response from backend.
 */
async function submitUserMessage(userMessage) {
  if (!userMessage || !userMessage.trim()) return;

  const state = store.getState();
  const scenarioKey = state.activeScenarioKey || 'oom_kill';

  // Append user message to history
  const updatedMessages = [
    ...(state.copilotMessages || []),
    { role: 'user', content: userMessage.trim(), timestamp: new Date() }
  ];

  store.setState({
    copilotMessages: updatedMessages,
    copilotLoading: true,
    copilotError: null
  });
  renderMessages();

  try {
    const response = await api.sendChatMessage(scenarioKey, userMessage.trim());
    const finalMessages = [
      ...store.getState().copilotMessages,
      { role: 'aero', data: response, timestamp: new Date() }
    ];
    store.setState({
      copilotMessages: finalMessages,
      copilotLoading: false
    });
  } catch (err) {
    console.error('Copilot request failed:', err);
    store.setState({
      copilotLoading: false,
      copilotError: err.message || 'Failed to reach SRE Copilot service.'
    });
  }
  renderMessages();
}

/**
 * Render all conversation messages inside drawer container.
 */
function renderMessages() {
  const container = document.getElementById('copilot-messages-container');
  if (!container) return;

  const state = store.getState();
  const messages = state.copilotMessages || [];
  const isLoading = state.copilotLoading;
  const error = state.copilotError;

  if (messages.length === 0 && !isLoading && !error) {
    container.innerHTML = `
      <div class="copilot-welcome-card">
        <div class="copilot-welcome-icon">💬</div>
        <div class="copilot-welcome-title">Ask AERO SRE Copilot</div>
        <p class="copilot-welcome-desc">
          Get real-time causal answers grounded in the active telemetry. Answers separate 
          <strong>Observed Evidence</strong>, <strong>Derived Inferences</strong>, and <strong>Recommendations</strong>.
        </p>
        <div style="font-size: 11px; color: var(--text-muted);">
          Select a quick suggested prompt above or type your inquiry below.
        </div>
      </div>
    `;
    return;
  }

  let html = '';
  for (const msg of messages) {
    if (msg.role === 'user') {
      html += `
        <div class="chat-msg-user">
          ${escapeHtml(msg.content)}
        </div>
      `;
    } else if (msg.role === 'aero' && msg.data) {
      const resp = msg.data;
      const evidence = resp.evidence || [];
      const inferences = resp.inferences || [];
      const recommendations = resp.recommendations || [];
      const isGrounded = resp.grounded !== false;

      html += `
        <div class="chat-msg-aero">
          <!-- Card Header -->
          <div class="aero-msg-header">
            <div class="aero-msg-brand">
              <span>⚡</span>
              <span>AERO REASONING</span>
            </div>
            <span class="badge ${isGrounded ? 'badge-healthy' : 'badge-warning'}" style="font-size: 9.5px;">
              ${isGrounded ? '✓ Verified Grounded' : '⚠️ Partial Evidence'}
            </span>
          </div>

          <!-- Main Answer Markdown -->
          <div class="aero-msg-answer">
            ${escapeHtml(resp.answer)}
          </div>

          <!-- 1. Observed Evidence -->
          ${evidence.length > 0 ? `
            <div class="copilot-evidence-block">
              <div class="block-title-evidence">
                <span>🔍</span>
                <span>Observed Telemetry Evidence</span>
              </div>
              <div style="display: flex; flex-direction: column; gap: 6px;">
                ${evidence.map((item) => `
                  <div class="evidence-item-row">
                    <span class="evidence-type-badge">${escapeHtml(item.signal_type)}</span>
                    <div>
                      <strong>${escapeHtml(item.source)}:</strong> ${escapeHtml(item.description)}
                      ${item.log_snippet ? `<div class="font-mono" style="font-size: 11px; color: #38bdf8; margin-top: 2px;">↳ Log: "${escapeHtml(item.log_snippet)}"</div>` : ''}
                      ${item.metric_name ? `<div class="font-mono" style="font-size: 11px; color: #a78bfa; margin-top: 2px;">↳ Metric: ${escapeHtml(item.metric_name)}</div>` : ''}
                    </div>
                  </div>
                `).join('')}
              </div>
            </div>
          ` : ''}

          <!-- 2. Derived Inference -->
          ${inferences.length > 0 ? `
            <div class="copilot-inference-block">
              <div class="block-title-inference">
                <span>💡</span>
                <span>Derived Inference & Deduction</span>
              </div>
              <div style="display: flex; flex-direction: column; gap: 4px;">
                ${inferences.map((inf) => `
                  <div class="inference-item-row">
                    <span style="color: #fbbf24;">•</span>
                    <div>${escapeHtml(inf)}</div>
                  </div>
                `).join('')}
              </div>
            </div>
          ` : ''}

          <!-- 3. SRE Recommendations -->
          ${recommendations.length > 0 ? `
            <div class="copilot-recommendation-block">
              <div class="block-title-recommendation">
                <span>🛡️</span>
                <span>SRE Recommendation (Advisory Only)</span>
              </div>
              <div style="display: flex; flex-direction: column; gap: 4px;">
                ${recommendations.map((rec) => `
                  <div class="recommendation-item-row">
                    <span style="color: #34d399;">✓</span>
                    <div>${escapeHtml(rec)}</div>
                  </div>
                `).join('')}
              </div>
            </div>
          ` : ''}

          <!-- Grounding Audit Footer -->
          <div class="aero-grounding-audit font-mono">
            <span>Confidence: ${(resp.confidence * 100).toFixed(0)}%</span>
            <span>Scenario: ${escapeHtml(resp.scenario_key || 'active')}</span>
          </div>
        </div>
      `;
    }
  }

  // Loading indicator
  if (isLoading) {
    html += `
      <div class="copilot-loading-card">
        <div class="copilot-spinner"></div>
        <div>AERO is reasoning across active scenario telemetry...</div>
      </div>
    `;
  }

  // Error card
  if (error) {
    html += `
      <div class="alert-banner alert-banner-critical" style="font-size: 12px; margin: 4px 0;">
        <span>❌ ${escapeHtml(error)}</span>
      </div>
    `;
  }

  container.innerHTML = html;
  // Scroll to bottom
  container.scrollTop = container.scrollHeight;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
