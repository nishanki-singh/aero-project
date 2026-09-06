/**
 * AERO Five Whys Causal Explorer Component
 * Renders structured causal chains with explicit evidence grounding vs derived inference distinction.
 */

import { store } from '../state.js';

/**
 * Render the interactive Five Whys causal tree into a parent container.
 * @param {HTMLElement} parentEl 
 * @param {Array<object>} fiveWhysList 
 */
export function renderFiveWhysTree(parentEl, fiveWhysList) {
  if (!parentEl) return;

  const items = Array.isArray(fiveWhysList) && fiveWhysList.length > 0 ? fiveWhysList : [];

  if (items.length === 0) {
    parentEl.innerHTML = `
      <div class="five-whys-section">
        <div class="five-whys-header">
          <div class="five-whys-title-group">
            <span class="five-whys-title">5-Whys Causal Progression</span>
          </div>
          <span class="badge badge-warning">No Causal Chain</span>
        </div>
        <div class="placeholder-card" style="padding: 24px;">
          <p class="placeholder-desc">No structured causal progression available for this scenario.</p>
        </div>
      </div>
    `;
    return;
  }

  const state = store.getState();
  const selectedLevel = state.selectedWhyLevel || 1;

  const stepsHtml = items.map((step, idx) => {
    const level = step.level || (idx + 1);
    const isExpanded = level === selectedLevel || selectedLevel === 'all';
    const isInferred = Boolean(step.is_inferred);
    const evidenceRef = step.evidence_ref;

    const groundingBadge = isInferred
      ? `<span class="why-badge-grounding inferred">Derived Inference</span>`
      : `<span class="why-badge-grounding grounded">Observed Evidence</span>`;

    const evidenceHtml = evidenceRef
      ? `
        <div class="why-evidence-ref-box">
          <div style="font-size: 10px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 2px;">Grounding Evidence Reference:</div>
          <div>${escapeHtml(evidenceRef)}</div>
        </div>
      `
      : `
        <div class="why-evidence-ref-box" style="border-left-color: #a855f7; color: #c084fc;">
          <div style="font-size: 10px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 2px;">Causal Reasoning:</div>
          <div>Derived deductive inference based on telemetry correlation and domain architecture rules.</div>
        </div>
      `;

    return `
      <div class="why-step-node ${level === selectedLevel ? 'active' : ''}" data-level="${level}" id="why-step-${level}">
        <div class="why-step-header">
          <div class="why-level-badge">${level}</div>
          <div class="why-question">
            <span style="color: var(--text-muted); font-size: 11px; text-transform: uppercase; margin-right: 6px;">Why:</span>
            ${escapeHtml(step.why)}
          </div>
          ${groundingBadge}
        </div>
        
        <div class="why-body-details" style="${isExpanded ? 'display: flex;' : 'display: none;'}">
          <div class="why-because-row">
            <span class="why-because-label">Because:</span>
            <div style="color: var(--text-main); font-weight: 500;">${escapeHtml(step.because)}</div>
          </div>
          ${evidenceHtml}
        </div>
      </div>
    `;
  }).join('');

  parentEl.innerHTML = `
    <div class="five-whys-section">
      <div class="five-whys-header">
        <div class="five-whys-title-group">
          <span style="font-size: 18px;">🔍</span>
          <span class="five-whys-title">5-Whys Causal Progression</span>
          <span class="font-mono" style="font-size: 11px; color: var(--text-muted);">(${items.length} Grounded Causal Steps)</span>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          <button type="button" class="btn-reset-sim" id="btn-toggle-all-whys" style="padding: 4px 10px; font-size: 11px;">
            ${selectedLevel === 'all' ? 'Collapse All' : 'Expand All'}
          </button>
        </div>
      </div>

      <div class="five-whys-tree" id="five-whys-tree-container">
        ${stepsHtml}
      </div>
    </div>
  `;

  // Attach interactive step listeners
  const nodeEls = parentEl.querySelectorAll('.why-step-node');
  nodeEls.forEach((node) => {
    node.addEventListener('click', () => {
      const lvl = parseInt(node.dataset.level, 10);
      const cur = store.getState().selectedWhyLevel;
      const nextLevel = cur === lvl ? 0 : lvl;
      store.setState({ selectedWhyLevel: nextLevel });
      renderFiveWhysTree(parentEl, fiveWhysList);
    });
  });

  const btnToggleAll = parentEl.querySelector('#btn-toggle-all-whys');
  if (btnToggleAll) {
    btnToggleAll.addEventListener('click', (e) => {
      e.stopPropagation();
      const cur = store.getState().selectedWhyLevel;
      store.setState({ selectedWhyLevel: cur === 'all' ? 1 : 'all' });
      renderFiveWhysTree(parentEl, fiveWhysList);
    });
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
