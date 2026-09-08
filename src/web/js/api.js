/**
 * AERO REST API Client
 * Clean HTTP interface communicating strictly via FastAPI endpoints.
 */

const API_BASE = '';

/**
 * Handle HTTP response and parse JSON.
 * @param {Response} response 
 * @returns {Promise<any>}
 */
async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      // Use fallback status text if body isn't JSON
    }
    throw new Error(errorDetail);
  }
  return response.json();
}

export const api = {
  /**
   * Healthcheck verification.
   */
  async getHealth() {
    const res = await fetch(`${API_BASE}/healthz`);
    return handleResponse(res);
  },

  /**
   * Fetch backend environment & provider config.
   */
  async getConfig() {
    const res = await fetch(`${API_BASE}/api/config`);
    return handleResponse(res);
  },

  /**
   * List all available incident benchmark scenarios.
   */
  async getScenarios() {
    const res = await fetch(`${API_BASE}/api/scenarios`);
    return handleResponse(res);
  },

  /**
   * Fetch telemetry pack and details for a specific scenario.
   * @param {string} scenarioKey 
   */
  async getScenarioByKey(scenarioKey) {
    const res = await fetch(`${API_BASE}/api/scenarios/${encodeURIComponent(scenarioKey)}`);
    return handleResponse(res);
  },

  /**
   * Fetch synthesized chronological timeline for a specific scenario.
   * @param {string} scenarioKey 
   * @param {number} seed 
   */
  async getScenarioTimeline(scenarioKey, seed = 42) {
    const res = await fetch(`${API_BASE}/api/scenarios/${encodeURIComponent(scenarioKey)}/timeline?seed=${seed}`);
    return handleResponse(res);
  },

  /**
   * Fetch ordered step-by-step state replay series for a specific scenario.
   * @param {string} scenarioKey 
   * @param {number} intervalSeconds 
   * @param {number} seed 
   */
  async getScenarioReplay(scenarioKey, intervalSeconds = 60, seed = 42) {
    const res = await fetch(
      `${API_BASE}/api/scenarios/${encodeURIComponent(scenarioKey)}/replay?interval_seconds=${intervalSeconds}&seed=${seed}`
    );
    return handleResponse(res);
  },

  /**
   * Synthesize timeline from arbitrary incident telemetry payload.
   * @param {object} incident 
   * @param {object|null} diagnosticReport 
   */
  async synthesizeTimeline(incident, diagnosticReport = null) {
    const res = await fetch(`${API_BASE}/api/timeline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ incident, diagnostic_report: diagnosticReport })
    });
    return handleResponse(res);
  },

  /**
   * Generate step-by-step state replay snapshots for arbitrary incident telemetry.
   * @param {object} incident 
   * @param {number} intervalSeconds 
   */
  async generateReplay(incident, intervalSeconds = 60) {
    const res = await fetch(`${API_BASE}/api/timeline/replay`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ incident, interval_seconds: intervalSeconds })
    });
    return handleResponse(res);
  },

  /**
   * Fetch structured diagnostic report and evidence grounding for a scenario.
   * @param {string} scenarioKey 
   * @param {string|null} provider 
   * @param {number} seed 
   */
  async getScenarioDiagnosis(scenarioKey, provider = null, seed = 42) {
    const providerParam = provider ? `&provider=${encodeURIComponent(provider)}` : '';
    const res = await fetch(
      `${API_BASE}/api/scenarios/${encodeURIComponent(scenarioKey)}/diagnose?seed=${seed}${providerParam}`
    );
    return handleResponse(res);
  },

  /**
   * Fetch quantitative benchmark evaluation metrics for a scenario.
   * @param {string} scenarioKey 
   * @param {string} provider 
   * @param {number} seed 
   */
  async getScenarioEvaluation(scenarioKey, provider = 'mock', seed = 42) {
    const res = await fetch(
      `${API_BASE}/api/scenarios/${encodeURIComponent(scenarioKey)}/evaluation?provider=${encodeURIComponent(provider)}&seed=${seed}`
    );
    return handleResponse(res);
  },

  /**
   * Run AI diagnosis on an arbitrary incident telemetry payload.
   * @param {object} incident 
   * @param {string|null} provider 
   */
  async runDiagnosis(incident, provider = 'mock') {
    const res = await fetch(`${API_BASE}/api/diagnose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ incident, provider })
    });
    return handleResponse(res);
  },

  /**
   * Fetch publication-ready Google SRE postmortem and Markdown for a scenario.
   * @param {string} scenarioKey
   * @param {string|null} provider
   * @param {number} seed
   */
  async getScenarioPostmortem(scenarioKey, provider = null, seed = 42) {
    const providerParam = provider ? `&provider=${encodeURIComponent(provider)}` : '';
    const res = await fetch(
      `${API_BASE}/api/scenarios/${encodeURIComponent(scenarioKey)}/postmortem?seed=${seed}${providerParam}`
    );
    return handleResponse(res);
  },

  /**
   * Send question to Grounded SRE Copilot.
   * @param {string} scenarioKey
   * @param {string} message
   * @param {string|null} provider
   * @param {number} seed
   */
  async sendChatMessage(scenarioKey, message, provider = null, seed = 42) {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario_key: scenarioKey,
        message,
        provider,
        seed
      })
    });
    return handleResponse(res);
  },

  /**
   * Evaluate proposed deployment/config change for SRE stability risks.
   * @param {object} proposedChange
   * @param {string|null} scenarioKey
   * @param {string} provider
   */
  async analyzeRisk(proposedChange, scenarioKey = null, provider = 'deterministic') {
    const res = await fetch(`${API_BASE}/api/risk/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        proposed_change: proposedChange,
        scenario_key: scenarioKey,
        provider
      })
    });
    return handleResponse(res);
  }
};
