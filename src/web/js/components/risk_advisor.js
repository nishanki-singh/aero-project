/**
 * AERO Pre-Deployment Risk Advisor Component
 * Evaluates proposed deployment/configuration changes before production release.
 * 3-Tier separation: Observed Change Facts -> Derived Risk Assessment -> Recommended Preventive Actions.
 */

import { api } from '../api.js';
import { store } from '../state.js';

const PRESET_CHANGES = {
  uncapped_jvm: {
    label: 'Uncapped JVM Heap',
    service: 'worker-service',
    change_type: 'deployment',
    description: 'Bump JVM worker pool image to latest without memory limits and with debug logging enabled.',
    environment: 'production',
    parameters: {
      image_tag: 'latest',
      debug_mode: true,
      log_level: 'DEBUG',
      memory_request_mb: 1024
    }
  },
  db_pool_starvation: {
    label: 'DB Pool Starvation',
    service: 'order-service',
    change_type: 'config',
    description: 'Reduce database pool max size to 2 connections with 45s downstream RPC timeout.',
    environment: 'production',
    parameters: {
      pool_max_size: 2,
      timeout_ms: 45000,
      downstream_timeout_ms: 45000,
      upstream_timeout_ms: 10000
    }
  },
  missing_readiness: {
    label: 'Missing Readiness Probe',
    service: 'checkout-service',
    change_type: 'deployment',
    description: 'Deploy checkout-service v2.5.0 with disabled readiness probe and aggressive 2s liveness delay.',
    environment: 'production',
    parameters: {
      image_tag: 'v2.5.0',
      readiness_probe_enabled: false,
      liveness_initial_delay_seconds: 2
    }
  },
  safe_canary: {
    label: 'Safe Canary Rollout',
    service: 'payment-service',
    change_type: 'deployment',
    description: 'Canary rollout of payment-service v2.4.2 with verified resource limits and rollback target.',
    environment: 'production',
    rollback_plan: 'Rollback to v2.4.1 within 60s if p99 latency > 300ms',
    parameters: {
      image_tag: 'v2.4.2',
      memory_limit_mb: 2048,
      memory_request_mb: 1024,
      cpu_limit_cores: 2.0,
      cpu_request_cores: 1.0,
      pool_max_size: 25,
      timeout_ms: 3000,
      readiness_probe_enabled: true,
      liveness_initial_delay_seconds: 15,
      rollback_version: 'v2.4.1'
    }
  }
};

const MIN_DRAWER_WIDTH = 420;
const DEFAULT_DRAWER_WIDTH = 680;
const EXPANDED_DRAWER_WIDTH = 960;
let currentDrawerWidth = DEFAULT_DRAWER_WIDTH;
let activePresetKey = 'uncapped_jvm';

/**
 * Initialize Risk Advisor Drawer DOM and event listeners.
 */
export function initRiskAdvisorDrawer() {
  let backdrop = document.getElementById('risk-backdrop');
  let drawer = document.getElementById('risk-drawer');

  if (!backdrop) {
    backdrop = document.createElement('div');
    backdrop.id = 'risk-backdrop';
    backdrop.className = 'risk-backdrop';
    document.body.appendChild(backdrop);
    backdrop.addEventListener('click', closeRiskAdvisorDrawer);
  }

  if (!drawer) {
    drawer = document.createElement('div');
    drawer.id = 'risk-drawer';
    drawer.className = 'risk-drawer';
    document.body.appendChild(drawer);
  }

  renderDrawerStructure(drawer);
}

/**
 * Render static layout and change input form.
 */
function renderDrawerStructure(drawer) {
  const state = store.getState();
  const scenarioKey = state.activeScenarioKey || 'oom_kill';
  const scenarioData = state.activeScenarioData;
  const svc = scenarioData?.incident?.metadata?.service_name || scenarioKey;

  if (currentDrawerWidth && currentDrawerWidth !== DEFAULT_DRAWER_WIDTH) {
    drawer.style.width = `${currentDrawerWidth}px`;
  }

  const preset = PRESET_CHANGES[activePresetKey] || PRESET_CHANGES.uncapped_jvm;

  drawer.innerHTML = `
    <!-- Left Boundary Drag Handle for Resizing -->
    <div class="risk-resize-handle" id="risk-resize-handle" title="Drag to resize drawer" aria-label="Resize drawer"></div>

    <!-- Header -->
    <div class="risk-header">
      <div class="risk-header-title-group">
        <div class="risk-eyebrow">
          <span>🛡️ PRE-DEPLOYMENT RISK ADVISOR</span>
          <span class="badge badge-info font-mono" style="font-size: 9.5px;">Advisory Only</span>
        </div>
        <div class="risk-title">Change Safety & Anti-Pattern Evaluator</div>
      </div>
      <div class="risk-header-actions">
        <button type="button" class="risk-icon-btn" id="btn-risk-expand" title="Expand / Restore width (Toggle)">
          ⤢
        </button>
        <button type="button" class="risk-icon-btn" id="btn-risk-close" title="Close Risk Advisor (Esc)">
          ✕
        </button>
      </div>
    </div>

    <!-- Active Incident Context Bar -->
    <div class="risk-context-bar">
      <div class="font-mono" style="color: var(--text-main); font-size: 11px;">
        <span>Active Incident Context:</span>
        <span style="color: var(--accent-color); font-weight: 600;">${escapeHtml(svc)}</span>
        <span style="color: var(--text-muted); font-size: 10px;">(${escapeHtml(scenarioKey)})</span>
      </div>
      <span class="badge badge-healthy" style="font-size: 9.5px;">Deterministic Rules</span>
    </div>

    <!-- Preset Change Buttons -->
    <div class="risk-presets-bar">
      ${Object.entries(PRESET_CHANGES).map(([k, v]) => `
        <button type="button" class="preset-pill ${k === activePresetKey ? 'active' : ''}" data-preset="${escapeHtml(k)}">
          ${escapeHtml(v.label)}
        </button>
      `).join('')}
    </div>

    <!-- Body Scroll Container -->
    <div class="risk-body-container" id="risk-body-container">
      <!-- Input Form Card -->
      <div class="risk-input-card">
        <div class="risk-form-row">
          <div class="risk-form-group" style="flex: 2;">
            <label class="risk-label" for="risk-input-service">Target Microservice</label>
            <input type="text" id="risk-input-service" class="risk-input" value="${escapeHtml(preset.service)}" />
          </div>
          <div class="risk-form-group" style="flex: 1;">
            <label class="risk-label" for="risk-input-type">Change Type</label>
            <select id="risk-input-type" class="risk-select">
              <option value="deployment" ${preset.change_type === 'deployment' ? 'selected' : ''}>Deployment</option>
              <option value="config" ${preset.change_type === 'config' ? 'selected' : ''}>Config</option>
              <option value="resource" ${preset.change_type === 'resource' ? 'selected' : ''}>Resource</option>
              <option value="dependency" ${preset.change_type === 'dependency' ? 'selected' : ''}>Dependency</option>
            </select>
          </div>
          <div class="risk-form-group" style="flex: 1;">
            <label class="risk-label" for="risk-input-env">Environment</label>
            <select id="risk-input-env" class="risk-select">
              <option value="production" selected>Production</option>
              <option value="staging">Staging</option>
            </select>
          </div>
        </div>

        <div class="risk-form-group">
          <label class="risk-label" for="risk-input-desc">Change Description & Release Scope</label>
          <textarea id="risk-input-desc" class="risk-textarea" rows="2">${escapeHtml(preset.description)}</textarea>
        </div>

        <div class="risk-form-group">
          <label class="risk-label" for="risk-input-params">Configuration & Resource Parameters (JSON)</label>
          <textarea id="risk-input-params" class="risk-textarea font-mono" style="font-size: 11.5px;" rows="4">${escapeHtml(JSON.stringify(preset.parameters, null, 2))}</textarea>
        </div>

        <div class="risk-form-group">
          <label class="risk-label" for="risk-input-rollback">Rollback Plan / Recovery Target</label>
          <input type="text" id="risk-input-rollback" class="risk-input" placeholder="e.g. Rollback to v2.4.0 within 60s" value="${escapeHtml(preset.rollback_plan || '')}" />
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
          <span style="font-size: 11px; color: var(--text-muted);">
            Evaluates limits, pools, timeouts, probes, and drift.
          </span>
          <button type="button" class="btn-risk-analyze" id="btn-risk-analyze">
            <span>🛡️ Analyze Change Risk</span>
          </button>
        </div>
      </div>

      <!-- Analysis Results Container -->
      <div id="risk-results-placeholder">
        <!-- Results injected here upon analysis -->
      </div>
    </div>
  `;

  // Bind Listeners
  const btnClose = drawer.querySelector('#btn-risk-close');
  if (btnClose) btnClose.addEventListener('click', closeRiskAdvisorDrawer);

  const btnExpand = drawer.querySelector('#btn-risk-expand');
  if (btnExpand) {
    btnExpand.addEventListener('click', () => {
      const maxW = Math.min(EXPANDED_DRAWER_WIDTH, Math.floor(window.innerWidth * 0.92));
      if (currentDrawerWidth >= maxW - 30) {
        currentDrawerWidth = DEFAULT_DRAWER_WIDTH;
      } else {
        currentDrawerWidth = maxW;
      }
      drawer.style.width = `${currentDrawerWidth}px`;
    });
  }

  // Preset pill click listeners
  const presetPills = drawer.querySelectorAll('.preset-pill');
  presetPills.forEach((btn) => {
    btn.addEventListener('click', () => {
      const k = btn.getAttribute('data-preset');
      if (k && PRESET_CHANGES[k]) {
        activePresetKey = k;
        renderDrawerStructure(drawer);
        // Auto-run analysis for instant feedback
        setTimeout(() => triggerRiskAnalysis(), 50);
      }
    });
  });

  // Analyze button click
  const btnAnalyze = drawer.querySelector('#btn-risk-analyze');
  if (btnAnalyze) {
    btnAnalyze.addEventListener('click', () => {
      triggerRiskAnalysis();
    });
  }

  // Resize drag setup
  setupDrawerResize(drawer);
}

/**
 * Setup smooth horizontal drag resizing on the left boundary of the drawer.
 */
function setupDrawerResize(drawer) {
  const handle = drawer.querySelector('#risk-resize-handle');
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
    document.body.classList.add('risk-resizing');

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    window.addEventListener('pointercancel', onPointerUp);
  };

  const onPointerMove = (e) => {
    if (!isDragging) return;
    const delta = startX - e.clientX;
    const maxAllowed = Math.min(1200, Math.floor(window.innerWidth * 0.94));
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
    document.body.classList.remove('risk-resizing');

    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  handle.addEventListener('pointerdown', onPointerDown);
}

/**
 * Open Risk Advisor Drawer.
 */
export function openRiskAdvisorDrawer() {
  initRiskAdvisorDrawer();
  const backdrop = document.getElementById('risk-backdrop');
  const drawer = document.getElementById('risk-drawer');
  if (backdrop) backdrop.classList.add('open');
  if (drawer) {
    drawer.classList.add('open');
    renderDrawerStructure(drawer);
    // Auto-run current preset on open
    setTimeout(() => triggerRiskAnalysis(), 100);
  }
  store.setState({ riskAdvisorOpen: true });
}

/**
 * Close Risk Advisor Drawer.
 */
export function closeRiskAdvisorDrawer() {
  const backdrop = document.getElementById('risk-backdrop');
  const drawer = document.getElementById('risk-drawer');
  if (backdrop) backdrop.classList.remove('open');
  if (drawer) drawer.classList.remove('open');
  store.setState({ riskAdvisorOpen: false });
}

/**
 * Toggle open / close state.
 */
export function toggleRiskAdvisorDrawer() {
  const state = store.getState();
  if (state.riskAdvisorOpen) {
    closeRiskAdvisorDrawer();
  } else {
    openRiskAdvisorDrawer();
  }
}

/**
 * Reset Risk Advisor state upon scenario switch.
 */
export function resetRiskAdvisor() {
  store.setState({
    riskAnalysisResult: null,
    riskAdvisorLoading: false,
    riskAdvisorError: null
  });
  activePresetKey = 'uncapped_jvm';
  const drawer = document.getElementById('risk-drawer');
  if (drawer) {
    renderDrawerStructure(drawer);
  }
}

/**
 * Read form inputs, dispatch analysis request, and render findings.
 */
async function triggerRiskAnalysis() {
  const drawer = document.getElementById('risk-drawer');
  if (!drawer) return;

  const svc = drawer.querySelector('#risk-input-service')?.value?.trim() || 'order-service';
  const changeType = drawer.querySelector('#risk-input-type')?.value || 'deployment';
  const env = drawer.querySelector('#risk-input-env')?.value || 'production';
  const desc = drawer.querySelector('#risk-input-desc')?.value?.trim() || 'Proposed change';
  const rollbackPlan = drawer.querySelector('#risk-input-rollback')?.value?.trim() || null;
  const paramsText = drawer.querySelector('#risk-input-params')?.value?.trim() || '{}';

  let paramsObj = {};
  try {
    paramsObj = JSON.parse(paramsText);
  } catch {
    renderError('Invalid JSON in parameters field. Please correct syntax.');
    return;
  }

  const state = store.getState();
  const scenarioKey = state.activeScenarioKey || 'oom_kill';

  const proposedChange = {
    service: svc,
    change_type: changeType,
    description: desc,
    environment: env,
    rollback_plan: rollbackPlan,
    parameters: paramsObj
  };

  store.setState({ riskAdvisorLoading: true, riskAdvisorError: null });
  renderLoading();

  try {
    const result = await api.analyzeRisk(proposedChange, scenarioKey);
    store.setState({
      riskAnalysisResult: result,
      riskAdvisorLoading: false
    });
    renderResults(result);
  } catch (err) {
    console.error('Risk analysis request failed:', err);
    store.setState({
      riskAdvisorLoading: false,
      riskAdvisorError: err.message || 'Failed to analyze proposed change.'
    });
    renderError(err.message || 'Failed to analyze proposed change.');
  }
}

function renderLoading() {
  const container = document.getElementById('risk-results-placeholder');
  if (!container) return;

  container.innerHTML = `
    <div class="risk-results-card" style="align-items: center; justify-content: center; padding: 32px 20px;">
      <div class="copilot-spinner" style="width: 24px; height: 24px; margin-bottom: 12px;"></div>
      <div style="font-size: 13px; color: var(--text-main); font-weight: 600;">
        Evaluating Deterministic SRE Risk Rules...
      </div>
      <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
        Cross-referencing resource limits, connection pools, timeouts, and active telemetry baseline.
      </div>
    </div>
  `;
}

function renderError(msg) {
  const container = document.getElementById('risk-results-placeholder');
  if (!container) return;

  container.innerHTML = `
    <div class="alert-banner alert-banner-critical" style="margin-top: 10px;">
      <span>❌ ${escapeHtml(msg)}</span>
    </div>
  `;
}

/**
 * Render 3-Tier Risk Results: Observed Facts -> Derived Findings -> Preventive Recommendations.
 */
function renderResults(result) {
  const container = document.getElementById('risk-results-placeholder');
  if (!container) return;

  const severityClass = (result.overall_severity || 'LOW').toLowerCase();
  const isBlocked = !result.is_safe_to_deploy;
  const findings = result.findings || [];
  const facts = result.observed_facts_summary || [];
  const recs = result.preventive_recommendations || [];

  container.innerHTML = `
    <div class="risk-results-card">
      <!-- Score & Gate Banner -->
      <div class="risk-score-banner">
        <div class="risk-score-group">
          <div class="risk-score-circle ${severityClass}">
            <span class="score-num">${result.risk_score}</span>
            <span class="score-lbl">RISK</span>
          </div>
          <div>
            <div style="font-size: 14px; font-weight: 700; color: var(--text-main);">
              Overall Severity: <span style="text-transform: uppercase;">${escapeHtml(result.overall_severity)}</span>
            </div>
            <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
              ${result.rule_evaluation_count} safety checks evaluated · Context: ${result.scenario_context_applied ? 'Telemetry Cross-Referenced' : 'Standalone'}
            </div>
          </div>
        </div>

        <div class="risk-gate-status">
          <span class="gate-badge ${isBlocked ? 'blocked' : 'safe'}">
            ${isBlocked ? '🚫 DEPLOYMENT BLOCKED' : '🛡️ SAFE TO DEPLOY'}
          </span>
          <span style="font-size: 10px; color: var(--text-muted);">
            ${isBlocked ? 'Mandatory guardrails required' : 'Proceed with canary rollout'}
          </span>
        </div>
      </div>

      <!-- Explanation narrative -->
      <div class="risk-explanation-card">
        ${escapeHtml(result.explanation)}
      </div>

      <!-- 1. Observed Change Facts -->
      ${facts.length > 0 ? `
        <div class="risk-facts-block">
          <div class="facts-title">
            <span>🔍</span>
            <span>1. Observed Change Facts & Telemetry Baseline</span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 6px;">
            ${facts.map((f) => `
              <div class="fact-item">
                <span style="color: #38bdf8; font-weight: 700;">•</span>
                <div>${escapeHtml(f)}</div>
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}

      <!-- 2. Derived Risk Findings -->
      <div class="risk-findings-block">
        <div class="findings-header">
          <span>⚠️</span>
          <span>2. Derived Risk Findings (${findings.length})</span>
        </div>
        ${findings.length === 0 ? `
          <div style="font-size: 12px; color: var(--text-muted); font-style: italic; padding: 8px;">
            ✓ No anti-patterns detected. Proposed change satisfies standard SRE safety constraints.
          </div>
        ` : `
          <div style="display: flex; flex-direction: column; gap: 8px;">
            ${findings.map((f) => `
              <div class="finding-card ${f.severity.toLowerCase()}">
                <div class="finding-title-row">
                  <span class="finding-title">${escapeHtml(f.title)}</span>
                  <div style="display: flex; align-items: center; gap: 6px;">
                    <span class="badge ${getSeverityBadgeClass(f.severity)}" style="font-size: 9.5px;">${escapeHtml(f.severity)}</span>
                    <span class="font-mono" style="font-size: 10px; color: var(--text-muted);">+${f.score_impact}pts</span>
                  </div>
                </div>
                <div class="finding-reasoning">
                  ${escapeHtml(f.derived_risk)}
                </div>
                ${f.recommendations && f.recommendations.length > 0 ? `
                  <div style="font-size: 11px; color: #34d399; margin-top: 2px;">
                    <strong>Fix:</strong> ${escapeHtml(f.recommendations[0])}
                  </div>
                ` : ''}
              </div>
            `).join('')}
          </div>
        `}
      </div>

      <!-- 3. Preventive Recommendations -->
      ${recs.length > 0 ? `
        <div class="risk-recs-block">
          <div class="recs-title">
            <span>🛡️</span>
            <span>3. Recommended Preventive Actions</span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 6px;">
            ${recs.map((r) => `
              <div class="rec-item">
                <span style="color: #34d399; font-weight: 700;">✓</span>
                <div>${escapeHtml(r)}</div>
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}
    </div>
  `;
}

function getSeverityBadgeClass(sev) {
  switch (String(sev).toUpperCase()) {
    case 'CRITICAL':
      return 'badge-critical';
    case 'HIGH':
      return 'badge-warning';
    case 'MEDIUM':
      return 'badge-info';
    case 'LOW':
    default:
      return 'badge-healthy';
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
