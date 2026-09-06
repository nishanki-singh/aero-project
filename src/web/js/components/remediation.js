/**
 * AERO Safe Remediation Workspace Component
 * Displays human-in-the-loop remediation checklist, verification metrics, rollback plan, and dry-run console.
 */

import { store } from '../state.js';
import { renderDryRunConsole } from './dry_run_console.js';

/**
 * Render complete Safe Remediation workspace.
 * @param {HTMLElement} container 
 */
export function renderRemediationWorkspace(container) {
  if (!container) return;

  const state = store.getState();
  const diagData = state.activeDiagnosisData;

  if (!diagData || !diagData.report) {
    container.innerHTML = `
      <div class="pane-card">
        <div class="pane-header">
          <div class="pane-title-group">
            <span class="pane-title">Safe Remediation & Simulation</span>
          </div>
          <span class="badge badge-warning">Loading Remediation Plan</span>
        </div>
        <div class="placeholder-card" style="padding: 40px 20px;">
          <div class="placeholder-icon">⚙️</div>
          <div class="placeholder-title">Formulating Remediation Plan...</div>
          <p class="placeholder-desc">Deriving evidence-backed mitigation steps and rollback contingency.</p>
        </div>
      </div>
    `;
    return;
  }

  const report = diagData.report;
  const rem = report.recommended_remediation || {
    immediate_steps: ['Inspect service logs and verify cluster status'],
    dry_run_command: 'gcloud run services update service --dry-run',
    verification_metric: 'Health check status returns to HEALTHY',
    rollback_plan: 'Revert deployment to previous stable revision'
  };
  const steps = rem.immediate_steps || [];

  container.innerHTML = `
    <div class="remediation-workspace">
      
      <!-- Top Prominent Safety Guarantee Banner -->
      <div class="safety-banner-simulation">
        <div class="safety-banner-left">
          <span class="safety-shield-icon">🛡️</span>
          <div>
            <div class="safety-banner-title">SIMULATION ONLY — SAFE REMEDIATION GUARDRAIL</div>
            <div class="safety-banner-desc">
              All commands and operational workflows below are strictly simulated in-browser. Zero subprocess execution, zero mutation to GCP or Kubernetes.
            </div>
          </div>
        </div>
        <span class="safety-badge-immutable">SANDBOXED REHEARSAL</span>
      </div>

      <!-- Main Remediation Grid -->
      <div class="remediation-main-grid">
        
        <!-- Left: Actionable Human-in-the-Loop Remediation Plan -->
        <div class="remediation-plan-card">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div class="remediation-section-title">
              <span>📋</span>
              <span>Mitigation Action Checklist</span>
            </div>
            <span class="badge badge-info">${steps.length} Steps Recommended</span>
          </div>

          <div class="remediation-step-list">
            ${steps.map((step, idx) => `
              <div class="remediation-step-item">
                <div class="remediation-step-num">${idx + 1}</div>
                <div>${escapeHtml(step)}</div>
              </div>
            `).join('')}
          </div>

          <div class="remediation-meta-block" style="border-left: 3px solid #10b981;">
            <span class="remediation-meta-label">Verification Target Metric</span>
            <div class="remediation-meta-val" style="color: #34d399; font-weight: 500;">
              ${escapeHtml(rem.verification_metric)}
            </div>
          </div>

          <div class="remediation-meta-block" style="border-left: 3px solid #f59e0b;">
            <span class="remediation-meta-label">Contingency Rollback Plan</span>
            <div class="remediation-meta-val" style="color: #fbbf24;">
              ${escapeHtml(rem.rollback_plan)}
            </div>
          </div>

          ${report.relevant_runbook ? `
            <div class="remediation-meta-block" style="border-left: 3px solid #38bdf8;">
              <span class="remediation-meta-label">Retrieved SRE Runbook</span>
              <div class="remediation-meta-val">
                <strong>${escapeHtml(report.relevant_runbook.title)}</strong>: ${escapeHtml(report.relevant_runbook.pertinent_section)}
              </div>
            </div>
          ` : ''}

        </div>

        <!-- Right: Simulation-Only Dry Run Terminal Console -->
        <div id="dry-run-console-embed"></div>

      </div>

    </div>
  `;

  // Render Dry Run Terminal
  const dryRunContainer = container.querySelector('#dry-run-console-embed');
  if (dryRunContainer) {
    renderDryRunConsole(dryRunContainer, rem, report.service_name);
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
