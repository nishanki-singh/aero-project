/**
 * AERO Lightweight SVG Metrics Chart Component
 * High-performance browser-native time-series visualization with tooltips, gradients, and thresholds.
 */

/**
 * Format ISO timestamp to readable UTC time (HH:mm:ss).
 * @param {string|Date} ts 
 * @returns {string}
 */
export function formatTime(ts) {
  const d = new Date(ts);
  return d.toLocaleTimeString('en-US', { hour12: false, timeZone: 'UTC' });
}

/**
 * Render an interactive SVG line chart for a MetricSeries object.
 * @param {object} metricSeries { metric_name, service_name, unit, points, labels }
 * @param {object} options { height: number, isCritical: boolean, threshold: number|null }
 * @returns {string} HTML string containing the complete metric card and SVG chart
 */
export function renderMetricCard(metricSeries, options = {}) {
  if (!metricSeries || !metricSeries.points || metricSeries.points.length === 0) {
    return `
      <div class="metric-card">
        <div class="metric-header">
          <div class="metric-title-group">
            <span class="metric-name">${metricSeries?.metric_name || 'Metric'}</span>
            <span class="metric-service-tag">${metricSeries?.service_name || 'Service'}</span>
          </div>
          <span class="badge badge-warning">No Signal</span>
        </div>
        <div class="placeholder-card" style="padding: 20px; border-style: dotted;">
          <p class="placeholder-desc" style="font-size: 11px;">No time-series data points available for this signal.</p>
        </div>
      </div>
    `;
  }

  const points = metricSeries.points;
  const unit = metricSeries.unit || '';
  const values = points.map((p) => Number(p.value));
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const latestVal = values[values.length - 1];
  const avgVal = values.reduce((a, b) => a + b, 0) / values.length;

  // Determine if value represents a critical/warning condition
  const isPercent = unit.toLowerCase().includes('percent') || unit === '%';
  const isErrorRate = metricSeries.metric_name.includes('error_rate') || metricSeries.metric_name.includes('failure');
  const isUtilization = metricSeries.metric_name.includes('utilization') || metricSeries.metric_name.includes('memory') || metricSeries.metric_name.includes('cpu');

  let statusClass = '';
  if (isErrorRate && maxVal > 5) {
    statusClass = 'critical';
  } else if (isUtilization && maxVal > 85) {
    statusClass = 'critical';
  } else if (isUtilization && maxVal > 70) {
    statusClass = 'warning';
  } else if (options.isCritical) {
    statusClass = 'critical';
  }

  // Chart dimensions & scaling
  const width = 360;
  const height = options.height || 110;
  const padding = { top: 12, right: 12, bottom: 20, left: 34 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  const effectiveMin = minVal === maxVal ? Math.max(0, minVal - 5) : Math.min(0, minVal);
  const effectiveMax = minVal === maxVal ? maxVal + 5 : maxVal * 1.15;
  const valRange = effectiveMax - effectiveMin || 1;

  // Generate SVG coordinates
  const coords = points.map((p, i) => {
    const x = padding.left + (i / (points.length - 1 || 1)) * chartW;
    const y = padding.top + chartH - ((p.value - effectiveMin) / valRange) * chartH;
    return { x, y, timestamp: p.timestamp, value: p.value };
  });

  const pathD = coords.reduce((acc, c, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`, '');
  const areaD = `${pathD} L ${coords[coords.length - 1].x.toFixed(1)} ${(padding.top + chartH).toFixed(1)} L ${coords[0].x.toFixed(1)} ${(padding.top + chartH).toFixed(1)} Z`;

  // Grid lines
  const gridY1 = padding.top;
  const gridY2 = padding.top + chartH / 2;
  const gridY3 = padding.top + chartH;

  const startTimeStr = formatTime(points[0].timestamp);
  const endTimeStr = formatTime(points[points.length - 1].timestamp);

  // Generate unique ID for SVG gradients
  const chartId = `chart-${metricSeries.metric_name.replace(/[^a-zA-Z0-9]/g, '_')}`;

  // Interactive circles
  const pointElements = coords.map((c) => `
    <circle 
      class="chart-point" 
      cx="${c.x.toFixed(1)}" 
      cy="${c.y.toFixed(1)}" 
      r="2.5" 
      data-time="${formatTime(c.timestamp)}" 
      data-val="${c.value.toFixed(2)} ${unit}"
      onmouseenter="window.showChartTooltip(event, '${formatTime(c.timestamp)}', '${c.value.toFixed(2)} ${unit}')"
      onmouseleave="window.hideChartTooltip()"
    />
  `).join('');

  return `
    <div class="metric-card" id="card-${chartId}">
      <div class="metric-header">
        <div class="metric-title-group">
          <span class="metric-name">${metricSeries.metric_name}</span>
          <span class="metric-service-tag">${metricSeries.service_name}</span>
        </div>
        <div class="metric-stats-row">
          <span class="metric-current-val ${statusClass}">${latestVal.toFixed(1)}</span>
          <span class="metric-unit">${unit}</span>
        </div>
      </div>

      <div class="chart-container">
        <svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
          <defs>
            <linearGradient id="grad-cyan-${chartId}" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#06b6d4" stop-opacity="0.4" />
              <stop offset="100%" stop-color="#06b6d4" stop-opacity="0.0" />
            </linearGradient>
            <linearGradient id="grad-crit-${chartId}" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#ef4444" stop-opacity="0.45" />
              <stop offset="100%" stop-color="#ef4444" stop-opacity="0.0" />
            </linearGradient>
          </defs>

          <!-- Grid Lines -->
          <line class="chart-grid-line" x1="${padding.left}" y1="${gridY1}" x2="${width - padding.right}" y2="${gridY1}" />
          <line class="chart-grid-line" x1="${padding.left}" y1="${gridY2}" x2="${width - padding.right}" y2="${gridY2}" />
          <line class="chart-grid-line" x1="${padding.left}" y1="${gridY3}" x2="${width - padding.right}" y2="${gridY3}" />

          <!-- Axis Labels -->
          <text class="chart-axis-text" x="${padding.left - 4}" y="${gridY1 + 3}" text-anchor="end">${effectiveMax.toFixed(0)}</text>
          <text class="chart-axis-text" x="${padding.left - 4}" y="${gridY2 + 3}" text-anchor="end">${((effectiveMax + effectiveMin) / 2).toFixed(0)}</text>
          <text class="chart-axis-text" x="${padding.left - 4}" y="${gridY3 + 3}" text-anchor="end">${effectiveMin.toFixed(0)}</text>

          <text class="chart-axis-text" x="${padding.left}" y="${height - 2}" text-anchor="start">${startTimeStr}</text>
          <text class="chart-axis-text" x="${width - padding.right}" y="${height - 2}" text-anchor="end">${endTimeStr}</text>

          <!-- Area & Line -->
          <path class="chart-area ${statusClass}" d="${areaD}" fill="url(#${statusClass === 'critical' ? 'grad-crit-' + chartId : 'grad-cyan-' + chartId})" />
          <path class="chart-line ${statusClass}" d="${pathD}" />

          <!-- Hover Points -->
          ${pointElements}
        </svg>
      </div>

      <div style="display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--border-subtle); padding-top: 8px;">
        <div style="display: flex; gap: 6px;">
          <span class="metric-stat-pill">Min: ${minVal.toFixed(1)} ${unit}</span>
          <span class="metric-stat-pill">Max: ${maxVal.toFixed(1)} ${unit}</span>
          <span class="metric-stat-pill">Avg: ${avgVal.toFixed(1)} ${unit}</span>
        </div>
        <span class="font-mono" style="font-size: 10px; color: var(--text-muted);">${points.length} samples</span>
      </div>
    </div>
  `;
}

// Global chart tooltip handler
if (typeof window !== 'undefined') {
  window.showChartTooltip = function(event, time, val) {
    let tooltip = document.getElementById('aero-chart-tooltip');
    if (!tooltip) {
      tooltip = document.createElement('div');
      tooltip.id = 'aero-chart-tooltip';
      tooltip.className = 'chart-tooltip';
      document.body.appendChild(tooltip);
    }
    tooltip.innerHTML = `<strong>${val}</strong> <span style="color:var(--text-muted); font-size:10px;">@ ${time} UTC</span>`;
    tooltip.style.left = `${event.pageX}px`;
    tooltip.style.top = `${event.pageY}px`;
    tooltip.style.display = 'block';
  };

  window.hideChartTooltip = function() {
    const tooltip = document.getElementById('aero-chart-tooltip');
    if (tooltip) tooltip.style.display = 'none';
  };
}
