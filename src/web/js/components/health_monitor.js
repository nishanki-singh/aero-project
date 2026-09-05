/**
 * AERO Service Health Monitor Component
 * Compact health observation dashboard displaying status breakdown, latency P99, and error rate indicators.
 */

/**
 * Render the compact Service Health Monitor view.
 * @param {Array<object>} healthSignals Array of ServiceHealth records
 * @param {string} affectedService Primary service name
 * @returns {string} HTML string
 */
export function renderHealthMonitor(healthSignals = [], affectedService = 'Service') {
  if (!Array.isArray(healthSignals) || healthSignals.length === 0) {
    return `
      <div class="pane-card">
        <div class="pane-header">
          <div class="pane-title-group">
            <span class="pane-title">Service Health Monitor</span>
          </div>
          <span class="badge badge-warning">No Checks</span>
        </div>
        <div class="placeholder-card" style="padding: 20px;">
          <p class="placeholder-desc" style="font-size: 11px;">No active health check signals recorded.</p>
        </div>
      </div>
    `;
  }

  const total = healthSignals.length;
  let healthyCount = 0;
  let degradedCount = 0;
  let unhealthyCount = 0;

  let maxLatency = 0;
  let maxErrorRate = 0;
  let latestSignal = healthSignals[healthSignals.length - 1];

  healthSignals.forEach((h) => {
    const st = String(h.status || '').toUpperCase();
    if (st === 'HEALTHY') healthyCount++;
    else if (st === 'DEGRADED') degradedCount++;
    else if (st === 'UNHEALTHY') unhealthyCount++;

    if (h.latency_p99_ms > maxLatency) maxLatency = h.latency_p99_ms;
    if (h.error_rate_pct > maxErrorRate) maxErrorRate = h.error_rate_pct;
  });

  let overallStatus = 'HEALTHY';
  let badgeClass = 'badge-healthy';
  if (unhealthyCount > 0) {
    overallStatus = 'UNHEALTHY';
    badgeClass = 'badge-critical';
  } else if (degradedCount > 0) {
    overallStatus = 'DEGRADED';
    badgeClass = 'badge-warning';
  }

  return `
    <div class="pane-card">
      <div class="pane-header">
        <div class="pane-title-group">
          <span class="pane-title">Service Health Monitor (${affectedService})</span>
        </div>
        <span class="badge ${badgeClass}">${overallStatus}</span>
      </div>

      <div class="health-monitor-grid">
        <div class="health-stat-card">
          <span class="health-stat-label">Operational State</span>
          <span class="health-stat-value ${overallStatus.toLowerCase()}">${overallStatus}</span>
          <span class="font-mono" style="font-size: 10px; color: var(--text-muted);">
            ${unhealthyCount} unhealthy · ${degradedCount} degraded · ${healthyCount} healthy
          </span>
        </div>

        <div class="health-stat-card">
          <span class="health-stat-label">P99 Latency (Peak)</span>
          <span class="health-stat-value ${maxLatency > 1000 ? 'unhealthy' : (maxLatency > 500 ? 'degraded' : 'healthy')}">
            ${maxLatency.toFixed(1)} ms
          </span>
          <span class="font-mono" style="font-size: 10px; color: var(--text-muted);">
            Latest: ${latestSignal.latency_p99_ms.toFixed(1)} ms
          </span>
        </div>

        <div class="health-stat-card">
          <span class="health-stat-label">Error Rate (Peak)</span>
          <span class="health-stat-value ${maxErrorRate > 5 ? 'unhealthy' : (maxErrorRate > 1 ? 'degraded' : 'healthy')}">
            ${maxErrorRate.toFixed(1)}%
          </span>
          <span class="font-mono" style="font-size: 10px; color: var(--text-muted);">
            Latest: ${latestSignal.error_rate_pct.toFixed(1)}%
          </span>
        </div>

        <div class="health-stat-card">
          <span class="health-stat-label">Checks Sampled</span>
          <span class="health-stat-value font-mono" style="font-size: 18px; color: var(--accent-cyan-light);">
            ${total} Probes
          </span>
          <span class="font-mono" style="font-size: 10px; color: var(--text-muted);">
            Active synthetic probe series
          </span>
        </div>
      </div>
    </div>
  `;
}
