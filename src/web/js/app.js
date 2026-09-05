/**
 * AERO Application Controller & Shell Bootstrapper
 * Coordinates state, REST API calls, header controls, and lifecycle view switching.
 */

import { store } from './state.js';
import { api } from './api.js';
import { initHeader } from './components/header.js';
import { renderTelemetryWorkspace } from './components/telemetry.js';

// Configuration for lifecycle stages (4B-4H placeholders in Stage 4A)
const STAGE_META = {
  telemetry: {
    stage: 'Stage 4B',
    title: 'Evidence & Telemetry Stream',
    icon: '📊',
    desc: 'Deep inspection of correlated incident logs, time-series metrics, anomaly thresholds, and distributed trace spans.'
  },
  timeline: {
    stage: 'Stage 4C',
    title: 'Incident Timeline & State Machine',
    icon: '⏱️',
    desc: 'Chronological progression of anomalies, trigger events, alert thresholds, and operational milestones.'
  },
  rca: {
    stage: 'Stage 4D',
    title: 'Root Cause Analysis & Diagnostic Reasoning',
    icon: '🧠',
    desc: 'Structured SRE diagnostic report featuring primary root cause, contributing factors, affected services, and confidence score.'
  },
  grounding: {
    stage: 'Stage 4D',
    title: 'Telemetry Grounding & Verification Matrix',
    icon: '🛡️',
    desc: 'Rigorous empirical verification of AI claims against incident telemetry. Displays Grounding Recall, Precision, and Hallucination Rate.'
  },
  remediation: {
    stage: 'Stage 4E',
    title: 'Safe Remediation Simulator (Dry-Run Only)',
    icon: '⚙️',
    desc: 'Simulated execution environment for mitigation runbooks and scripts. Strictly isolated simulation with zero infrastructure mutation.'
  },
  postmortem: {
    stage: 'Stage 4F',
    title: 'Incident Postmortem & SRE Report',
    icon: '📄',
    desc: 'Actionable SRE postmortem document featuring 5-Whys analysis, timeline, lessons learned, and preventive action items with Markdown export.'
  },
  architecture: {
    stage: 'Stage 4H',
    title: 'Topology & Blast Radius Visualizer',
    icon: '🌐',
    desc: 'Interactive cloud service dependency graph illustrating blast radius, cascade paths, and resource health status.'
  }
};

/**
 * Extracts normalized incident and telemetry metadata from scenario response.
 * @param {object|null} scenarioData 
 * @param {string|null} fallbackKey 
 */
export function extractScenarioInfo(scenarioData, fallbackKey) {
  if (!scenarioData) {
    return {
      key: fallbackKey || 'INC',
      title: 'Loading incident...',
      service: 'Cloud Service',
      severity: 'CRITICAL',
      status: 'INVESTIGATING',
      impact: '',
      logsCount: 0,
      metricsCount: 0,
      deploymentsCount: 0,
      healthSignalsCount: 0,
    };
  }

  // Handle BenchmarkScenarioBundle: { ground_truth: {...}, incident: { metadata: {...}, telemetry: {...} } }
  const gt = scenarioData.ground_truth || {};
  const incident = scenarioData.incident || {};
  const metadata = incident.metadata || {};
  const telemetry = incident.telemetry || scenarioData.telemetry || scenarioData.telemetry_pack || {};

  const key = metadata.incident_id || gt.scenario_id || scenarioData.scenario_id || fallbackKey || 'INC';
  const title = metadata.title || gt.scenario_name || scenarioData.scenario_name || scenarioData.title || key;
  const service = metadata.affected_service || gt.affected_service || scenarioData.affected_service || scenarioData.service_name || 'Cloud Service';
  const severity = metadata.severity || gt.category || scenarioData.severity || 'CRITICAL';
  const status = metadata.status || 'OPEN';
  const impact = metadata.impact_summary || gt.root_cause_summary || '';

  const logsCount = Array.isArray(telemetry.logs) ? telemetry.logs.length : (scenarioData.logs_count || 0);
  const metricsCount = Array.isArray(telemetry.metrics) ? telemetry.metrics.length : (scenarioData.metrics_count || 0);
  const deploymentsCount = Array.isArray(telemetry.deployments) ? telemetry.deployments.length : 0;
  const healthSignalsCount = Array.isArray(telemetry.health_signals) ? telemetry.health_signals.length : 0;

  return {
    key,
    title,
    service,
    severity,
    status,
    impact,
    logsCount,
    metricsCount,
    deploymentsCount,
    healthSignalsCount,
    raw: scenarioData
  };
}

/**
 * Render active lifecycle view in the right workspace pane.
 * @param {string} tabKey 
 */
function renderActiveView(tabKey) {
  const container = document.getElementById('active-view-container');
  if (!container) return;

  const state = store.getState();

  // Stage 4B: Fully rendered Incident Workspace & Telemetry for 'telemetry' tab
  if (tabKey === 'telemetry') {
    renderTelemetryWorkspace(container, state.activeScenarioData);
    return;
  }

  // Future Stages (4C-4H): Sleek placeholder containers
  const meta = STAGE_META[tabKey] || STAGE_META.telemetry;
  const info = extractScenarioInfo(state.activeScenarioData, state.activeScenarioKey);

  container.innerHTML = `
    <div class="pane-card">
      <div class="pane-header">
        <div class="pane-title-group">
          <span class="pane-title">${meta.title}</span>
        </div>
        <span class="badge badge-info">${meta.stage}</span>
      </div>

      <div class="placeholder-card">
        <div class="placeholder-icon">${meta.icon}</div>
        <div class="placeholder-title">${meta.title}</div>
        <p class="placeholder-desc">${meta.desc}</p>
        <div style="display: flex; gap: 8px; align-items: center; margin-top: 8px;">
          <span class="placeholder-tag">Shell Container Ready</span>
          <span class="font-mono" style="font-size: 11px; color: var(--text-muted);" id="active-scenario-indicator">
            Active Scenario: ${info.title} (${info.key})
          </span>
        </div>
      </div>
    </div>
  `;
}

/**
 * Update left-pane telemetry stream quick summary.
 * @param {object} scenarioData 
 */
function updateTelemetryLeftPane(scenarioData) {
  const container = document.getElementById('telemetry-pane-body');
  if (!container) return;

  if (!scenarioData) {
    container.innerHTML = `
      <div class="placeholder-card" style="padding: 20px 16px;">
        <p class="placeholder-desc" style="font-size: 11px;">Select a scenario to view telemetry stream.</p>
      </div>
    `;
    return;
  }

  const incident = scenarioData.incident || {};
  const telemetry = incident.telemetry || scenarioData.telemetry || {};
  const logs = telemetry.logs || [];
  const deployments = telemetry.deployments || [];
  const healthSignals = telemetry.health_signals || [];

  const errorLogs = logs.filter((l) => ['FATAL', 'ERROR'].includes(String(l.log_level).toUpperCase())).length;
  const warnLogs = logs.filter((l) => String(l.log_level).toUpperCase() === 'WARN').length;
  const unhealthyProbes = healthSignals.filter((h) => String(h.status).toUpperCase() === 'UNHEALTHY').length;

  container.innerHTML = `
    <div style="display: flex; flex-direction: column; gap: 10px;">
      <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.2); padding: 8px 12px; border-radius: var(--radius-sm);">
        <span class="font-mono" style="font-size: 11px; color: var(--text-muted);">Critical Errors</span>
        <span class="badge ${errorLogs > 0 ? 'badge-critical' : 'badge-healthy'}">${errorLogs} Errors</span>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.2); padding: 8px 12px; border-radius: var(--radius-sm);">
        <span class="font-mono" style="font-size: 11px; color: var(--text-muted);">Warning Signals</span>
        <span class="badge ${warnLogs > 0 ? 'badge-warning' : 'badge-healthy'}">${warnLogs} Warnings</span>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.2); padding: 8px 12px; border-radius: var(--radius-sm);">
        <span class="font-mono" style="font-size: 11px; color: var(--text-muted);">Probe Outages</span>
        <span class="badge ${unhealthyProbes > 0 ? 'badge-critical' : 'badge-healthy'}">${unhealthyProbes} Unhealthy</span>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.2); padding: 8px 12px; border-radius: var(--radius-sm);">
        <span class="font-mono" style="font-size: 11px; color: var(--text-muted);">Change Events</span>
        <span class="badge ${deployments.length > 0 ? 'badge-warning' : 'badge-info'}">${deployments.length} Deploys</span>
      </div>
    </div>
  `;
}

/**
 * Update left-pane incident metadata card based on current scenario.
 * @param {object} scenarioData 
 */
function updateIncidentSummary(scenarioData) {
  const state = store.getState();
  const info = extractScenarioInfo(scenarioData, state.activeScenarioKey);

  const titleEl = document.getElementById('incident-title');
  const serviceEl = document.getElementById('incident-service-name');
  const idEl = document.getElementById('incident-id-display');
  const severityEl = document.getElementById('incident-severity');
  const severityBadge = document.getElementById('incident-severity-badge');
  const countsEl = document.getElementById('incident-telemetry-count');

  if (titleEl) titleEl.textContent = info.title;
  if (serviceEl) serviceEl.textContent = info.service;
  if (idEl) idEl.textContent = `#${info.key.toUpperCase()}`;
  
  const sevStr = String(info.severity).replace('SEV1_', '').replace('SEV2_', '');
  if (severityEl) severityEl.textContent = sevStr.toUpperCase();
  if (severityBadge) {
    const isCritical = String(info.severity).toLowerCase().includes('critical');
    severityBadge.className = `badge badge-${isCritical ? 'critical' : 'warning'}`;
  }

  if (countsEl) {
    countsEl.textContent = `${info.logsCount} logs · ${info.metricsCount} metrics · ${info.deploymentsCount} deployments`;
  }

  updateTelemetryLeftPane(scenarioData);
}

/**
 * Load a scenario's complete telemetry pack and update state.
 * @param {string} scenarioKey 
 */
export async function loadScenarioDetails(scenarioKey) {
  if (!scenarioKey) return;
  try {
    store.setState({ isLoading: true, error: null, activeScenarioKey: scenarioKey });
    const scenarioData = await api.getScenarioByKey(scenarioKey);
    store.setState({
      activeScenarioKey: scenarioKey,
      activeScenarioData: scenarioData,
      isLoading: false
    });
    updateIncidentSummary(scenarioData);
    renderActiveView(store.getState().activeTab);
  } catch (err) {
    console.error('Failed to load scenario details:', err);
    store.setState({ isLoading: false, error: err.message });
    showError(`Error loading scenario: ${err.message}`);
  }
}

/**
 * Display a global error message.
 * @param {string} msg 
 */
function showError(msg) {
  const errorContainer = document.getElementById('global-error-container');
  const errorMsg = document.getElementById('global-error-msg');
  if (errorContainer && errorMsg) {
    errorMsg.textContent = msg;
    errorContainer.style.display = 'block';
  }
}

/**
 * Hide global error message.
 */
function clearError() {
  const errorContainer = document.getElementById('global-error-container');
  if (errorContainer) {
    errorContainer.style.display = 'none';
  }
}

/**
 * Initialize lifecycle navigation tab listeners.
 */
function initLifecycleNav() {
  const navList = document.getElementById('lifecycle-nav');
  if (!navList) return;

  const tabs = navList.querySelectorAll('.lifecycle-tab');
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const targetTab = tab.dataset.tab;
      if (!targetTab) return;

      tabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');

      store.setState({ activeTab: targetTab });
      renderActiveView(targetTab);
    });
  });
}

/**
 * Initialize floating quick action buttons (Risk Advisor & SRE Copilot).
 */
function initDockActions() {
  const btnRisk = document.getElementById('btn-dock-risk');
  const btnChat = document.getElementById('btn-dock-chat');

  if (btnRisk) {
    btnRisk.addEventListener('click', () => {
      alert('Risk & Change Advisor drawer will be integrated in Stage 4G.');
    });
  }

  if (btnChat) {
    btnChat.addEventListener('click', () => {
      alert('Interactive SRE Copilot Chat drawer will be integrated in Stage 4G.');
    });
  }
}

/**
 * Main application bootstrap function.
 */
async function bootstrapApp() {
  try {
    clearError();

    // 1. Initialize Header
    initHeader((newScenarioKey) => {
      loadScenarioDetails(newScenarioKey);
    });

    // 2. Initialize Navigation & Actions
    initLifecycleNav();
    initDockActions();

    // 3. Subscribe to reactive state updates
    store.subscribe((state, prevState) => {
      if (state.activeScenarioData !== prevState.activeScenarioData) {
        updateIncidentSummary(state.activeScenarioData);
        renderActiveView(state.activeTab);
      }
      if (state.activeTab !== prevState.activeTab) {
        renderActiveView(state.activeTab);
      }
    });

    // 4. Fetch backend health & config
    try {
      const config = await api.getConfig();
      if (config) {
        store.setState({ gcpConfig: config });
      }
    } catch (e) {
      console.warn('Could not load backend config:', e);
    }

    // 5. Fetch scenarios from REST API
    const scenarios = await api.getScenarios();
    if (scenarios && scenarios.length > 0) {
      const defaultKey = scenarios[0].scenario_id || scenarios[0].scenario_key;
      store.setState({
        scenarios: scenarios,
        activeScenarioKey: defaultKey
      });
      // Load details of the initial scenario
      await loadScenarioDetails(defaultKey);
    } else {
      showError('No scenarios found from API gateway.');
    }
  } catch (err) {
    console.error('Bootstrap failed:', err);
    showError(`Failed to initialize AERO: ${err.message}`);
  }
}

// Start application when DOM is ready
if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrapApp);
  } else {
    bootstrapApp();
  }
}
