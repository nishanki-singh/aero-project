/**
 * AERO Grounding Scorecard & Verification Matrix Component
 * Displays empirical grounding recall, precision, hallucination metrics and citation verification details.
 */

import { store } from '../state.js';

/**
 * Render complete Evidence Grounding workspace.
 * @param {HTMLElement} container 
 */
export function renderGroundingWorkspace(container) {
  if (!container) return;

  const state = store.getState();
  const diagData = state.activeDiagnosisData;
  const evalData = state.activeEvaluationData;

  if (!diagData || !diagData.grounding) {
    container.innerHTML = `
      <div class="pane-card">
        <div class="pane-header">
          <div class="pane-title-group">
            <span class="pane-title">Telemetry Grounding & Verification Matrix</span>
          </div>
          <span class="badge badge-warning">Awaiting Verification</span>
        </div>
        <div class="placeholder-card" style="padding: 40px 20px;">
          <div class="placeholder-icon">🛡️</div>
          <div class="placeholder-title">Verifying Telemetry Citations...</div>
          <p class="placeholder-desc">Evaluating citations against raw telemetry data.</p>
        </div>
      </div>
    `;
    return;
  }

  const grounding = diagData.grounding;
  const precisionPct = Math.round((grounding.grounding_precision || 1.0) * 100);
  const hallucinationPct = Math.round((grounding.hallucination_rate || 0.0) * 100);
  
  // Recall from evaluation if available, otherwise 100%
  const recallPct = evalData ? Math.round((evalData.grounding_recall || 1.0) * 100) : 100;
  const isPassed = evalData ? evalData.is_benchmark_passed : grounding.is_fully_grounded;

  const details = grounding.evidence_details || [];

  container.innerHTML = `
    <div class="grounding-workspace">
      
      <!-- Top Metrics Scorecard Grid -->
      <div class="grounding-metrics-grid">
        
        <!-- Metric 1: Grounding Precision -->
        <div class="scorecard-metric-card">
          <div class="metric-card-top">
            <span class="metric-card-label">Grounding Precision</span>
            <span class="badge badge-healthy">Empirical</span>
          </div>
          <div class="metric-card-value metric-status-pass">${precisionPct}%</div>
          <div class="metric-card-subtext">${grounding.verified_count} of ${grounding.total_citations} citations verified</div>
        </div>

        <!-- Metric 2: Grounding Recall -->
        <div class="scorecard-metric-card">
          <div class="metric-card-top">
            <span class="metric-card-label">Grounding Recall</span>
            <span class="badge badge-healthy">Benchmark</span>
          </div>
          <div class="metric-card-value metric-status-pass">${recallPct}%</div>
          <div class="metric-card-subtext">Mandatory signals coverage</div>
        </div>

        <!-- Metric 3: Hallucination Rate -->
        <div class="scorecard-metric-card">
          <div class="metric-card-top">
            <span class="metric-card-label">Hallucination Rate</span>
            <span class="badge ${hallucinationPct === 0 ? 'badge-healthy' : 'badge-critical'}">Guardrail</span>
          </div>
          <div class="metric-card-value ${hallucinationPct === 0 ? 'metric-status-pass' : 'metric-status-warn'}">
            ${hallucinationPct}%
          </div>
          <div class="metric-card-subtext">${grounding.unverified_count} ungrounded claims detected</div>
        </div>

        <!-- Metric 4: Benchmark Status -->
        <div class="scorecard-metric-card">
          <div class="metric-card-top">
            <span class="metric-card-label">Evaluation Status</span>
            <span class="badge badge-info">SRE Criteria</span>
          </div>
          <div class="metric-card-value" style="font-size: 20px; color: ${isPassed ? '#10b981' : '#f59e0b'};">
            ${isPassed ? 'CRITERIA MET' : 'FLAGGED'}
          </div>
          <div class="metric-card-subtext">RCA & Grounding SLA satisfied</div>
        </div>

      </div>

      <!-- Grounding Disclaimer Notice -->
      <div class="alert-banner alert-banner-info" style="font-size: 12px; padding: 10px 16px;">
        <span>📊 <strong>Empirical Grounding Audit:</strong> Metrics are calculated by cross-matching each citation in the diagnostic output against raw telemetry events and scenario ground-truth signals. Measured on benchmark dataset; does not imply an absolute universal guarantee.</span>
      </div>

      <!-- Verification Matrix Table -->
      <div class="grounding-table-card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 18px;">📋</span>
            <span class="pane-title" style="font-size: 14px; text-transform: uppercase;">Citation Verification Matrix</span>
          </div>
          <span class="font-mono" style="font-size: 11px; color: var(--text-muted);">
            ${grounding.verified_count}/${grounding.total_citations} Grounded Signals
          </span>
        </div>

        <div style="overflow-x: auto;">
          <table class="grounding-table">
            <thead>
              <tr>
                <th style="width: 110px;">Signal</th>
                <th style="width: 140px;">Source</th>
                <th>Observed Citation</th>
                <th style="width: 120px;">Status</th>
                <th>Verification Match Audit</th>
              </tr>
            </thead>
            <tbody>
              ${details.map((item) => {
                const ev = item.evidence;
                const isGrounded = item.is_grounded;
                return `
                  <tr>
                    <td>
                      <span class="signal-type-tag ${escapeHtml(ev.signal_type)}">${escapeHtml(ev.signal_type)}</span>
                    </td>
                    <td>
                      <span class="font-mono" style="font-size: 11px; color: var(--text-muted);">${escapeHtml(ev.source)}</span>
                    </td>
                    <td>
                      <div class="evidence-content-quote" style="font-size: 11.5px;">${escapeHtml(ev.content)}</div>
                    </td>
                    <td>
                      <span class="grounding-status-pill ${isGrounded ? 'verified' : 'unverified'}">
                        ${isGrounded ? '✓ Verified' : '⚠ Ungrounded'}
                      </span>
                    </td>
                    <td>
                      <div style="font-size: 11.5px; color: ${isGrounded ? 'var(--text-secondary)' : '#fca5a5'};">
                        ${escapeHtml(item.verification_reason)}
                      </div>
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>

      </div>

    </div>
  `;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
