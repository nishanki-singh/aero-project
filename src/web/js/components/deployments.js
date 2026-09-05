/**
 * AERO Deployment & Change Evidence Component
 * Visualizes code rollouts, configuration shifts, and temporal correlation with incident onset.
 */

/**
 * Format ISO timestamp to readable UTC date/time.
 * @param {string|Date} ts 
 * @returns {string}
 */
function formatDeployTime(ts) {
  const d = new Date(ts);
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'UTC'
  }) + ' UTC';
}

/**
 * Render the Deployment / Change Evidence panel.
 * @param {Array<object>} deployments Array of DeploymentEvent
 * @param {string|null} detectedAt Incident detection timestamp ISO string
 * @returns {string} HTML string
 */
export function renderDeploymentsPanel(deployments = [], detectedAt = null) {
  const count = Array.isArray(deployments) ? deployments.length : 0;
  const onsetTime = detectedAt ? new Date(detectedAt).getTime() : null;

  if (count === 0) {
    return `
      <div class="pane-card deployment-card">
        <div class="pane-header">
          <div class="pane-title-group">
            <span class="pane-title">Deployment & Configuration Changes</span>
          </div>
          <span class="badge badge-info">0 Deployments</span>
        </div>
        <div class="placeholder-card" style="padding: 24px 16px; border-style: solid; border-color: var(--border-subtle);">
          <div class="placeholder-icon" style="background: rgba(255,255,255,0.05); border-color: var(--border-subtle); color: var(--text-muted);">📦</div>
          <div class="placeholder-title" style="font-size: 14px; color: var(--text-secondary);">No Recent Deployments Detected</div>
          <p class="placeholder-desc" style="font-size: 12px; max-width: 440px;">
            Zero code releases or configuration rollouts occurred during this observation window. Incident onset is driven by external/upstream workload conditions.
          </p>
        </div>
      </div>
    `;
  }

  const itemsHtml = deployments.map((dep, idx) => {
    const depTime = new Date(dep.timestamp).getTime();
    const isPreIncident = onsetTime ? depTime <= onsetTime : true;

    return `
      <div class="deployment-item ${isPreIncident ? 'onset-trigger' : ''}" id="deploy-item-${idx}">
        <div class="deployment-info">
          <div class="deployment-title-row">
            <span class="badge ${isPreIncident ? 'badge-warning' : 'badge-info'}">
              ${isPreIncident ? '⚠️ SUSPECT CHANGE · Pre-Incident' : 'ℹ️ Change Event'}
            </span>
            <span class="deployment-version">${dep.version || 'v1.0.0'}</span>
            <span class="deployment-commit">${dep.commit_hash || 'HEAD'}</span>
          </div>

          <div class="deployment-summary-text">
            <strong>${dep.service_name || 'Service'}:</strong> ${dep.change_summary || 'Deployment update'}
          </div>

          <div class="deployment-meta-row">
            <span>🕒 ${formatDeployTime(dep.timestamp)}</span>
            <span>👤 ${dep.deployed_by || 'ci-cd-bot'}</span>
            <span>🌐 ${dep.environment || 'production'}</span>
          </div>
        </div>
      </div>
    `;
  }).join('');

  return `
    <div class="pane-card deployment-card">
      <div class="pane-header">
        <div class="pane-title-group">
          <span class="pane-title">Deployment & Configuration Evidence</span>
        </div>
        <span class="badge badge-warning">${count} Change ${count === 1 ? 'Event' : 'Events'}</span>
      </div>

      <div class="deployment-list">
        ${itemsHtml}
      </div>
    </div>
  `;
}
