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
  }
};
