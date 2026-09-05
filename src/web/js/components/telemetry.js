/**
 * AERO Stage 4B: Incident Workspace & Telemetry Component
 * Main coordinator rendering golden signal metric charts, log explorer, deployments, and health monitor.
 */

import { renderMetricCard } from './metrics_chart.js';
import { renderLogExplorer, initLogExplorerEvents } from './log_explorer.js';
import { renderDeploymentsPanel } from './deployments.js';
import { renderHealthMonitor } from './health_monitor.js';
import { extractScenarioInfo } from '../app.js';

/**
 * Render the complete Stage 4B Incident Workspace.
 * @param {HTMLElement} container Container element to inject the workspace into
 * @param {object} scenarioData Complete scenario bundle { ground_truth, incident }
 */
export function renderTelemetryWorkspace(container, scenarioData) {
  if (!container) return;

  if (!scenarioData) {
    container.innerHTML = `
      <div class="placeholder-card">
        <div class="spinner"></div>
        <div class="placeholder-title">Loading incident telemetry...</div>
      </div>
    `;
    return;
  }

  const info = extractScenarioInfo(scenarioData);
  const incident = scenarioData.incident || {};
  const telemetry = incident.telemetry || scenarioData.telemetry || {};

  const metrics = Array.isArray(telemetry.metrics) ? telemetry.metrics : [];
  const logs = Array.isArray(telemetry.logs) ? telemetry.logs : [];
  const deployments = Array.isArray(telemetry.deployments) ? telemetry.deployments : [];
  const healthSignals = Array.isArray(telemetry.health_signals) ? telemetry.health_signals : [];
  const detectedAt = incident.metadata?.detected_at || null;

  // Render Golden Signals Grid
  let metricsGridHtml = '';
  if (metrics.length === 0) {
    metricsGridHtml = `
      <div class="placeholder-card" style="padding: 24px; grid-column: 1 / -1;">
        <div class="placeholder-icon">📈</div>
        <div class="placeholder-title" style="font-size: 14px;">No Metric Series Found</div>
        <p class="placeholder-desc" style="font-size: 12px;">This scenario contains zero metric streams.</p>
      </div>
    `;
  } else {
    metricsGridHtml = metrics.map((m) => renderMetricCard(m)).join('');
  }

  // Render Health Monitor
  const healthHtml = renderHealthMonitor(healthSignals, info.service);

  // Render Deployment Evidence
  const deploymentsHtml = renderDeploymentsPanel(deployments, detectedAt);

  // Render Log Explorer
  const logsHtml = renderLogExplorer(logs);

  container.innerHTML = `
    <div class="telemetry-workspace">
      
      <!-- Incident Overview Header Banner -->
      <div class="pane-card" style="background: linear-gradient(135deg, rgba(21, 31, 50, 0.9), rgba(16, 23, 38, 0.8)); border-color: rgba(6, 182, 212, 0.3);">
        <div class="pane-header" style="border-bottom: none; padding-bottom: 0;">
          <div class="pane-title-group">
            <span class="badge badge-critical" style="font-size: 12px; padding: 4px 10px;">
              ${String(info.severity).replace('SEV1_', '').replace('SEV2_', '')}
            </span>
            <span class="pane-title" style="font-size: 18px;">${info.title}</span>
          </div>
          <span class="badge badge-info" style="font-size: 11px;">#${info.key}</span>
        </div>

        <div style="display: flex; flex-wrap: wrap; gap: 16px; margin-top: 12px; font-size: 12px; color: var(--text-secondary);">
          <div><strong style="color:var(--text-muted);">AFFECTED SERVICE:</strong> <span style="color:var(--accent-cyan); font-weight:600;">${info.service}</span></div>
          <div><strong style="color:var(--text-muted);">ENVIRONMENT:</strong> <span class="font-mono">gcp-prod-us-central1</span></div>
          <div><strong style="color:var(--text-muted);">STATUS:</strong> <span class="badge badge-warning" style="font-size:10px; padding:2px 6px;">INVESTIGATING</span></div>
          ${detectedAt ? `<div><strong style="color:var(--text-muted);">DETECTED AT:</strong> <span class="font-mono">${new Date(detectedAt).toUTCString()}</span></div>` : ''}
        </div>

        ${info.impact ? `
          <div style="margin-top: 10px; padding: 8px 12px; background: rgba(0,0,0,0.3); border-radius: var(--radius-sm); font-size: 12px; color: #cbd5e1; line-height: 1.5;">
            <strong>Impact Assessment:</strong> ${info.impact}
          </div>
        ` : ''}
      </div>

      <!-- Section 1: Golden Signal Resource & Service Metrics -->
      <div>
        <div class="section-title-bar">
          <div class="section-heading">
            <span>📈</span>
            <span>Golden Signals & Resource Metrics</span>
          </div>
          <span class="section-subtitle">Real-time correlated time-series data</span>
        </div>
        <div class="metrics-grid">
          ${metricsGridHtml}
        </div>
      </div>

      <!-- Section 2: Service Health Monitor -->
      <div>
        <div class="section-title-bar">
          <div class="section-heading">
            <span>🩺</span>
            <span>Service Health & Synthetic Probes</span>
          </div>
          <span class="section-subtitle">${healthSignals.length} Probes Monitored</span>
        </div>
        ${healthHtml}
      </div>

      <!-- Section 3: Deployment & Change Evidence -->
      <div>
        <div class="section-title-bar">
          <div class="section-heading">
            <span>🚀</span>
            <span>Deployment & Configuration Events</span>
          </div>
          <span class="section-subtitle">${deployments.length} Change Events</span>
        </div>
        ${deploymentsHtml}
      </div>

      <!-- Section 4: Correlated Log Evidence Explorer -->
      <div>
        <div class="section-title-bar">
          <div class="section-heading">
            <span>📜</span>
            <span>Application & Container Log Evidence</span>
          </div>
          <span class="section-subtitle">${logs.length} Total Correlated Records</span>
        </div>
        <div id="log-explorer-container">
          ${logsHtml}
        </div>
      </div>

    </div>
  `;

  // Attach Log Explorer Event Handlers
  const rebindLogs = () => {
    const logContainer = document.getElementById('log-explorer-container');
    if (logContainer) {
      logContainer.innerHTML = renderLogExplorer(logs);
      initLogExplorerEvents(logs, rebindLogs);
    }
  };
  initLogExplorerEvents(logs, rebindLogs);
}
