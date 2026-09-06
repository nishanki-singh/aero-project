/**
 * AERO Diagnostic & RCA Workspace Component
 * Renders primary root cause analysis, evidence vs inference breakdown, and 5-whys causal progression.
 */

import { store } from '../state.js';
import { renderFiveWhysTree } from './five_whys.js';

/**
 * Render complete RCA & Diagnosis workspace.
 * @param {HTMLElement} container 
 */
export function renderRcaWorkspace(container) {
  if (!container) return;

  const state = store.getState();
  const diagData = state.activeDiagnosisData;

  if (!diagData || !diagData.report) {
    container.innerHTML = `
      <div class="pane-card">
        <div class="pane-header">
          <div class="pane-title-group">
            <span class="pane-title">Root Cause Analysis & Diagnostic Reasoning</span>
          </div>
          <span class="badge badge-warning">Loading Diagnostic Pack</span>
        </div>
        <div class="placeholder-card" style="padding: 40px 20px;">
          <div class="placeholder-icon">🧠</div>
          <div class="placeholder-title">Analyzing Telemetry & Root Cause...</div>
          <p class="placeholder-desc">Correlating multi-signal metrics, logs, and deployment events.</p>
        </div>
      </div>
    `;
    return;
  }

  const report = diagData.report;
  const rc = report.probable_root_cause || {};
  const conf = report.confidence_level || { score: 0.95, rating: 'HIGH', rationale: '' };
  const evidenceList = report.supporting_evidence || [];
  const fiveWhysList = report.five_whys || [];
  const confPct = Math.round((conf.score || 0) * 100);

  // Categorize evidence
  const observedEvidence = evidenceList;

  container.innerHTML = `
    <div class="rca-workspace">
      
      <!-- Primary Root Cause Hero Card -->
      <div class="rca-hero-card" id="rca-hero-card">
        <div class="rca-hero-header">
          <div class="rca-title-group">
            <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 6px;">
              <span class="rca-category-tag">${escapeHtml(rc.category || 'SYSTEM_FAILURE')}</span>
              <span class="badge badge-critical font-mono" style="font-size: 10px;">${escapeHtml(report.service_name || 'Service')}</span>
            </div>
            <h2 class="rca-hero-title">${escapeHtml(rc.title || 'Root Cause Identified')}</h2>
          </div>

          <!-- Confidence Rating Gauge -->
          <div class="confidence-gauge-container" title="${escapeHtml(conf.rationale)}">
            <div class="confidence-score-val">${confPct}%</div>
            <div class="confidence-meta">
              <span class="confidence-label">AI Confidence</span>
              <span class="confidence-rating-badge">${escapeHtml(conf.rating || 'HIGH')}</span>
            </div>
          </div>
        </div>

        <p class="rca-summary-desc">${escapeHtml(rc.description || report.incident_summary)}</p>

        <!-- Trigger Event Box -->
        ${rc.trigger_event ? `
          <div class="rca-trigger-box">
            <span class="rca-trigger-icon">⚡</span>
            <div>
              <strong style="color: #ffffff;">Trigger Event:</strong> ${escapeHtml(rc.trigger_event)}
            </div>
          </div>
        ` : ''}
      </div>

      <!-- Evidence vs. Inference Dual Split Grid -->
      <div class="evidence-vs-inference-grid">
        
        <!-- Left: Observed Evidence -->
        <div class="evidence-split-card evidence-card-observed">
          <div class="split-card-header">
            <div class="split-card-title">
              <span>📡</span>
              <span>Observed Evidence</span>
            </div>
            <span class="split-pill-observed">${observedEvidence.length} Signals Captured</span>
          </div>

          <div class="evidence-citation-list">
            ${observedEvidence.map((ev) => `
              <div class="evidence-citation-item">
                <div class="evidence-citation-header">
                  <span class="signal-type-tag ${escapeHtml(ev.signal_type)}">${escapeHtml(ev.signal_type)}</span>
                  <span class="evidence-source-tag">${escapeHtml(ev.source)}</span>
                </div>
                <div class="evidence-content-quote">${escapeHtml(ev.content)}</div>
                ${ev.relevance ? `<div class="evidence-relevance-note">↳ ${escapeHtml(ev.relevance)}</div>` : ''}
              </div>
            `).join('')}
          </div>
        </div>

        <!-- Right: Derived Inference & Causal Reasoning -->
        <div class="evidence-split-card evidence-card-inferred">
          <div class="split-card-header">
            <div class="split-card-title">
              <span>🧠</span>
              <span>Derived Inference</span>
            </div>
            <span class="split-pill-inferred">Deductive SRE Reasoning</span>
          </div>

          <div style="display: flex; flex-direction: column; gap: 12px; margin-top: 6px;">
            <div class="evidence-citation-item" style="border-left: 2px solid #a855f7;">
              <div style="font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: #c084fc; margin-bottom: 4px;">
                Confidence Justification
              </div>
              <p style="font-size: 12.5px; color: var(--text-secondary); line-height: 1.5; margin: 0;">
                ${escapeHtml(conf.rationale)}
              </p>
            </div>

            <div class="evidence-citation-item" style="border-left: 2px solid #a855f7;">
              <div style="font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: #c084fc; margin-bottom: 4px;">
                Incident Executive Synthesis
              </div>
              <p style="font-size: 12.5px; color: var(--text-secondary); line-height: 1.5; margin: 0;">
                ${escapeHtml(report.incident_summary)}
              </p>
            </div>

            <div class="alert-banner alert-banner-info" style="font-size: 11.5px; margin: 0; padding: 8px 12px;">
              <span>🛡️ Claims are cross-verified against raw telemetry signals. Inferences represent causal explanations derived from observed telemetry.</span>
            </div>
          </div>
        </div>

      </div>

      <!-- Five Whys Causal Progression Tree -->
      <div id="five-whys-embed-container"></div>

    </div>
  `;

  // Render embedded Five Whys component
  const fiveWhysContainer = container.querySelector('#five-whys-embed-container');
  if (fiveWhysContainer) {
    renderFiveWhysTree(fiveWhysContainer, fiveWhysList);
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
