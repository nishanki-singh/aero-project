/**
 * AERO Application State Management
 * Pure reactive Store pattern with Pub/Sub subscriptions.
 */

class AppState {
  constructor() {
    this.state = {
      scenarios: [],
      activeScenarioKey: null,
      activeScenarioData: null,
      activeTab: 'telemetry',
      providerMode: 'mock', // 'mock' is the strict default; 'live' requires explicit user action
      activeTimelineData: null,
      activeReplayData: null,
      currentReplayStep: 0,
      isPlayingReplay: false,
      selectedMilestoneIndex: null,
      replayPlaybackSpeed: 1000,
      activeDiagnosisData: null,
      activeEvaluationData: null,
      selectedWhyLevel: 1,
      remediationSimState: {
        status: 'idle',
        currentStep: 0,
        logs: [],
        isRunning: false,
        completed: false
      },
      gcpConfig: {
        project_id: 'project-a47199cc-a109-4cd5-917',
        region: 'us-central1',
        default_model: 'gemini-2.5-flash'
      },
      isLoading: false,
      error: null

    };

    this.listeners = new Set();
  }

  /**
   * Get an immutable snapshot of current state.
   */
  getState() {
    return { ...this.state };
  }

  /**
   * Update state and notify all subscribers.
   * @param {Partial<AppState>} updates 
   */
  setState(updates) {
    const prevState = { ...this.state };
    this.state = { ...this.state, ...updates };
    this.notify(prevState);
  }

  /**
   * Subscribe a listener function to state changes.
   * @param {(state: AppState, prevState: AppState) => void} listener 
   * @returns {() => void} Unsubscribe function
   */
  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /**
   * Notify all listeners of a state transition.
   * @private
   */
  notify(prevState) {
    for (const listener of this.listeners) {
      try {
        listener(this.getState(), prevState);
      } catch (err) {
        console.error('Error in state change listener:', err);
      }
    }
  }
}

export const store = new AppState();
