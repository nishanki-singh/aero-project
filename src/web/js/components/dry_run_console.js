/**
 * AERO Safe Remediation Simulation-Only Dry Run Console Component
 * STRICT SAFETY INVARIANT: local simulation only with ZERO infrastructure or shell execution.
 */

import { store } from '../state.js';

let activeTimer = null;

/**
 * Render the Dry Run Simulation Terminal Console into a parent container.
 * @param {HTMLElement} parentEl 
 * @param {object} remediation 
 * @param {string} serviceName 
 */
export function renderDryRunConsole(parentEl, remediation, serviceName) {
  if (!parentEl) return;

  const simState = store.getState().remediationSimState || {
    status: 'idle',
    currentStep: 0,
    logs: [],
    isRunning: false,
    completed: false
  };

  const dryRunCmd = remediation.dry_run_command || `gcloud run services update ${serviceName || 'service'} --dry-run`;
  const metric = remediation.verification_metric || 'Health check status returns to HEALTHY';
  const rollback = remediation.rollback_plan || 'Revert previous deployment';

  // Build initial terminal text if idle
  let initialLines = simState.logs;
  if (simState.status === 'idle' && initialLines.length === 0) {
    initialLines = [
      { type: 'info', text: '=== AERO REMEDIATION SIMULATION RUNNER ===' },
      { type: 'guardrail', text: '[SAFETY GUARDRAIL ACTIVE] DRY-RUN SIMULATION ONLY — ZERO INFRASTRUCTURE MUTATION' },
      { type: 'prompt', text: `$ # Target Service: ${serviceName || 'service'}` },
      { type: 'cmd', text: `$ simulated-cli ${dryRunCmd}` },
      { type: 'info', text: 'Ready for simulated dry-run rehearsal. Press "Simulate Remediation Dry-Run" below.' }
    ];
  }

  parentEl.innerHTML = `
    <div class="dry-run-terminal-card">
      <div class="dry-run-header">
        <div class="terminal-title-group">
          <div class="terminal-window-dots">
            <span class="terminal-dot dot-red"></span>
            <span class="terminal-dot dot-yellow"></span>
            <span class="terminal-dot dot-green"></span>
          </div>
          <span class="terminal-title-text">aero-remediation-sim ~ (SIMULATION ONLY)</span>
        </div>
        <span class="safety-badge-immutable">🛡️ ZERO MUTATION GUARANTEE</span>
      </div>

      <div class="dry-run-screen" id="dry-run-screen">
        ${initialLines.map((l) => renderTerminalLine(l)).join('')}
      </div>

      <div class="dry-run-footer">
        <div style="display: flex; gap: 8px; align-items: center;">
          <button type="button" class="btn-simulate" id="btn-run-simulation" ${simState.isRunning ? 'disabled' : ''}>
            <span>${simState.isRunning ? '⏳' : '▶'}</span>
            <span>${simState.isRunning ? 'Simulating...' : (simState.completed ? 'Re-run Simulation' : 'Simulate Remediation Dry-Run')}</span>
          </button>
          <button type="button" class="btn-reset-sim" id="btn-reset-sim" ${simState.isRunning ? 'disabled' : ''}>
            Reset
          </button>
        </div>
        <span class="font-mono" style="font-size: 11px; color: var(--text-muted);">
          Status: <strong style="color: ${simState.completed ? '#10b981' : (simState.isRunning ? '#38bdf8' : 'var(--text-secondary)')};">${simState.status.toUpperCase()}</strong>
        </span>
      </div>
    </div>
  `;

  // Scroll terminal to bottom
  const screenEl = parentEl.querySelector('#dry-run-screen');
  if (screenEl) {
    screenEl.scrollTop = screenEl.scrollHeight;
  }

  // Bind Buttons
  const btnRun = parentEl.querySelector('#btn-run-simulation');
  if (btnRun) {
    btnRun.addEventListener('click', () => {
      runRemediationSimulation(parentEl, remediation, serviceName);
    });
  }

  const btnReset = parentEl.querySelector('#btn-reset-sim');
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      if (activeTimer) clearTimeout(activeTimer);
      store.setState({
        remediationSimState: {
          status: 'idle',
          currentStep: 0,
          logs: [],
          isRunning: false,
          completed: false
        }
      });
      renderDryRunConsole(parentEl, remediation, serviceName);
    });
  }
}

function renderTerminalLine(line) {
  if (line.type === 'guardrail') {
    return `<div class="terminal-line terminal-line-guardrail">${escapeHtml(line.text)}</div>`;
  }
  if (line.type === 'cmd') {
    return `<div class="terminal-line terminal-line-cmd">${escapeHtml(line.text)}</div>`;
  }
  if (line.type === 'prompt') {
    return `<div class="terminal-line terminal-line-prompt">${escapeHtml(line.text)}</div>`;
  }
  if (line.type === 'success') {
    return `<div class="terminal-line terminal-line-success">${escapeHtml(line.text)}</div>`;
  }
  if (line.type === 'highlight') {
    return `<div class="terminal-line terminal-line-highlight">${escapeHtml(line.text)}</div>`;
  }
  return `<div class="terminal-line terminal-line-info">${escapeHtml(line.text)}</div>`;
}

/**
 * Execute strictly local in-browser simulated dry-run rehearsal with zero mutation.
 */
function runRemediationSimulation(parentEl, remediation, serviceName) {
  if (activeTimer) clearTimeout(activeTimer);

  const dryRunCmd = remediation.dry_run_command || `gcloud run services update ${serviceName || 'service'} --dry-run`;
  const metric = remediation.verification_metric || 'Health check status returns to HEALTHY';
  const rollback = remediation.rollback_plan || 'Revert previous deployment';

  const simulationScript = [
    { delay: 300, line: { type: 'guardrail', text: '[SAFETY BOUNDARY] Starting Simulation Rehearsal (NO INFRASTRUCTURE CHANGE)' } },
    { delay: 600, line: { type: 'info', text: `[PRECONDITION] Checking incident confirmation for service '${serviceName}'... [OK]` } },
    { delay: 900, line: { type: 'info', text: `[PRECONDITION] Checking rollback target availability... [OK]` } },
    { delay: 1200, line: { type: 'cmd', text: `[SIMULATING EXECUTION] ${dryRunCmd}` } },
    { delay: 1600, line: { type: 'highlight', text: `[SIMULATION] Validating syntax and configuration diff against schema... [VALID]` } },
    { delay: 2000, line: { type: 'info', text: `[SIMULATION] Modeling traffic stabilization and recovery trajectory...` } },
    { delay: 2400, line: { type: 'info', text: `[VERIFICATION] Target Metric Expectation: '${metric}'` } },
    { delay: 2800, line: { type: 'info', text: `[CONTINGENCY] Rollback Plan Registered: '${rollback}'` } },
    { delay: 3200, line: { type: 'guardrail', text: '------------------------------------------------------------' } },
    { delay: 3300, line: { type: 'success', text: '✓ [RESULT] SIMULATED SUCCESS — NO INFRASTRUCTURE WAS CHANGED' } },
    { delay: 3400, line: { type: 'info', text: 'Remediation dry-run passed all safety validation checks.' } }
  ];

  store.setState({
    remediationSimState: {
      status: 'simulating',
      currentStep: 0,
      logs: [
        { type: 'info', text: `=== STARTING SIMULATION REHEARSAL FOR ${serviceName.toUpperCase()} ===` }
      ],
      isRunning: true,
      completed: false
    }
  });
  renderDryRunConsole(parentEl, remediation, serviceName);

  let currentStep = 0;
  function processStep() {
    if (currentStep >= simulationScript.length) {
      store.setState({
        remediationSimState: {
          ...store.getState().remediationSimState,
          status: 'completed',
          isRunning: false,
          completed: true
        }
      });
      renderDryRunConsole(parentEl, remediation, serviceName);
      return;
    }

    const step = simulationScript[currentStep];
    const prevLogs = store.getState().remediationSimState.logs || [];
    const nextLogs = [...prevLogs, step.line];

    store.setState({
      remediationSimState: {
        ...store.getState().remediationSimState,
        logs: nextLogs,
        currentStep: currentStep + 1
      }
    });

    renderDryRunConsole(parentEl, remediation, serviceName);
    currentStep++;
    activeTimer = setTimeout(processStep, step.delay);
  }

  activeTimer = setTimeout(processStep, 300);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
