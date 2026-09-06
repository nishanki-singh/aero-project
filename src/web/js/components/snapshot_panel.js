/**
 * AERO Stage 4C: Point-in-Time System Snapshot Component
 * Renders discretized system operational state at a specific replay timestamp.
 */

import { formatRelativeTime, formatUtcTime } from './timeline_event.js';

// Health status badge class mapping
const HEALTH_STATUS_BADGES = {
  HEALTHY: 'badge-healthy',
  RECOVERING: 'badge-info',
  DEGRADED: 'badge-warning',
  CRITICAL: 'badge-critical',
  UNHEALTHY: 'badge-critical'
};

/**
 * Render point-in-time operational snapshot card HTML.
 * @param {object|null} snapshot SystemReplaySnapshot object
 * @param {string|Date} windowStart Window start timestamp
 * @param {number} currentStep Current step index
 * @param {number} totalSteps Total steps in series
 * @returns {string} HTML string
 */
export function renderSnapshotPanel(snapshot, windowStart, currentStep = 0, totalSteps = 1) {
  if (!snapshot) {
    return `
      <div class="snapshot-card">
        <div class="snapshot-header">
          <div class="snapshot-time-box">
            <span class="snapshot-rel-time">--:--:--</span>
            <span class="snapshot-utc-time">No active replay snapshot</span>
          </div>
          <span class="badge badge-info">AWAITING DATA</span>
        </div>
        <div class="empty-timeline-state" style="padding: 20px;">
          <p>Replay data not initialized.</p>
        </div>
      </div>
    `;
  }

  const relTime = formatRelativeTime(snapshot.timestamp, windowStart);
  const utcTime = formatUtcTime(snapshot.timestamp);
  const statusStr = (snapshot.health_status || 'HEALTHY').toUpperCase();
  const badgeClass = HEALTH_STATUS_BADGES[statusStr] || 'badge-info';

  // Format primary metric name for clean display
  let metricLabel = 'Primary Metric';
  let metricDisplayVal = '--';
  let metricUnit = '';
  if (snapshot.primary_metric_name) {
    const parts = snapshot.primary_metric_name.split('/');
    metricLabel = parts[parts.length - 1].replace(/_/g, ' ').toUpperCase();
    metricDisplayVal = snapshot.primary_metric_value !== null ? Number(snapshot.primary_metric_value).toFixed(1) : '--';
    metricUnit = snapshot.primary_metric_unit || '';
  }

  // Annotation banner if available
  const annotationHtml = snapshot.active_annotation ? `
    <div class="snapshot-annotation-banner">
      <span class="annotation-icon">⚡</span>
      <div>
        <strong style="color: var(--accent-cyan); font-family: var(--font-mono); font-size: 11px;">POINT-IN-TIME EVENT:</strong>
        <div>${escapeHtml(snapshot.active_annotation)}</div>
      </div>
    </div>
  ` : '';

  // Sample error log snippet if errors exist
  const errorLogHtml = snapshot.active_error_count > 0 && snapshot.sample_error_log ? `
    <div class="snapshot-error-log-box">
      <div class="error-log-header">
        <span>⚠️ ${snapshot.active_error_count} Error Logs Captured in Interval</span>
        <span>${snapshot.service_name}</span>
      </div>
      <div class="error-log-text">${escapeHtml(snapshot.sample_error_log)}</div>
    </div>
  ` : `
    <div style="padding: 8px 12px; background: rgba(0,0,0,0.2); border-radius: var(--radius-sm); font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); display: flex; justify-content: space-between;">
      <span>Active Error Logs: 0</span>
      <span style="color: var(--status-healthy);">Baseline Clear</span>
    </div>
  `;

  const isDegradedOrCritical = ['DEGRADED', 'CRITICAL', 'UNHEALTHY'].includes(statusStr);

  return `
    <div class="snapshot-card">
      <div class="snapshot-header">
        <div class="snapshot-time-box">
          <div class="snapshot-rel-time">
            <span>⏱️ ${relTime}</span>
          </div>
          <div class="snapshot-utc-time">${utcTime} (Step ${currentStep + 1} of ${totalSteps})</div>
        </div>
        <span class="badge ${badgeClass}" style="font-size: 12px; padding: 4px 8px;">
          <span class="badge-dot ${isDegradedOrCritical ? 'pulse' : ''}"></span>
          <span>${statusStr}</span>
        </span>
      </div>

      ${annotationHtml}

      <!-- 4-Tile State Signals Grid -->
      <div class="snapshot-signals-grid">
        <!-- Error Rate Tile -->
        <div class="snapshot-signal-tile">
          <div class="signal-tile-title">
            <span>Error Rate</span>
            <span>🚨</span>
          </div>
          <div class="signal-tile-value" style="color: ${snapshot.error_rate_pct > 0 ? 'var(--status-critical)' : 'var(--status-healthy)'}">
            ${Number(snapshot.error_rate_pct || 0).toFixed(1)}<span class="signal-tile-unit">%</span>
          </div>
          <div class="signal-tile-status" style="color: ${snapshot.error_rate_pct > 0 ? 'var(--status-critical)' : 'var(--text-muted)'}">
            ${snapshot.error_rate_pct > 0 ? 'Elevated' : 'Normal'}
          </div>
        </div>

        <!-- Latency P99 Tile -->
        <div class="snapshot-signal-tile">
          <div class="signal-tile-title">
            <span>P99 Latency</span>
            <span>⚡</span>
          </div>
          <div class="signal-tile-value" style="color: ${snapshot.latency_p99_ms > 500 ? 'var(--status-warning)' : 'var(--text-primary)'}">
            ${Math.round(snapshot.latency_p99_ms || 0)}<span class="signal-tile-unit">ms</span>
          </div>
          <div class="signal-tile-status" style="color: ${snapshot.latency_p99_ms > 500 ? 'var(--status-warning)' : 'var(--text-muted)'}">
            ${snapshot.latency_p99_ms > 1000 ? 'Severe Latency' : (snapshot.latency_p99_ms > 300 ? 'Elevated' : 'Healthy')}
          </div>
        </div>

        <!-- Primary Bottleneck Metric Tile -->
        <div class="snapshot-signal-tile">
          <div class="signal-tile-title">
            <span>${metricLabel}</span>
            <span>📊</span>
          </div>
          <div class="signal-tile-value" style="color: var(--accent-cyan);">
            ${metricDisplayVal}<span class="signal-tile-unit">${metricUnit}</span>
          </div>
          <div class="signal-tile-status" style="color: var(--text-muted); font-size: 9px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            ${snapshot.primary_metric_name || 'Resource Metric'}
          </div>
        </div>

        <!-- Active Error Count Tile -->
        <div class="snapshot-signal-tile">
          <div class="signal-tile-title">
            <span>Interval Errors</span>
            <span>📜</span>
          </div>
          <div class="signal-tile-value" style="color: ${snapshot.active_error_count > 0 ? 'var(--status-critical)' : 'var(--text-muted)'}">
            ${snapshot.active_error_count}
          </div>
          <div class="signal-tile-status" style="color: ${snapshot.active_error_count > 0 ? 'var(--status-critical)' : 'var(--status-healthy)'}">
            ${snapshot.active_error_count > 0 ? 'Active Failures' : '0 Log Errors'}
          </div>
        </div>
      </div>

      <!-- Sample Error Log Drawer -->
      ${errorLogHtml}
    </div>
  `;
}

/**
 * HTML escaper utility.
 * @param {string} str 
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
