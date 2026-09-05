/**
 * AERO Log Evidence Explorer Component
 * Real-time searchable, filterable log explorer with severity badges and incident evidence highlighting.
 */

let activeLogState = {
  filterLevel: 'ALL',
  searchQuery: '',
  evidenceOnly: false,
  expandedLogIds: new Set()
};

/**
 * Format ISO timestamp to readable UTC time with milliseconds.
 * @param {string|Date} ts 
 * @returns {string}
 */
function formatLogTime(ts) {
  const d = new Date(ts);
  const time = d.toLocaleTimeString('en-US', { hour12: false, timeZone: 'UTC' });
  const ms = String(d.getUTCMilliseconds()).padStart(3, '0');
  return `${time}.${ms}`;
}

/**
 * Determine if a log entry represents primary incident evidence.
 * @param {object} log 
 * @returns {boolean}
 */
export function isEvidenceLog(log) {
  const lvl = String(log.log_level || '').toUpperCase();
  if (lvl === 'FATAL' || lvl === 'ERROR') return true;
  if (lvl === 'WARN') {
    const msg = (log.message || '').toLowerCase();
    if (msg.includes('connection') || msg.includes('pool') || msg.includes('threshold') || 
        msg.includes('deadlock') || msg.includes('drift') || msg.includes('timeout') ||
        msg.includes('exhaust') || msg.includes('oom') || msg.includes('latency')) {
      return true;
    }
  }
  return false;
}

/**
 * Filter log entries based on current search, level, and evidence toggle.
 * @param {Array<object>} logs 
 * @param {object} state 
 * @returns {Array<object>}
 */
export function filterLogs(logs, state) {
  if (!Array.isArray(logs)) return [];
  const query = (state.searchQuery || '').toLowerCase().trim();
  const level = (state.filterLevel || 'ALL').toUpperCase();
  const evidenceOnly = Boolean(state.evidenceOnly);

  return logs.filter((log) => {
    const logLvl = String(log.log_level || 'INFO').toUpperCase();

    // Level filter
    if (level !== 'ALL' && logLvl !== level) {
      return false;
    }

    // Evidence only filter
    if (evidenceOnly && !isEvidenceLog(log)) {
      return false;
    }

    // Text query match against message, service_name, trace_id, attributes
    if (query) {
      const msgMatch = (log.message || '').toLowerCase().includes(query);
      const srvMatch = (log.service_name || '').toLowerCase().includes(query);
      const traceMatch = (log.trace_id || '').toLowerCase().includes(query);
      const attrMatch = JSON.stringify(log.attributes || {}).toLowerCase().includes(query);
      if (!msgMatch && !srvMatch && !traceMatch && !attrMatch) {
        return false;
      }
    }

    return true;
  });
}

/**
 * Render the Log Evidence Explorer HTML.
 * @param {Array<object>} logs 
 * @returns {string}
 */
export function renderLogExplorer(logs = []) {
  const totalCount = logs.length;
  
  // Calculate severity breakdown
  const counts = {
    ALL: totalCount,
    FATAL: 0,
    ERROR: 0,
    WARN: 0,
    INFO: 0,
    DEBUG: 0
  };

  logs.forEach((l) => {
    const lvl = String(l.log_level || 'INFO').toUpperCase();
    if (counts[lvl] !== undefined) counts[lvl]++;
  });

  const filtered = filterLogs(logs, activeLogState);

  // Render log rows
  const rowsHtml = filtered.length === 0
    ? `
      <tr>
        <td colspan="4" style="text-align: center; padding: 36px 12px; color: var(--text-muted);">
          <div style="font-size: 20px; margin-bottom: 6px;">🔍</div>
          <div style="font-weight: 600;">No logs matching current filter</div>
          <div style="font-size: 11px; margin-top: 4px;">Try clearing search or selecting "ALL" severity levels.</div>
        </td>
      </tr>
    `
    : filtered.map((log, index) => {
        const isEv = isEvidenceLog(log);
        const lvl = String(log.log_level || 'INFO').toUpperCase();
        let badgeClass = 'badge-info';
        if (lvl === 'FATAL' || lvl === 'ERROR') badgeClass = 'badge-critical';
        else if (lvl === 'WARN') badgeClass = 'badge-warning';

        const rowId = `log-row-${index}`;
        const hasAttrs = log.attributes && Object.keys(log.attributes).length > 0;
        const hasTrace = Boolean(log.trace_id);
        const isExpanded = activeLogState.expandedLogIds.has(rowId);

        let attrsDetails = '';
        if (hasAttrs || hasTrace) {
          attrsDetails = `
            <div id="${rowId}-attrs" class="log-attrs-panel" style="display: ${isExpanded ? 'block' : 'none'};">
              ${hasTrace ? `<div><strong>Trace ID:</strong> <span class="font-mono" style="color:var(--accent-cyan);">${log.trace_id}</span></div>` : ''}
              ${hasAttrs ? `<div><strong>Attributes:</strong> <pre class="font-mono" style="margin-top:4px; font-size:10px; color:#e2e8f0;">${JSON.stringify(log.attributes, null, 2)}</pre></div>` : ''}
            </div>
          `;
        }

        return `
          <tr class="log-row ${isEv ? 'evidence-highlight' : ''}" id="${rowId}">
            <td class="log-time">${formatLogTime(log.timestamp)}</td>
            <td>
              <span class="badge ${badgeClass}" style="font-size: 10px; padding: 2px 6px;">
                ${lvl}
              </span>
            </td>
            <td class="log-service">${log.service_name || 'service'}</td>
            <td class="log-message">
              ${isEv ? '<span class="log-evidence-badge">EVIDENCE</span>' : ''}
              ${escapeHtml(log.message || '')}
              ${(hasAttrs || hasTrace) ? `
                <span class="log-attrs-toggle" onclick="window.toggleLogAttrs('${rowId}')">
                  ${isExpanded ? '▲ Hide context' : '▼ View context'}
                </span>
              ` : ''}
              ${attrsDetails}
            </td>
          </tr>
        `;
      }).join('');

  return `
    <div class="pane-card logs-card">
      <div class="pane-header">
        <div class="pane-title-group">
          <span class="pane-title">Correlated Log Evidence Explorer</span>
        </div>
        <span class="badge badge-info" id="log-count-badge">${filtered.length} / ${totalCount} Logs</span>
      </div>

      <!-- Log Explorer Toolbar -->
      <div class="logs-toolbar">
        <div class="logs-search-box">
          <span>🔍</span>
          <input 
            type="text" 
            id="log-search-input" 
            class="logs-search-input" 
            placeholder="Search log messages, services, traces..." 
            value="${escapeHtml(activeLogState.searchQuery)}"
          />
        </div>

        <div class="logs-filter-group" id="log-level-filters">
          <button type="button" class="filter-chip ${activeLogState.filterLevel === 'ALL' ? 'active' : ''}" data-level="ALL">
            ALL (${counts.ALL})
          </button>
          <button type="button" class="filter-chip fatal ${activeLogState.filterLevel === 'FATAL' ? 'active' : ''}" data-level="FATAL">
            FATAL (${counts.FATAL})
          </button>
          <button type="button" class="filter-chip error ${activeLogState.filterLevel === 'ERROR' ? 'active' : ''}" data-level="ERROR">
            ERROR (${counts.ERROR})
          </button>
          <button type="button" class="filter-chip warn ${activeLogState.filterLevel === 'WARN' ? 'active' : ''}" data-level="WARN">
            WARN (${counts.WARN})
          </button>
          <button type="button" class="filter-chip ${activeLogState.filterLevel === 'INFO' ? 'active' : ''}" data-level="INFO">
            INFO (${counts.INFO})
          </button>
        </div>

        <label class="filter-toggle-label">
          <input type="checkbox" id="log-evidence-toggle" ${activeLogState.evidenceOnly ? 'checked' : ''} />
          <span>Evidence Only</span>
        </label>
      </div>

      <!-- Logs Table -->
      <div class="logs-table-wrapper">
        <table class="logs-table">
          <thead>
            <tr>
              <th style="width: 90px;">Time (UTC)</th>
              <th style="width: 70px;">Level</th>
              <th style="width: 140px;">Service</th>
              <th>Message & Structured Evidence</th>
            </tr>
          </thead>
          <tbody id="logs-table-body">
            ${rowsHtml}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

/**
 * Escape HTML to prevent injection.
 * @param {string} str 
 * @returns {string}
 */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Initialize event handlers for Log Explorer.
 * @param {Array<object>} logs 
 * @param {Function} onFilterChange 
 */
export function initLogExplorerEvents(logs, onFilterChange) {
  const searchInput = document.getElementById('log-search-input');
  const levelChips = document.querySelectorAll('#log-level-filters .filter-chip');
  const evidenceToggle = document.getElementById('log-evidence-toggle');

  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      activeLogState.searchQuery = e.target.value;
      if (typeof onFilterChange === 'function') onFilterChange();
    });
  }

  levelChips.forEach((chip) => {
    chip.addEventListener('click', () => {
      const level = chip.dataset.level || 'ALL';
      activeLogState.filterLevel = level;
      if (typeof onFilterChange === 'function') onFilterChange();
    });
  });

  if (evidenceToggle) {
    evidenceToggle.addEventListener('change', (e) => {
      activeLogState.evidenceOnly = e.target.checked;
      if (typeof onFilterChange === 'function') onFilterChange();
    });
  }
}

// Global context expansion toggle
if (typeof window !== 'undefined') {
  window.toggleLogAttrs = function(rowId) {
    const el = document.getElementById(`${rowId}-attrs`);
    if (!el) return;
    if (activeLogState.expandedLogIds.has(rowId)) {
      activeLogState.expandedLogIds.delete(rowId);
      el.style.display = 'none';
    } else {
      activeLogState.expandedLogIds.add(rowId);
      el.style.display = 'block';
    }
  };
}
