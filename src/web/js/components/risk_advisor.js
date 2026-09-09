/**
 * AERO Pre-Deployment Risk Advisor Component
 * Evaluates proposed deployment/configuration changes before production release.
 * Checks proposed changes against:
 * 1. Incident diagnosis root cause & observed telemetry (Recurrence Prevention)
 * 2. AERO mitigation recommendations
 * 3. 18 Generic SRE deployment safety rules
 */

import { api } from '../api.js';
import { store } from '../state.js';

export const PRESET_CHANGES = {
  aero_recommended: {
    label: 'AERO Recommended Fix',
    service: 'worker-service',
    change_type: 'deployment',
    description: 'Deploy worker-service v1.9.1 with 2048MB memory limit, 10 workers concurrency, readiness probe enabled, and validated rollback target.',
    environment: 'production',
    rollback_plan: 'Rollback to v1.9.0 within 60s if error rate > 1%',
    parameters: {
      image_tag: 'v1.9.1',
      memory_limit_mb: 2048,
      memory_request_mb: 1024,
      cpu_limit_cores: 2.0,
      cpu_request_cores: 1.0,
      concurrency: 10,
      pool_max_size: 25,
      readiness_probe_enabled: true,
      liveness_initial_delay_seconds: 15,
      rollback_version: 'v1.9.0',
      debug_mode: false
    }
  },
  unsafe_insufficient_memory: {
    label: 'Unsafe Fix — Insufficient Memory',
    service: 'worker-service',
    change_type: 'deployment',
    description: 'Deploy worker-service with 512MB memory limit (below observed 1.95GB peak) and unversioned latest image without rollback plan.',
    environment: 'production',
    rollback_plan: '',
    parameters: {
      image_tag: 'latest',
      memory_limit_mb: 512,
      memory_request_mb: 256,
      concurrency: 10
    }
  },
  unsafe_increased_concurrency: {
    label: 'Unsafe Fix — Increased Concurrency',
    service: 'worker-service',
    change_type: 'deployment',
    description: 'Increase worker concurrency from 10 to 100 with baseline 1024MB memory limit, multiplying per-worker heap allocations.',
    environment: 'production',
    rollback_plan: 'Revert to v1.9.0',
    parameters: {
      image_tag: 'v1.9.1',
      memory_limit_mb: 1024,
      memory_request_mb: 512,
      concurrency: 100,
      rollback_version: 'v1.9.0'
    }
  },
  unrelated_fix: {
    label: 'Unrelated Fix',
    service: 'worker-service',
    change_type: 'config',
    description: 'Update logging configuration and connection pool settings without addressing memory limits or worker concurrency.',
    environment: 'production',
    rollback_plan: 'Revert logging config',
    parameters: {
      pool_max_size: 30,
      timeout_ms: 3000,
      readiness_probe_enabled: true,
      rollback_version: 'v1.9.0'
    }
  }
};

// Aliases for backwards compatibility
PRESET_CHANGES.uncapped_jvm = PRESET_CHANGES.unsafe_insufficient_memory;
PRESET_CHANGES.db_pool_starvation = PRESET_CHANGES.unsafe_increased_concurrency;
PRESET_CHANGES.missing_readiness = PRESET_CHANGES.unrelated_fix;
PRESET_CHANGES.safe_canary = PRESET_CHANGES.aero_recommended;

const MIN_DRAWER_WIDTH = 420;
const DEFAULT_DRAWER_WIDTH = 700;
const EXPANDED_DRAWER_WIDTH = 980;
let currentDrawerWidth = DEFAULT_DRAWER_WIDTH;
let activePresetKey = 'aero_recommended';

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
  const svc = scenarioData?.incident?.metadata?.service_name || scenarioData?.incident?.metadata?.affected_service || 'worker-service';

  if (currentDrawerWidth && currentDrawerWidth !== DEFAULT_DRAWER_WIDTH) {
    drawer.style.width = `${currentDrawerWidth}px`;
  }

  const preset = PRESET_CHANGES[activePresetKey] || PRESET_CHANGES.aero_recommended;

  drawer.innerHTML = `
    <!-- Left Boundary Drag Handle for Resizing -->
    <div class="risk-resize-handle" id="risk-resize-handle" title="Drag to resize drawer" aria-label="Resize drawer"></div>

    <!-- Header -->
    <div class="risk-header">
      <div class="risk-header-title-group">
        <div class="risk-eyebrow">
          <span>🛡️ PRE-DEPLOYMENT RISK ADVISOR</span>
          <span class="badge badge-info font-mono" style="font-size: 9.5px;">Prevention Gate</span>
        </div>
        <div class="risk-title">Change Safety & Recurrence Prevention</div>
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

    <!-- Learning From Incident Evidence Context Bar -->
    <div class="risk-context-bar">
      <div class="font-mono" style="color: var(--text-main); font-size: 11px;">
        <span>Learning From Incident Evidence:</span>
        <span style="color: var(--accent-color); font-weight: 600;">${escapeHtml(svc)}</span>
        <span style="color: var(--text-muted); font-size: 10px;">(${escapeHtml(scenarioKey)})</span>
      </div>
      <span class="badge badge-healthy" style="font-size: 9.5px;">Deterministic Prevention</span>
    </div>

    <!-- Preset Change Buttons -->
    <div class="risk-presets-bar">
      ${['aero_recommended', 'unsafe_insufficient_memory', 'unsafe_increased_concurrency', 'unrelated_fix'].map((k) => {
        const v = PRESET_CHANGES[k];
        return `
          <button type="button" class="preset-pill ${k === activePresetKey ? 'active' : ''}" data-preset="${escapeHtml(k)}">
            ${escapeHtml(v.label)}
          </button>
        `;
      }).join('')}
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
          <label class="risk-label" for="risk-input-desc">Proposed Change Description</label>
          <textarea id="risk-input-desc" class="risk-textarea" rows="2">${escapeHtml(preset.description)}</textarea>
        </div>

        <div class="risk-form-group">
          <label class="risk-label" for="risk-input-params">Configuration & Resource Parameters (JSON)</label>
          <textarea id="risk-input-params" class="risk-textarea font-mono" style="font-size: 11.5px;" rows="4">${escapeHtml(JSON.stringify(preset.parameters, null, 2))}</textarea>
        </div>

        <div class="risk-form-group">
          <label class="risk-label" for="risk-input-rollback">Rollback Plan / Target Version</label>
          <input type="text" id="risk-input-rollback" class="risk-input" placeholder="e.g. Rollback to v1.9.0 within 60s" value="${escapeHtml(preset.rollback_plan || '')}" />
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
          <span style="font-size: 11px; color: var(--text-muted);">
            Evaluates against diagnosed root cause, observed saturation, and SRE rules.
          </span>
          <button type="button" class="btn-risk-analyze" id="btn-risk-analyze">
            <span>🛡️ Evaluate Deployment Risk</span>
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
      const maxW = Math.min(EXPANDED_DRAWER_WIDTH, Math.floor(window.innerWidth * 0.94));
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
    const maxAllowed = Math.min(1200, Math.floor(window.innerWidth * 0.96));
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
  activePresetKey = 'aero_recommended';
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

  const svc = drawer.querySelector('#risk-input-service')?.value?.trim() || 'worker-service';
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
      riskAdvisorError: err.message || 'Failed to evaluate deployment risk.'
    });
    renderError(err.message || 'Failed to evaluate deployment risk.');
  }
}

function renderLoading() {
  const container = document.getElementById('risk-results-placeholder');
  if (!container) return;

  container.innerHTML = `
    <div class="risk-results-card" style="align-items: center; justify-content: center; padding: 32px 20px;">
      <div class="copilot-spinner" style="width: 24px; height: 24px; margin-bottom: 12px;"></div>
      <div style="font-size: 13px; color: var(--text-main); font-weight: 600;">
        Evaluating Deployment Risk & Recurrence Prevention...
      </div>
      <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
        Checking proposed change against diagnosed root cause, saturation evidence, and generic SRE safety rules.
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
 * Render complete Risk Advisor Results Breakdown:
 * - Deployment Risk & Decision Gate Banner
 * - Evaluated Proposed Change Card
 * - Diagnosis Alignment Card
 * - Recurrence Risk Prediction Card
 * - 1. Diagnosis-Aware Prevention Checks
 * - 2. Generic SRE Safety Checks
 * - 3. Recommended Preventive Actions
 */
function renderResults(result) {
  const container = document.getElementById('risk-results-placeholder');
  if (!container) return;

  const severityClass = (result.overall_severity || 'LOW').toLowerCase();
  const decision = result.decision || (result.is_safe_to_deploy ? 'SAFE' : 'BLOCKED');
  const isBlocked = decision === 'BLOCKED' || decision === 'HIGH_RISK';
  const isSafe = decision === 'SAFE';

  const genericFindings = result.generic_findings || [];
  const preventionFindings = result.prevention_findings || [];
  const allFindings = result.findings || [...genericFindings, ...preventionFindings];
  const recs = result.preventive_recommendations || [];
  const diagAlign = result.diagnosis_alignment || {};
  const recPred = result.predicted_recurrence || {};
  const evalChange = result.evaluated_change || {};
  const evalParams = evalChange.parameters || {};

  // Authoritative Evaluated Fields directly from API response
  const evalSvc = evalChange.service || evalParams.service || 'worker-service';
  const evalMem = evalChange.memory_limit_mb != null ? evalChange.memory_limit_mb : evalParams.memory_limit_mb;
  const evalMemText = evalMem != null && evalMem !== '' ? `${evalMem} MB` : 'Uncapped';

  const evalConc = evalChange.concurrency != null ? evalChange.concurrency : (evalParams.concurrency != null ? evalParams.concurrency : evalParams.worker_count);
  const evalConcText = evalConc != null ? `${evalConc} workers` : 'Default';

  const evalImage = evalChange.image_tag || evalParams.image_tag || 'latest';
  const evalRollback = evalChange.rollback_plan || evalChange.rollback_version || evalParams.rollback_version || evalParams.rollback_plan;
  const evalRollbackText = evalRollback ? (String(evalRollback).length > 45 ? `${String(evalRollback).slice(0, 42)}...` : String(evalRollback)) : 'None (Unconfigured)';

  const evalDebug = evalChange.debug_mode === true || evalParams.debug_mode === true;
  const evalDebugText = evalDebug ? 'Enabled (DEBUG)' : 'Disabled';

  // Format decision gate label & badge class
  let gateBadgeClass = 'safe';
  let gateBadgeText = '🛡️ SAFE TO DEPLOY (SAFE)';
  if (decision === 'BLOCKED') {
    gateBadgeClass = 'blocked';
    gateBadgeText = '🚫 DEPLOYMENT BLOCKED';
  } else if (decision === 'HIGH_RISK') {
    gateBadgeClass = 'blocked';
    gateBadgeText = '⚠️ HIGH RISK DEPLOYMENT';
  } else if (decision === 'WARNING') {
    gateBadgeClass = 'caution';
    gateBadgeText = '⚠️ PROCEED WITH CAUTION (WARNING)';
  }

  // Recurrence badge class
  const recSev = (recPred.risk || 'LOW').toUpperCase();
  let recBadgeClass = 'badge-healthy';
  let recCardClass = 'safe';
  if (recSev === 'CRITICAL') {
    recBadgeClass = 'badge-critical';
    recCardClass = '';
  } else if (recSev === 'HIGH') {
    recBadgeClass = 'badge-warning';
    recCardClass = 'warning';
  } else if (recSev === 'MEDIUM') {
    recBadgeClass = 'badge-info';
    recCardClass = 'warning';
  }

  container.innerHTML = `
    <div class="risk-results-card">
      <!-- 1. Deployment Risk & Gate Banner -->
      <div class="risk-score-banner">
        <div class="risk-score-group">
          <div class="risk-score-circle ${severityClass}">
            <span class="score-num">${result.risk_score}</span>
            <span class="score-lbl">RISK</span>
          </div>
          <div>
            <div style="font-size: 14px; font-weight: 700; color: var(--text-main);">
              Deployment Risk: <span style="text-transform: uppercase;">${escapeHtml(result.overall_severity)}</span>
            </div>
            <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
              Score: ${result.risk_score}/100 · ${result.rule_evaluation_count || 13} deterministic checks evaluated
            </div>
          </div>
        </div>

        <div class="risk-gate-status">
          <span class="gate-badge ${gateBadgeClass}">
            ${gateBadgeText}
          </span>
          <span style="font-size: 10px; color: var(--text-muted);">
            ${isBlocked ? 'Pre-deployment blocking gates triggered' : 'Verified safe for rollout'}
          </span>
        </div>
      </div>

      <!-- Narrative explanation -->
      <div class="risk-explanation-card">
        ${escapeHtml(result.explanation)}
      </div>

      <!-- 2. Evaluated Proposed Change -->
      <div class="risk-eval-change-card">
        <div class="risk-eval-header">
          <span>📦</span>
          <span>EVALUATED PROPOSED CHANGE</span>
        </div>
        <div class="risk-eval-grid">
          <div class="risk-eval-item">
            <span class="risk-eval-label">Target Service</span>
            <div class="risk-eval-val font-mono">${escapeHtml(evalSvc)}</div>
          </div>
          <div class="risk-eval-item">
            <span class="risk-eval-label">Memory Limit</span>
            <div class="risk-eval-val font-mono">${escapeHtml(evalMemText)}</div>
          </div>
          <div class="risk-eval-item">
            <span class="risk-eval-label">Concurrency</span>
            <div class="risk-eval-val font-mono">${escapeHtml(evalConcText)}</div>
          </div>
          <div class="risk-eval-item">
            <span class="risk-eval-label">Image Tag</span>
            <div class="risk-eval-val font-mono">${escapeHtml(evalImage)}</div>
          </div>
          <div class="risk-eval-item">
            <span class="risk-eval-label">Rollback Target</span>
            <div class="risk-eval-val font-mono">${escapeHtml(evalRollbackText)}</div>
          </div>
          <div class="risk-eval-item">
            <span class="risk-eval-label">Debug Mode</span>
            <div class="risk-eval-val font-mono">${escapeHtml(evalDebugText)}</div>
          </div>
        </div>
      </div>

      <!-- 3. Diagnosis Alignment -->
      ${diagAlign.root_cause ? `
        <div class="risk-alignment-card">
          <div class="alignment-title">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span>🧠</span>
              <span>DIAGNOSIS ALIGNMENT</span>
            </div>
            <span class="badge ${diagAlign.is_aligned ? 'badge-healthy' : 'badge-warning'}" style="font-size: 9.5px;">
              ${diagAlign.is_aligned ? '✓ Aligned with Diagnosis' : '⚠️ Misaligned with Incident Findings'}
            </span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 4px; font-size: 12px;">
            <div><strong style="color: var(--text-muted);">Root Cause:</strong> <span style="color: var(--text-main);">${escapeHtml(diagAlign.root_cause)}</span></div>
            <div><strong style="color: var(--text-muted);">Observed Evidence:</strong> <span style="color: #38bdf8;" class="font-mono">${escapeHtml(diagAlign.observed_peak || '99.8% memory saturation')}</span></div>
            ${diagAlign.aero_recommendations && diagAlign.aero_recommendations.length > 0 ? `
              <div><strong style="color: var(--text-muted);">AERO Recommendation:</strong> <span style="color: #34d399;">${escapeHtml(diagAlign.aero_recommendations[0])}</span></div>
            ` : ''}
            <div style="color: var(--text-secondary); margin-top: 2px; font-style: italic;">
              ${escapeHtml(diagAlign.alignment_summary)}
            </div>
          </div>
        </div>
      ` : ''}

      <!-- 4. Recurrence Prediction Card -->
      <div class="risk-recurrence-card ${recCardClass}">
        <div class="recurrence-header">
          <div style="display: flex; align-items: center; gap: 6px; color: ${recSev === 'LOW' ? '#34d399' : (recSev === 'CRITICAL' ? '#f87171' : '#fbbf24')};">
            <span>🔮</span>
            <span>RECURRENCE RISK PREDICTION</span>
          </div>
          <span class="badge ${recBadgeClass}" style="font-size: 9.5px;">
            ${escapeHtml(recPred.risk || 'LOW')} RECURRENCE RISK
          </span>
        </div>
        <div style="font-size: 12px; color: var(--text-main); line-height: 1.45;">
          ${escapeHtml(recPred.reason || 'Proposed change satisfies verified safety constraints.')}
        </div>
      </div>

      <!-- 5. Diagnosis-Aware Prevention Checks -->
      ${preventionFindings.length > 0 ? `
        <div class="risk-findings-block">
          <div class="findings-header" style="color: #f87171;">
            <span>🛡️</span>
            <span>1. Diagnosis-Aware Prevention Checks (${preventionFindings.length})</span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 8px;">
            ${preventionFindings.map((f) => renderFindingCard(f)).join('')}
          </div>
        </div>
      ` : ''}

      <!-- 6. Generic SRE Safety Checks -->
      <div class="risk-findings-block">
        <div class="findings-header">
          <span>⚙️</span>
          <span>${preventionFindings.length > 0 ? '2' : '1'}. Generic SRE Safety Checks (${genericFindings.length})</span>
        </div>
        ${genericFindings.length === 0 ? `
          <div style="font-size: 12px; color: var(--text-muted); font-style: italic; padding: 8px;">
            ✓ All generic deployment safety checks passed (limits, connection pools, timeouts, probes, and rollback strategy).
          </div>
        ` : `
          <div style="display: flex; flex-direction: column; gap: 8px;">
            ${genericFindings.map((f) => renderFindingCard(f)).join('')}
          </div>
        `}
      </div>

      <!-- 7. Recommended Preventive Actions -->
      ${recs.length > 0 ? `
        <div class="risk-recs-block">
          <div class="recs-title">
            <span>🛡️</span>
            <span>Recommended Preventive Actions</span>
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

function renderFindingCard(f) {
  const sevClass = (f.severity || 'LOW').toLowerCase();
  return `
    <div class="finding-card ${sevClass}">
      <div class="finding-title-row">
        <div style="display: flex; align-items: center; gap: 6px;">
          <span class="font-mono" style="font-size: 10px; color: var(--text-muted);">${escapeHtml(f.rule_id || 'RULE')}</span>
          <span class="finding-title">${escapeHtml(f.title)}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
          <span class="badge ${getSeverityBadgeClass(f.severity)}" style="font-size: 9.5px;">${escapeHtml(f.severity)}</span>
          <span class="font-mono" style="font-size: 10px; color: var(--text-muted);">+${f.score_impact}pts</span>
        </div>
      </div>
      <div class="finding-reasoning">
        ${escapeHtml(f.derived_risk)}
      </div>
      ${f.observed_facts && f.observed_facts.length > 0 ? `
        <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
          <strong>Evidence:</strong> ${escapeHtml(f.observed_facts[0])}
        </div>
      ` : ''}
      ${f.recommendations && f.recommendations.length > 0 ? `
        <div style="font-size: 11px; color: #34d399; margin-top: 2px;">
          <strong>Fix:</strong> ${escapeHtml(f.recommendations[0])}
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
