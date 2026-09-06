/**
 * AERO Stage 4C: Timeline Event / Milestone Component
 * Renders individual chronological milestone event cards with observed telemetry evidence context.
 */

// Milestone Icon Mapping
const MILESTONE_ICONS = {
  ANOMALY_ONSET: '⚡',
  ALERT_FIRED: '🚨',
  TRIAGE_START: '🔍',
  PEAK_IMPACT: '💥',
  MITIGATION_APPLIED: '🛠️',
  RECOVERY_VERIFIED: '✅',
  RESOLVED: '🏁'
};

// Milestone Badge Style Mapping
const MILESTONE_BADGE_CLASSES = {
  ANOMALY_ONSET: 'badge-warning',
  ALERT_FIRED: 'badge-critical',
  TRIAGE_START: 'badge-info',
  PEAK_IMPACT: 'badge-critical',
  MITIGATION_APPLIED: 'badge-info',
  RECOVERY_VERIFIED: 'badge-healthy',
  RESOLVED: 'badge-healthy'
};

// Signal Badge Style Mapping
const SIGNAL_BADGE_CLASSES = {
  DEPLOYMENT: 'badge-warning',
  METRIC: 'badge-info',
  LOG: 'badge-critical',
  HEALTH: 'badge-warning',
  ALERT: 'badge-critical',
  OPERATOR: 'badge-healthy'
};

/**
 * Format relative time in minutes & seconds from the start of the observation window.
 * @param {string|Date} timestamp 
 * @param {string|Date} startTime 
 * @returns {string} e.g. "T+00m 00s" or "+12m 30s"
 */
export function formatRelativeTime(timestamp, startTime) {
  if (!timestamp || !startTime) return 'T+00:00';
  const t = new Date(timestamp).getTime();
  const start = new Date(startTime).getTime();
  const diffSec = Math.max(0, Math.floor((t - start) / 1000));
  const mins = Math.floor(diffSec / 60);
  const secs = diffSec % 60;
  return `T+${String(mins).padStart(2, '0')}m ${String(secs).padStart(2, '0')}s`;
}

/**
 * Format UTC timestamp string.
 * @param {string|Date} timestamp 
 * @returns {string} e.g. "Aug 30 14:15:00 UTC"
 */
export function formatUtcTime(timestamp) {
  if (!timestamp) return '--:--:-- UTC';
  const d = new Date(timestamp);
  return d.toUTCString().replace('GMT', 'UTC');
}

/**
 * Render a single Timeline Milestone node HTML.
 * @param {object} milestone TimelineMilestone object
 * @param {number} index Index in milestone list
 * @param {string|Date} windowStart Window start timestamp
 * @param {boolean} isSelected Whether this card is expanded/selected
 * @returns {string} HTML string
 */
export function renderMilestoneItem(milestone, index, windowStart, isSelected = false) {
  const mType = milestone.milestone_type || 'ANOMALY_ONSET';
  const icon = MILESTONE_ICONS[mType] || '📌';
  const badgeClass = MILESTONE_BADGE_CLASSES[mType] || 'badge-info';
  const signalClass = SIGNAL_BADGE_CLASSES[milestone.source_signal] || 'badge-info';
  const relTime = formatRelativeTime(milestone.timestamp, windowStart);
  const utcTime = formatUtcTime(milestone.timestamp);

  const evidenceHtml = milestone.evidence_ref ? `
    <div class="milestone-evidence-box">
      <div class="evidence-header">
        <span>🔬 Observed Evidence Source [${milestone.source_signal}]</span>
        <span>Service: ${milestone.source_service}</span>
      </div>
      <div class="evidence-body">
        ${escapeHtml(milestone.evidence_ref)}
      </div>
      <button type="button" class="btn-jump-replay" data-timestamp="${milestone.timestamp}" title="Jump replay scrubber to this event">
        <span>▶ Jump Replay Here</span>
      </button>
    </div>
  ` : `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
      <span class="font-mono" style="font-size: 10px; color: var(--text-muted);">Source: ${milestone.source_service} [${milestone.source_signal}]</span>
      <button type="button" class="btn-jump-replay" data-timestamp="${milestone.timestamp}" title="Jump replay scrubber to this event">
        <span>▶ Jump Replay Here</span>
      </button>
    </div>
  `;

  return `
    <div class="timeline-milestone-node" data-milestone-index="${index}">
      <div class="milestone-icon-dot type-${mType}">
        <span>${icon}</span>
      </div>
      <div class="milestone-card ${isSelected ? 'selected' : ''}" data-index="${index}">
        <div class="milestone-header">
          <div class="milestone-timing">
            <span class="milestone-rel-time">${relTime}</span>
            <span class="milestone-utc-time">${utcTime}</span>
          </div>
          <div class="milestone-tags">
            <span class="badge ${signalClass}">${milestone.source_signal}</span>
            <span class="badge ${badgeClass}">${mType.replace(/_/g, ' ')}</span>
          </div>
        </div>

        <div class="milestone-title">${escapeHtml(milestone.title)}</div>
        <div class="milestone-desc">${escapeHtml(milestone.description)}</div>

        ${evidenceHtml}
      </div>
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
