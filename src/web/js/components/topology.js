/**
 * AERO Phase 4 Stage 4H: Blast-Radius Topology & Synthetic Chaos Sandbox Component
 * Interactive SVG microservice graph, dynamic graph traversal, and deterministic chaos sandbox.
 */

import { store } from '../state.js';
import { api } from '../api.js';

// Pre-calculated deterministic layout coordinates for canonical 11 nodes (viewBox: 0 0 760 480)
const NODE_COORDINATES = {
  'api-gateway': { x: 380, y: 45, icon: '🌐', label: 'API Gateway' },
  'catalog-service': { x: 100, y: 145, icon: '📦', label: 'Catalog Service' },
  'auth-service': { x: 280, y: 145, icon: '🔑', label: 'Auth Service' },
  'checkout-service': { x: 470, y: 145, icon: '🛒', label: 'Checkout Service' },
  'order-service': { x: 650, y: 145, icon: '📋', label: 'Order Service' },
  'redis-cache': { x: 180, y: 255, icon: '⚡', label: 'Redis Cache' },
  'payment-service': { x: 500, y: 255, icon: '💳', label: 'Payment Service' },
  'worker-service': { x: 670, y: 255, icon: '⚙️', label: 'Worker Service' },
  'postgres-db': { x: 340, y: 360, icon: '🗄️', label: 'PostgreSQL DB' },
  'kafka-queue': { x: 620, y: 360, icon: '📨', label: 'Kafka Queue' },
  'partner-payment-gateway': { x: 440, y: 440, icon: '🏦', label: 'Partner Payment GW' }
};

// 5 Canonical Chaos Presets
const CHAOS_PRESETS = [
  {
    id: 'preset-1',
    type: 'LATENCY_INJECTION',
    target: 'partner-payment-gateway',
    title: 'Payment GW Latency',
    desc: 'Inject +5000ms upstream latency into acquiring bank payment gateway.'
  },
  {
    id: 'preset-2',
    type: 'DB_POOL_EXHAUSTION_SIMULATION',
    target: 'postgres-db',
    title: 'DB Pool Starvation',
    desc: 'Exhaust connection pool (pool_max: 2, queue: 85) on primary PostgreSQL database.'
  },
  {
    id: 'preset-3',
    type: 'OOM_CRASH_SIMULATION',
    target: 'worker-service',
    title: 'Worker OOMKill Crash',
    desc: 'Simulate container exit code 137 OOMKill and Kafka consumer lag.'
  },
  {
    id: 'preset-4',
    type: 'DOWNSTREAM_OUTAGE_SIMULATION',
    target: 'redis-cache',
    title: 'Redis Cache Outage',
    desc: 'Sever Redis connectivity triggering 4.5x DB query fallback surge.'
  },
  {
    id: 'preset-5',
    type: 'CACHE_POISONING_CHAOS',
    target: 'auth-service',
    title: 'Auth Key Poisoning',
    desc: 'Simulate corrupted JWT key cache causing 401 validation cascade.'
  }
];


let activePreset = CHAOS_PRESETS[0];

/**
 * Resets local chaos presets and completely clears simulated topology state.
 */
export function resetTopologyState() {
  activePreset = CHAOS_PRESETS[0];
  store.setState({
    activeTopologyData: null,
    selectedTopologyNode: null,
    activeBlastRadiusData: null,
    activeChaosSimulation: null,
    isChaosSimulated: false,
    topologyLoading: false,
    topologyError: null,
  });
}

/**
 * Renders the complete Stage 4H Topology & Chaos Sandbox Workspace.
 * @param {HTMLElement} container 
 */
export function renderTopologyWorkspace(container) {
  const state = store.getState();
  const topo = state.activeTopologyData;
  const isSim = state.isChaosSimulated;
  const selectedNodeId = state.selectedTopologyNode || (topo ? topo.active_incident_service : 'postgres-db');
  const blast = state.activeBlastRadiusData;
  const simResult = state.activeChaosSimulation;

  if (state.topologyLoading && !topo) {
    container.innerHTML = `
      <div class="pane-card" style="padding: 40px; text-align: center;">
        <div class="loading-spinner" style="margin: 0 auto 16px auto;"></div>
        <div style="font-size: 14px; color: var(--text-bright);">Computing Canonical Dependency Topology...</div>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Dynamic graph traversal and incident state mapping</div>
      </div>
    `;
    return;
  }

  if (!topo) {
    container.innerHTML = `
      <div class="pane-card" style="padding: 32px; text-align: center;">
        <div style="font-size: 24px; margin-bottom: 8px;">⚠️</div>
        <div style="font-size: 14px; color: var(--text-bright);">Topology Graph Unavailable</div>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">${state.topologyError || 'Please select an incident scenario'}</div>
      </div>
    `;
    return;
  }

  // Build impacted sets for visualization
  const impactedTarget = blast ? blast.target_service : null;
  const directUpstreams = blast ? blast.direct_upstream : [];
  const transUpstreams = blast ? blast.transitive_upstream : [];
  const allImpacted = blast ? [blast.target_service, ...directUpstreams, ...transUpstreams] : [];

  // Selected node model
  const selectedNode = topo.nodes.find(n => n.id === selectedNodeId) || topo.nodes[0];

  container.innerHTML = `
    <div class="topology-workspace" id="topology-workspace">
      
      <!-- Top State Separation Banner -->
      <div class="state-mode-banner ${isSim ? 'simulated' : 'observed'}">
        <div class="mode-badge-group">
          <span class="mode-tag ${isSim ? 'simulated' : 'observed'}">
            ${isSim ? '🔬 [SIMULATED CHAOS STATE]' : '📡 [OBSERVED INCIDENT STATE]'}
          </span>
          <span class="mode-desc">
            ${isSim 
              ? 'Hypothetical deterministic sandbox output · Non-destructive · Zero infrastructure mutation' 
              : 'Derived from active benchmark incident telemetry & health signals'
            }
          </span>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          <span class="badge badge-info" style="font-size: 10px;">Architectural Model (Synthetic)</span>
          ${isSim ? `
            <button type="button" class="btn-chaos-reset" id="btn-banner-reset">
              ↺ Reset to Baseline
            </button>
          ` : ''}
        </div>
      </div>

      <!-- Main Workspace Grid (SVG Graph + Blast Inspector) -->
      <div class="topology-grid">
        
        <!-- Left: SVG Canvas Graph -->
        <div class="graph-canvas-card">
          <div class="pane-header" style="border-bottom: 1px solid var(--border-subtle);">
            <div class="pane-title-group">
              <span class="pane-title">Architectural Topology Graph</span>
              <span class="font-mono" style="font-size: 11px; color: var(--text-muted);">
                ${topo.nodes.length} Nodes · ${topo.edges.length} Edges
              </span>
            </div>
            <div style="display: flex; gap: 6px; align-items: center;">
              <span class="font-mono" style="font-size: 11px; color: var(--text-muted);">Interactive simulated health transitions</span>
            </div>
          </div>

          <!-- SVG Visualizer Container -->
          <div class="graph-svg-container" id="graph-svg-container">
            ${renderSvgGraph(topo, selectedNodeId, blast, isSim)}
          </div>

          <!-- Legend Overlay -->
          <div class="graph-legend-overlay">
            <span style="font-weight: 600;">Legend:</span>
            <div class="legend-item"><span class="legend-dot healthy"></span> Healthy</div>
            <div class="legend-item"><span class="legend-dot degraded"></span> Degraded</div>
            <div class="legend-item"><span class="legend-dot failed"></span> Failed</div>
            <div class="legend-item"><span class="legend-dot chaos"></span> Chaos Injected</div>
            <span style="margin-left: auto; font-family: var(--font-mono); font-size: 10px;">Click any node to evaluate blast radius</span>
          </div>
        </div>

        <!-- Right: Blast Radius & Node Inspector -->
        <div class="blast-inspector-card">
          
          <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
              <div class="font-mono" style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">
                ${selectedNode.tier.replace('_', ' ')}
              </div>
              <div style="font-size: 15px; font-weight: 700; color: var(--text-bright);">
                ${selectedNode.name}
              </div>
              <div class="font-mono" style="font-size: 11px; color: var(--text-muted);">
                ${selectedNode.id}
              </div>
            </div>
            <span class="badge ${getNodeStatusBadgeClass(selectedNode.status)}">
              ${selectedNode.status}
            </span>
          </div>

          <!-- Dynamic Blast Gauge Card -->
          ${blast ? `
            <div class="blast-gauge-container">
              <div class="font-mono" style="font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;">
                Dynamic Blast Radius
              </div>
              <div class="blast-percentage ${getBlastPillClass(blast.impact_level)}">
                ${blast.blast_radius_pct.toFixed(1)}%
              </div>
              <div class="blast-impact-pill ${getBlastPillClass(blast.impact_level)}">
                ${blast.impact_level} IMPACT (${blast.total_impacted_services}/${blast.total_nodes_in_system} Services)
              </div>
              <div style="margin-top: 8px; font-size: 11px; color: var(--text-muted);">
                Critical Path Impact: <strong style="color: ${getCriticalPathColor(blast.critical_path_impact)};">${blast.critical_path_impact}</strong>
              </div>
            </div>

            <!-- Upstream Impact Breakdown -->
            <div>
              <div class="font-mono" style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">
                Direct Callers (1-Hop):
              </div>
              <div class="upstream-list">
                ${blast.direct_upstream.length > 0 
                  ? blast.direct_upstream.map(u => `<span class="service-chip direct">${u}</span>`).join('') 
                  : '<span style="font-size: 11px; color: var(--text-muted);">None (Ingress edge or isolated)</span>'
                }
              </div>
            </div>

            <div>
              <div class="font-mono" style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">
                Transitive Upstream (Cascaded):
              </div>
              <div class="upstream-list">
                ${blast.transitive_upstream.length > 0 
                  ? blast.transitive_upstream.map(u => `<span class="service-chip transitive">${u}</span>`).join('') 
                  : '<span style="font-size: 11px; color: var(--text-muted);">None</span>'
                }
              </div>
            </div>

            <!-- Cascade Paths -->
            <div>
              <div class="font-mono" style="font-size: 11px; color: var(--text-muted); margin-bottom: 6px;">
                Upstream Propagation Paths (${blast.cascade_paths.length}):
              </div>
              <div style="max-height: 120px; overflow-y: auto;">
                ${blast.cascade_paths.slice(0, 4).map(p => `
                  <div class="cascade-path-box">
                    ${p.join(' <span class="cascade-path-arrow">←</span> ')}
                  </div>
                `).join('')}
              </div>
            </div>
          ` : `
            <div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 12px;">
              Click a node on the graph to compute dynamic blast radius.
            </div>
          `}

          <!-- Node Metrics Table -->
          <div style="border-top: 1px solid var(--border-subtle); padding-top: 10px;">
            <div class="font-mono" style="font-size: 10px; color: var(--text-muted); margin-bottom: 6px; text-transform: uppercase;">
              Active Operational Signals
            </div>
            <div style="display: flex; flex-direction: column; gap: 4px; font-family: var(--font-mono); font-size: 11px;">
              ${Object.entries(selectedNode.metrics || {}).map(([k, v]) => `
                <div style="display: flex; justify-content: space-between; padding: 2px 0;">
                  <span style="color: var(--text-muted);">${k}:</span>
                  <span style="color: var(--text-bright); font-weight: 600;">${v}</span>
                </div>
              `).join('')}
            </div>
          </div>

        </div>

      </div>

      <!-- Synthetic Chaos Control Bar -->
      <div class="chaos-card" id="chaos-controls-section">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 16px;">🔬</span>
            <span style="font-size: 14px; font-weight: 700; color: var(--text-bright);">
              Synthetic Chaos Sandbox
            </span>
            <span class="badge badge-warning" style="font-size: 10px;">Deterministic Simulation</span>
          </div>
          <span class="font-mono" style="font-size: 11px; color: var(--text-muted);">
            Pure Sandbox · Offline Only · No Production Mutation
          </span>
        </div>

        <!-- Chaos Experiment Preset Grid -->
        <div class="chaos-preset-grid">
          ${CHAOS_PRESETS.map(p => `
            <button type="button" class="chaos-preset-btn ${activePreset.id === p.id ? 'active' : ''}" data-preset-id="${p.id}">
              <div class="chaos-preset-title">${p.title}</div>
              <div class="chaos-preset-target">Target: ${p.target}</div>
              <div class="chaos-preset-desc">${p.desc}</div>
            </button>
          `).join('')}
        </div>

        <!-- Action Row -->
        <div class="chaos-action-row">
          <div style="display: flex; gap: 10px; align-items: center;">
            <button type="button" class="btn-chaos-run" id="btn-run-chaos">
              <span>⚡</span>
              <span>Inject Simulated Fault: ${activePreset.title}</span>
            </button>
            <button type="button" class="btn-chaos-reset" id="btn-reset-chaos">
              ↺ Reset to Observed Baseline
            </button>
          </div>
          <div class="font-mono" style="font-size: 11px; color: var(--text-muted);">
            ${isSim ? `Active Experiment: ${simResult ? simResult.experiment_id : 'Running'}` : 'Baseline Ready'}
          </div>
        </div>

        <!-- Simulation Narrative & Resilience Findings -->
        ${isSim && simResult ? `
          <div class="sim-narrative-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="font-size: 13px; font-weight: 700; color: #fbbf24;">
                Simulated Failure Propagation Narrative
              </span>
              <span class="font-mono" style="font-size: 10px; color: var(--text-muted);">
                ${simResult.experiment_id}
              </span>
            </div>

            <div style="display: flex; flex-direction: column; gap: 6px; margin-top: 6px;">
              ${simResult.propagation_steps.map((step, idx) => `
                <div class="sim-step-item">
                  <span class="sim-step-bullet">[Hop ${idx + 1}]</span>
                  <span>${step}</span>
                </div>
              `).join('')}
            </div>

            ${simResult.resilience_findings.length > 0 ? `
              <div class="resilience-takeaway-box">
                <div class="resilience-title">🛡️ Architectural Resilience Takeaways:</div>
                <ul style="margin: 0; padding-left: 18px; font-size: 11px; color: var(--text-normal); line-height: 1.4;">
                  ${simResult.resilience_findings.map(f => `<li>${f}</li>`).join('')}
                </ul>
              </div>
            ` : ''}
          </div>
        ` : ''}

      </div>

    </div>
  `;

  attachTopologyListeners(container);
}

/**
 * Generates interactive SVG markup representing the 11 nodes and 18 directed edges.
 */
function renderSvgGraph(topo, selectedNodeId, blast, isSim) {
  const width = 760;
  const height = 480;

  // Build edge SVG elements
  const edgeSvgElements = topo.edges.map(edge => {
    const src = NODE_COORDINATES[edge.source];
    const tgt = NODE_COORDINATES[edge.target];
    if (!src || !tgt) return '';

    const isCascadeActive = blast && blast.cascade_paths.some(path => {
      for (let i = 0; i < path.length - 1; i++) {
        // Paths are target -> upstream, so edge is path[i+1] -> path[i]
        if (path[i+1] === edge.source && path[i] === edge.target) return true;
      }
      return false;
    });

    let edgeClass = 'svg-edge';
    if (isCascadeActive) edgeClass += ' cascade-active';
    else if (edge.status === 'DEGRADED') edgeClass += ' status-degraded';
    else if (edge.status === 'SEVERED') edgeClass += ' status-severed';
    else if (edge.status === 'SATURATED') edgeClass += ' status-saturated';

    // Calculate curve or straight line
    const dx = tgt.x - src.x;
    const dy = tgt.y - src.y;
    const midX = (src.x + tgt.x) / 2;
    const midY = (src.y + tgt.y) / 2;

    return `
      <g class="svg-edge-group" data-edge="${edge.source}->${edge.target}">
        <line 
          x1="${src.x}" y1="${src.y}" 
          x2="${tgt.x}" y2="${tgt.y}" 
          class="${edgeClass}" 
          marker-end="url(#arrow)"
        />
      </g>
    `;
  }).join('');

  // Build node SVG elements
  const nodeSvgElements = topo.nodes.map(node => {
    const coords = NODE_COORDINATES[node.id] || { x: 380, y: 240, icon: '📦', label: node.name };
    const isSelected = node.id === selectedNodeId;
    const isTarget = blast && blast.target_service === node.id;
    const isDirectUp = blast && blast.direct_upstream.includes(node.id);
    const isTransUp = blast && blast.transitive_upstream.includes(node.id);

    let nodeGroupClass = 'svg-node-group';
    if (isSelected) nodeGroupClass += ' selected';
    if (isTarget) nodeGroupClass += ' impacted-target';
    else if (isDirectUp || isTransUp) nodeGroupClass += ' impacted-upstream';

    const rectClass = getNodeRectClass(node.status);
    const cardWidth = 110;
    const cardHeight = 44;
    const rectX = coords.x - cardWidth / 2;
    const rectY = coords.y - cardHeight / 2;

    return `
      <g class="${nodeGroupClass}" data-node-id="${node.id}" transform="translate(0, 0)">
        <rect 
          x="${rectX}" y="${rectY}" 
          width="${cardWidth}" height="${cardHeight}" 
          rx="8" ry="8" 
          class="${rectClass}"
        />
        <text x="${rectX + 10}" y="${rectY + 20}" font-size="14">${coords.icon}</text>
        <text 
          x="${rectX + 28}" y="${rectY + 18}" 
          font-family="system-ui, -apple-system, sans-serif" 
          font-size="10.5" 
          font-weight="600" 
          fill="#f8fafc"
        >
          ${truncateName(node.name, 12)}
        </text>
        <text 
          x="${rectX + 28}" y="${rectY + 32}" 
          font-family="monospace" 
          font-size="8.5" 
          fill="#94a3b8"
        >
          ${node.status}
        </text>
        <circle 
          cx="${rectX + cardWidth - 10}" cy="${rectY + 12}" 
          r="4" 
          fill="${getNodeStatusDotColor(node.status)}"
        />
      </g>
    `;
  }).join('');

  return `
    <svg class="graph-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="18" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(148, 163, 184, 0.4)" />
        </marker>
        <marker id="arrow-red" viewBox="0 0 10 10" refX="18" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
        </marker>
      </defs>
      
      <!-- Edges Layer -->
      <g class="edges-layer">
        ${edgeSvgElements}
      </g>

      <!-- Nodes Layer -->
      <g class="nodes-layer">
        ${nodeSvgElements}
      </g>
    </svg>
  `;
}

/**
 * Attach click handlers for nodes, presets, and chaos actions.
 */
function attachTopologyListeners(container) {
  // Node selection handler
  const nodeGroups = container.querySelectorAll('.svg-node-group');
  nodeGroups.forEach(g => {
    g.addEventListener('click', async () => {
      const nodeId = g.dataset.nodeId;
      if (!nodeId) return;

      const state = store.getState();
      const capturedToken = state.scenarioToken;
      const capturedScenario = state.activeScenarioKey;
      try {
        const blast = await api.getBlastRadius(nodeId, capturedScenario);
        if (store.getState().scenarioToken !== capturedToken || store.getState().activeScenarioKey !== capturedScenario) {
          return;
        }
        store.setState({
          selectedTopologyNode: nodeId,
          activeBlastRadiusData: blast
        });
        renderTopologyWorkspace(container);
      } catch (err) {
        console.error('Failed to compute blast radius:', err);
      }
    });
  });

  // Chaos Preset Selection
  const presetBtns = container.querySelectorAll('.chaos-preset-btn');
  presetBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const presetId = btn.dataset.presetId;
      const found = CHAOS_PRESETS.find(p => p.id === presetId);
      if (found) {
        activePreset = found;
        presetBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const runBtn = container.querySelector('#btn-run-chaos');
        if (runBtn) {
          runBtn.innerHTML = `<span>⚡</span><span>Inject Simulated Fault: ${found.title}</span>`;
        }
      }
    });
  });

  // Run Chaos Simulation
  const runBtn = container.querySelector('#btn-run-chaos');
  if (runBtn) {
    runBtn.addEventListener('click', async () => {
      const state = store.getState();
      const capturedToken = state.scenarioToken;
      const capturedScenario = state.activeScenarioKey;
      runBtn.disabled = true;
      runBtn.innerHTML = `<span>⏳</span><span>Simulating Fault Propagation...</span>`;

      try {
        const simResult = await api.simulateChaos(
          activePreset.target,
          activePreset.type,
          activePreset.type === 'LATENCY_INJECTION' ? 5000 : null,
          capturedScenario
        );

        // Guard: discard if user switched scenario during simulation
        if (store.getState().scenarioToken !== capturedToken || store.getState().activeScenarioKey !== capturedScenario) {
          return;
        }

        // Fetch baseline topology to apply simulated overlays to
        const simTopo = await api.getTopology(capturedScenario);

        // Guard again after async getTopology
        if (store.getState().scenarioToken !== capturedToken || store.getState().activeScenarioKey !== capturedScenario) {
          return;
        }

        // Apply simulated node states
        if (simResult.propagated_node_states) {
          simTopo.nodes.forEach(n => {
            if (simResult.propagated_node_states[n.id]) {
              n.status = simResult.propagated_node_states[n.id];
              n.is_observed_incident_state = false;
            }
          });
        }
        if (simResult.propagated_edge_states) {
          simTopo.edges.forEach(e => {
            const k = `${e.source}->${e.target}`;
            if (simResult.propagated_edge_states[k]) {
              e.status = simResult.propagated_edge_states[k];
            }
          });
        }

        store.setState({
          activeTopologyData: simTopo,
          activeChaosSimulation: simResult,
          selectedTopologyNode: activePreset.target,
          activeBlastRadiusData: simResult.blast_radius,
          isChaosSimulated: true
        });

        renderTopologyWorkspace(container);
      } catch (err) {
        if (store.getState().scenarioToken === capturedToken) {
          console.error('Chaos simulation failed:', err);
          alert(`Chaos simulation failed: ${err.message}`);
          runBtn.disabled = false;
          runBtn.innerHTML = `<span>⚡</span><span>Inject Simulated Fault: ${activePreset.title}</span>`;
        }
      }
    });
  }

  // Reset to Baseline
  const resetBtns = container.querySelectorAll('#btn-reset-chaos, #btn-banner-reset');
  resetBtns.forEach(btn => {
    btn.addEventListener('click', async () => {
      const state = store.getState();
      const capturedToken = state.scenarioToken;
      const capturedScenario = state.activeScenarioKey;
      try {
        const baselineTopo = await api.resetChaos(capturedScenario);
        if (store.getState().scenarioToken !== capturedToken || store.getState().activeScenarioKey !== capturedScenario) {
          return;
        }
        const defaultNode = (baselineTopo && baselineTopo.active_incident_service) || (baselineTopo && baselineTopo.nodes && baselineTopo.nodes[0] && baselineTopo.nodes[0].id) || 'postgres-db';
        const blast = await api.getBlastRadius(defaultNode, capturedScenario);
        if (store.getState().scenarioToken !== capturedToken || store.getState().activeScenarioKey !== capturedScenario) {
          return;
        }
        store.setState({
          activeTopologyData: baselineTopo,
          selectedTopologyNode: defaultNode,
          activeBlastRadiusData: blast,
          isChaosSimulated: false,
          activeChaosSimulation: null
        });
        renderTopologyWorkspace(container);
      } catch (err) {
        console.error('Failed to reset chaos:', err);
      }
    });
  });
}

// Helpers
function truncateName(name, max) {
  if (name.length <= max) return name;
  return name.substring(0, max - 1) + '…';
}

function getNodeRectClass(status) {
  switch (status) {
    case 'HEALTHY': return 'node-rect-healthy';
    case 'DEGRADED': return 'node-rect-degraded';
    case 'UNHEALTHY': return 'node-rect-unhealthy';
    case 'FAILED': return 'node-rect-failed';
    case 'SIMULATED_CHAOS': return 'node-rect-simulated-chaos';
    default: return 'node-rect-healthy';
  }
}

function getNodeStatusBadgeClass(status) {
  switch (status) {
    case 'HEALTHY': return 'badge-healthy';
    case 'DEGRADED': return 'badge-warning';
    case 'UNHEALTHY':
    case 'FAILED': return 'badge-critical';
    case 'SIMULATED_CHAOS': return 'badge-warning';
    default: return 'badge-info';
  }
}

function getNodeStatusDotColor(status) {
  switch (status) {
    case 'HEALTHY': return '#10b981';
    case 'DEGRADED': return '#f59e0b';
    case 'UNHEALTHY':
    case 'FAILED': return '#ef4444';
    case 'SIMULATED_CHAOS': return '#a855f7';
    default: return '#38bdf8';
  }
}

function getBlastPillClass(impactLevel) {
  switch (impactLevel) {
    case 'CATASTROPHIC': return 'catastrophic';
    case 'HIGH': return 'high';
    case 'MODERATE': return 'moderate';
    case 'ISOLATED': return 'isolated';
    default: return 'isolated';
  }
}

function getCriticalPathColor(impact) {
  switch (impact) {
    case 'CRITICAL': return '#ef4444';
    case 'HIGH': return '#f59e0b';
    case 'MODERATE': return '#eab308';
    case 'LOW': return '#38bdf8';
    case 'NONE': return '#10b981';
    default: return '#94a3b8';
  }
}
