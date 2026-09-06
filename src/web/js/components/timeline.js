/**
 * AERO Stage 4C: Incident Timeline & Point-in-Time Replay Coordinator
 * Main workspace orchestrator correlating chronological evidence milestones and state machine replay.
 */

import { store } from '../state.js';
import { renderMilestoneItem } from './timeline_event.js';
import { renderSnapshotPanel } from './snapshot_panel.js';
import { renderReplayControls, initReplayEvents, stopPlayback } from './replay_controls.js';

/**
 * Render the complete Stage 4C Incident Timeline & Replay Workspace.
 * @param {HTMLElement} container Container element to inject the workspace into
 */
export function renderTimelineWorkspace(container) {
  if (!container) return;

  const state = store.getState();
  const timeline = state.activeTimelineData;
  const replay = state.activeReplayData;

  if (state.isLoading || !timeline || !replay) {
    container.innerHTML = `
      <div class="placeholder-card" style="padding: 40px 20px;">
        <div class="spinner"></div>
        <div class="placeholder-title" style="margin-top: 12px;">Synthesizing Chronological Incident Timeline...</div>
        <p class="placeholder-desc">Correlating multi-signal logs, metrics, alerts, and deployment markers.</p>
      </div>
    `;
    return;
  }

  const milestones = Array.isArray(timeline.milestones) ? timeline.milestones : [];
  const currentStep = state.currentReplayStep || 0;
  const totalSteps = replay.snapshots?.length || 1;
  const clampedStep = Math.min(Math.max(0, currentStep), totalSteps - 1);
  const currentSnapshot = replay.snapshots?.[clampedStep] || null;
  const selectedIndex = state.selectedMilestoneIndex;

  // 1. Render Lifecycle Stats Summary Bar
  const statsBarHtml = `
    <div class="timeline-summary-bar">
      <div class="timeline-stat-card">
        <span class="stat-label"><span>⏱️</span> Telemetry Window</span>
        <span class="stat-val accent-cyan">${timeline.total_duration_minutes ?? '--'} <span style="font-size: 13px; font-weight: 400; color: var(--text-muted);">min</span></span>
        <span class="font-mono" style="font-size: 10px; color: var(--text-muted);">Observation Window</span>
      </div>
      <div class="timeline-stat-card">
        <span class="stat-label"><span>🔍</span> Time to Detect (TTD)</span>
        <span class="stat-val accent-amber">${timeline.time_to_detect_minutes !== null ? timeline.time_to_detect_minutes : '--'} <span style="font-size: 13px; font-weight: 400; color: var(--text-muted);">min</span></span>
        <span class="font-mono" style="font-size: 10px; color: var(--text-muted);">From change onset to alert</span>
      </div>
      <div class="timeline-stat-card">
        <span class="stat-label"><span>🛠️</span> Time to Mitigate (TTM)</span>
        <span class="stat-val accent-purple">${timeline.time_to_mitigate_minutes !== null ? timeline.time_to_mitigate_minutes : '--'} <span style="font-size: 13px; font-weight: 400; color: var(--text-muted);">min</span></span>
        <span class="font-mono" style="font-size: 10px; color: var(--text-muted);">From change onset to fix</span>
      </div>
      <div class="timeline-stat-card">
        <span class="stat-label"><span>🚩</span> Correlated Milestones</span>
        <span class="stat-val accent-emerald">${milestones.length} <span style="font-size: 13px; font-weight: 400; color: var(--text-muted);">events</span></span>
        <span class="font-mono" style="font-size: 10px; color: var(--text-muted);">Canonical sequence</span>
      </div>
    </div>
  `;

  // 2. Render Left Track: Milestones List
  let milestonesTrackHtml = '';
  if (milestones.length === 0) {
    milestonesTrackHtml = `
      <div class="empty-timeline-state">
        <div style="font-size: 24px; margin-bottom: 8px;">⏳</div>
        <div style="font-weight: 600; color: var(--text-primary);">No Timeline Milestones Found</div>
        <p style="font-size: 12px; margin-top: 4px;">Zero anomalous operational events detected in this scenario.</p>
      </div>
    `;
  } else {
    milestonesTrackHtml = milestones.map((m, idx) => 
      renderMilestoneItem(m, idx, timeline.time_window_start, selectedIndex === idx)
    ).join('');
  }

  // 3. Render Right Column: Replay Controls + Snapshot Panel
  const replayControlsHtml = renderReplayControls(replay, clampedStep, state.isPlayingReplay);
  const snapshotHtml = renderSnapshotPanel(currentSnapshot, timeline.time_window_start, clampedStep, totalSteps);

  container.innerHTML = `
    <div class="timeline-workspace">
      
      <!-- Incident Lifecycle Stats Bar -->
      ${statsBarHtml}

      <!-- Main Two-Column Layout -->
      <div class="timeline-main-grid">
        
        <!-- Left Pane: Chronological Incident Milestone Track -->
        <div class="timeline-track-pane">
          <div class="section-title-bar">
            <div class="section-heading">
              <span>⏱️</span>
              <span>Incident Progression Track</span>
            </div>
            <span class="section-subtitle">Chronological ground-truth event sequence</span>
          </div>

          <div class="timeline-track-container" id="milestones-track-list">
            ${milestonesTrackHtml}
          </div>
        </div>

        <!-- Right Pane: Sticky Replay Scrubber & Operational Snapshot -->
        <div class="replay-sticky-pane">
          
          <div id="replay-controls-slot">
            ${replayControlsHtml}
          </div>

          <div id="snapshot-panel-slot">
            ${snapshotHtml}
          </div>

        </div>

      </div>

    </div>
  `;

  // Helper to re-render replay and snapshot components dynamically during scrubbing/playback
  const updateReplayAndSnapshotView = (step) => {
    const currentState = store.getState();
    const currentReplay = currentState.activeReplayData;
    if (!currentReplay || !currentReplay.snapshots) return;

    const snapClampedStep = Math.min(Math.max(0, step), currentReplay.snapshots.length - 1);
    const snap = currentReplay.snapshots[snapClampedStep];

    const replaySlot = document.getElementById('replay-controls-slot');
    const snapshotSlot = document.getElementById('snapshot-panel-slot');

    if (replaySlot) {
      replaySlot.innerHTML = renderReplayControls(currentReplay, snapClampedStep, currentState.isPlayingReplay);
      initReplayEvents(updateReplayAndSnapshotView);
    }

    if (snapshotSlot) {
      snapshotSlot.innerHTML = renderSnapshotPanel(
        snap,
        timeline.time_window_start,
        snapClampedStep,
        currentReplay.snapshots.length
      );
    }
  };

  // Initialize Replay Controls Event Handlers
  initReplayEvents(updateReplayAndSnapshotView);

  // Initialize Milestone Selection & "Jump Replay" Click Handlers
  const trackContainer = document.getElementById('milestones-track-list');
  if (trackContainer) {
    trackContainer.addEventListener('click', (e) => {
      // Check if user clicked "Jump Replay Here"
      const jumpBtn = e.target.closest('.btn-jump-replay');
      if (jumpBtn) {
        e.stopPropagation();
        stopPlayback();
        const targetTs = jumpBtn.dataset.timestamp;
        if (targetTs && replay && replay.snapshots) {
          const targetTime = new Date(targetTs).getTime();
          // Find the snapshot closest to target timestamp
          let closestStep = 0;
          let minDiff = Infinity;
          replay.snapshots.forEach((s, idx) => {
            const sTime = new Date(s.timestamp).getTime();
            const diff = Math.abs(sTime - targetTime);
            if (diff < minDiff) {
              minDiff = diff;
              closestStep = idx;
            }
          });
          store.setState({ currentReplayStep: closestStep });
          updateReplayAndSnapshotView(closestStep);
        }
        return;
      }

      // Check if user clicked a milestone card
      const card = e.target.closest('.milestone-card');
      if (card) {
        const index = parseInt(card.dataset.index, 10);
        const currentSelected = store.getState().selectedMilestoneIndex;
        const newSelected = currentSelected === index ? null : index;
        store.setState({ selectedMilestoneIndex: newSelected });

        // Update card selected classes
        trackContainer.querySelectorAll('.milestone-card').forEach((c) => {
          c.classList.remove('selected');
        });
        if (newSelected !== null) {
          card.classList.add('selected');
        }
      }
    });
  }
}
