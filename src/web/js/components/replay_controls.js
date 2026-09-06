/**
 * AERO Stage 4C: Replay Controls Component
 * Provides interactive time-scrubber slider, step navigation, and play/pause simulation loop.
 */

import { store } from '../state.js';
import { formatRelativeTime } from './timeline_event.js';

let playbackIntervalId = null;

/**
 * Stop active playback timer.
 */
export function stopPlayback() {
  if (playbackIntervalId) {
    clearInterval(playbackIntervalId);
    playbackIntervalId = null;
  }
  store.setState({ isPlayingReplay: false });
}

/**
 * Start or resume step-by-step playback.
 * @param {Function} onStepChange Callback when replay step advances
 */
export function startPlayback(onStepChange) {
  stopPlayback();
  const state = store.getState();
  const replay = state.activeReplayData;
  if (!replay || !replay.snapshots || replay.snapshots.length === 0) return;

  store.setState({ isPlayingReplay: true });

  const speed = state.replayPlaybackSpeed || 1000;
  playbackIntervalId = setInterval(() => {
    const currentState = store.getState();
    const currentStep = currentState.currentReplayStep;
    const maxSteps = (currentState.activeReplayData?.snapshots?.length || 1) - 1;

    if (currentStep >= maxSteps) {
      stopPlayback();
      if (onStepChange) onStepChange(maxSteps);
      return;
    }

    const nextStep = currentStep + 1;
    store.setState({ currentReplayStep: nextStep });
    if (onStepChange) onStepChange(nextStep);
  }, speed);
}

/**
 * Render Replay Controls card HTML.
 * @param {object} replayData IncidentReplaySeries object
 * @param {number} currentStep Current step index
 * @param {boolean} isPlaying Whether playback is currently active
 * @returns {string} HTML string
 */
export function renderReplayControls(replayData, currentStep = 0, isPlaying = false) {
  const totalSteps = replayData?.snapshots?.length || 1;
  const clampedStep = Math.min(Math.max(0, currentStep), totalSteps - 1);
  const currentSnapshot = replayData?.snapshots?.[clampedStep] || null;
  const windowStart = replayData?.snapshots?.[0]?.timestamp || null;

  const relTime = currentSnapshot ? formatRelativeTime(currentSnapshot.timestamp, windowStart) : 'T+00m 00s';

  return `
    <div class="replay-controls-card">
      <div class="replay-header-bar">
        <div class="replay-title-group">
          <span style="font-size: 16px;">⏱️</span>
          <span class="pane-title" style="font-size: 14px;">Point-in-Time Replay</span>
        </div>
        <div class="replay-indicator ${isPlaying ? 'playing' : ''}">
          <span class="badge-dot ${isPlaying ? 'pulse' : ''}"></span>
          <span>${isPlaying ? 'PLAYING (1s/step)' : 'PAUSED'}</span>
        </div>
      </div>

      <!-- Range Slider -->
      <div class="replay-slider-wrapper">
        <input 
          type="range" 
          id="replay-time-slider" 
          class="replay-slider" 
          min="0" 
          max="${Math.max(0, totalSteps - 1)}" 
          value="${clampedStep}"
          aria-label="Incident Replay Timeline Scrubber"
        />
        <div class="replay-slider-meta">
          <span>Start (T+00:00)</span>
          <span style="color: var(--accent-cyan); font-weight: 600;">${relTime} — Step ${clampedStep + 1}/${totalSteps}</span>
          <span>End</span>
        </div>
      </div>

      <!-- Scrubber Button Toolbar -->
      <div class="replay-toolbar">
        <div class="replay-button-group">
          <button type="button" class="replay-btn" id="btn-replay-first" title="Jump to start (Step 1)" ${clampedStep === 0 ? 'disabled' : ''}>
            ⏮
          </button>
          <button type="button" class="replay-btn" id="btn-replay-prev" title="Step backward (1 min)" ${clampedStep === 0 ? 'disabled' : ''}>
            ◀
          </button>
          <button type="button" class="replay-btn play-btn" id="btn-replay-play" title="${isPlaying ? 'Pause replay' : 'Play replay sequence'}">
            <span>${isPlaying ? '⏸ Pause' : '▶ Play'}</span>
          </button>
          <button type="button" class="replay-btn" id="btn-replay-next" title="Step forward (1 min)" ${clampedStep >= totalSteps - 1 ? 'disabled' : ''}>
            ▶
          </button>
          <button type="button" class="replay-btn" id="btn-replay-last" title="Jump to end" ${clampedStep >= totalSteps - 1 ? 'disabled' : ''}>
            ⏭
          </button>
        </div>

        <div style="display: flex; align-items: center; gap: 6px;">
          <select id="replay-speed-select" class="speed-select" aria-label="Playback Speed">
            <option value="1000" selected>1.0x (1s)</option>
            <option value="500">2.0x (0.5s)</option>
            <option value="250">4.0x (0.25s)</option>
          </select>
          <button type="button" class="replay-btn" id="btn-replay-reset" title="Reset replay to beginning">
            ↺
          </button>
        </div>
      </div>
    </div>
  `;
}

/**
 * Initialize event listeners for the Replay Scrubber toolbar.
 * @param {Function} onStepChange Callback when step changes
 */
export function initReplayEvents(onStepChange) {
  const slider = document.getElementById('replay-time-slider');
  const btnFirst = document.getElementById('btn-replay-first');
  const btnPrev = document.getElementById('btn-replay-prev');
  const btnPlay = document.getElementById('btn-replay-play');
  const btnNext = document.getElementById('btn-replay-next');
  const btnLast = document.getElementById('btn-replay-last');
  const btnReset = document.getElementById('btn-replay-reset');
  const speedSelect = document.getElementById('replay-speed-select');

  // Slider scrub input
  if (slider) {
    slider.addEventListener('input', (e) => {
      stopPlayback();
      const step = parseInt(e.target.value, 10);
      store.setState({ currentReplayStep: step });
      if (onStepChange) onStepChange(step);
    });
  }

  // First step
  if (btnFirst) {
    btnFirst.addEventListener('click', () => {
      stopPlayback();
      store.setState({ currentReplayStep: 0 });
      if (onStepChange) onStepChange(0);
    });
  }

  // Prev step
  if (btnPrev) {
    btnPrev.addEventListener('click', () => {
      stopPlayback();
      const step = Math.max(0, store.getState().currentReplayStep - 1);
      store.setState({ currentReplayStep: step });
      if (onStepChange) onStepChange(step);
    });
  }

  // Play / Pause toggle
  if (btnPlay) {
    btnPlay.addEventListener('click', () => {
      const isPlaying = store.getState().isPlayingReplay;
      if (isPlaying) {
        stopPlayback();
        if (onStepChange) onStepChange(store.getState().currentReplayStep);
      } else {
        const currentStep = store.getState().currentReplayStep;
        const maxSteps = (store.getState().activeReplayData?.snapshots?.length || 1) - 1;
        // If at end, start from beginning
        if (currentStep >= maxSteps) {
          store.setState({ currentReplayStep: 0 });
        }
        startPlayback(onStepChange);
      }
    });
  }

  // Next step
  if (btnNext) {
    btnNext.addEventListener('click', () => {
      stopPlayback();
      const maxSteps = (store.getState().activeReplayData?.snapshots?.length || 1) - 1;
      const step = Math.min(maxSteps, store.getState().currentReplayStep + 1);
      store.setState({ currentReplayStep: step });
      if (onStepChange) onStepChange(step);
    });
  }

  // Last step
  if (btnLast) {
    btnLast.addEventListener('click', () => {
      stopPlayback();
      const maxSteps = (store.getState().activeReplayData?.snapshots?.length || 1) - 1;
      store.setState({ currentReplayStep: maxSteps });
      if (onStepChange) onStepChange(maxSteps);
    });
  }

  // Reset step
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      stopPlayback();
      store.setState({ currentReplayStep: 0 });
      if (onStepChange) onStepChange(0);
    });
  }

  // Playback speed
  if (speedSelect) {
    speedSelect.addEventListener('change', (e) => {
      const speed = parseInt(e.target.value, 10);
      store.setState({ replayPlaybackSpeed: speed });
      if (store.getState().isPlayingReplay) {
        startPlayback(onStepChange);
      }
    });
  }
}
