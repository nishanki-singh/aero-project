/**
 * AERO Header Component
 * Manages scenario dropdown, GCP cloud environment badge, and Provider mode selector.
 */

import { store } from '../state.js';

export function initHeader(onScenarioChange) {
  const scenarioSelect = document.getElementById('scenario-select');
  const projectIdEl = document.getElementById('gcp-project-id');
  const regionEl = document.getElementById('gcp-region');
  const btnMock = document.getElementById('btn-provider-mock');
  const btnLive = document.getElementById('btn-provider-live');

  // Populate scenarios dropdown
  function updateScenarioList(scenarios, activeKey) {
    if (!scenarioSelect) return;
    scenarioSelect.innerHTML = '';

    if (!scenarios || scenarios.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = 'No scenarios available';
      scenarioSelect.appendChild(opt);
      return;
    }

    scenarios.forEach((sc) => {
      const key = sc.scenario_id || sc.scenario_key;
      const title = sc.scenario_name || sc.title || key;
      const service = sc.affected_service || sc.service_name || 'Cloud Service';
      const category = sc.category || 'INCIDENT';
      
      const opt = document.createElement('option');
      opt.value = key;
      opt.textContent = `[${category}] ${title} (${service})`;
      if (key === activeKey) {
        opt.selected = true;
      }
      scenarioSelect.appendChild(opt);
    });
  }

  // Update GCP Project & Region Badges
  function updateGcpInfo(gcpConfig) {
    if (projectIdEl && gcpConfig.project_id) {
      projectIdEl.textContent = gcpConfig.project_id;
    }
    if (regionEl && gcpConfig.region) {
      regionEl.textContent = gcpConfig.region;
    }
  }

  // Update Provider Toggle UI
  function updateProviderToggle(mode) {
    if (!btnMock || !btnLive) return;
    if (mode === 'live') {
      btnMock.classList.remove('active');
      btnLive.classList.add('active');
    } else {
      btnMock.classList.add('active');
      btnLive.classList.remove('active');
    }
  }

  // Event Listeners
  if (scenarioSelect) {
    scenarioSelect.addEventListener('change', (e) => {
      const selectedKey = e.target.value;
      if (selectedKey && typeof onScenarioChange === 'function') {
        onScenarioChange(selectedKey);
      }
    });
  }

  if (btnMock) {
    btnMock.addEventListener('click', () => {
      const prev = store.getState().providerMode;
      store.setState({ providerMode: 'mock' });
      updateProviderToggle('mock');
      if (prev !== 'mock') {
        const activeKey = store.getState().activeScenarioKey;
        if (activeKey && typeof onScenarioChange === 'function') {
          onScenarioChange(activeKey);
        }
      }
    });
  }

  if (btnLive) {
    btnLive.addEventListener('click', () => {
      const prev = store.getState().providerMode;
      store.setState({ providerMode: 'live' });
      updateProviderToggle('live');
      if (prev !== 'live') {
        const activeKey = store.getState().activeScenarioKey;
        if (activeKey && typeof onScenarioChange === 'function') {
          onScenarioChange(activeKey);
        }
      }
    });
  }

  // Subscribe to store updates
  store.subscribe((state, prevState) => {
    if (state.scenarios !== prevState.scenarios || state.activeScenarioKey !== prevState.activeScenarioKey) {
      updateScenarioList(state.scenarios, state.activeScenarioKey);
    }
    if (state.gcpConfig !== prevState.gcpConfig) {
      updateGcpInfo(state.gcpConfig);
    }
    if (state.providerMode !== prevState.providerMode) {
      updateProviderToggle(state.providerMode);
    }
  });

  // Initial render
  const initial = store.getState();
  updateScenarioList(initial.scenarios, initial.activeScenarioKey);
  updateGcpInfo(initial.gcpConfig);
  updateProviderToggle(initial.providerMode);
}
