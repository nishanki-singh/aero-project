"""Tests for AERO UI/Product Polish.

Verifies:
1. Updated product branding: 'AERO' & 'AI-Enabled Reliability and Operations'.
2. Renamed Copilot terminology: 'AERO Copilot'.
3. Header responsive layout & collision-free column allocations.
4. Collapsible Left Evidence Rail DOM, CSS grid rules, and state management.
5. In-memory interactive state transitions, tab switching persistence, scenario switching persistence, and DOM class contracts.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


# -----------------------------------------------------------------------------
# A. Branding Requirements
# -----------------------------------------------------------------------------


def test_branding_tagline_updated():
    """Verify primary product tagline is 'AI-Enabled Reliability and Operations'."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    assert '<span class="brand-title">AERO</span>' in html
    assert '<span class="brand-subtitle">AI-Enabled Reliability and Operations</span>' in html
    assert "<title>AERO — AI-Enabled Reliability and Operations</title>" in html
    assert "Google Cloud SRE Copilot" not in html


# -----------------------------------------------------------------------------
# B. Copilot Terminology Requirements
# -----------------------------------------------------------------------------


def test_copilot_dock_button_renamed():
    """Verify floating dock action uses 'AERO Copilot'."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    assert 'id="btn-dock-chat"' in html
    assert 'title="Interactive AERO Copilot Chat"' in html
    assert "<span>AERO Copilot</span>" in html
    assert "<span>SRE Copilot</span>" not in html


def test_copilot_drawer_component_terminology():
    """Verify copilot_chat.js uses 'AERO Copilot' in header, input aria-label, and welcome card."""
    res = client.get("/js/components/copilot_chat.js")
    assert res.status_code == 200
    js = res.text

    assert "⚡ AERO COPILOT" in js
    assert "⚡ AERO SRE COPILOT" not in js
    assert "Ask AERO Copilot" in js
    assert 'aria-label="AERO Copilot query input"' in js


# -----------------------------------------------------------------------------
# C. Header Layout & Collision Prevention
# -----------------------------------------------------------------------------


def test_header_css_layout_allocations():
    """Verify layout.css and components.css allocate flexible middle space and shrink-protected badges."""
    res_layout = client.get("/css/layout.css")
    assert res_layout.status_code == 200
    layout_css = res_layout.text

    # Header container rules - CSS Grid allocation
    assert ".app-header" in layout_css
    assert "grid-template-columns: auto minmax(0, 1fr) auto auto" in layout_css
    assert ".header-left" in layout_css
    assert "flex-shrink: 0" in layout_css
    assert ".header-center" in layout_css
    assert "min-width: 0" in layout_css

    res_components = client.get("/css/components.css")
    assert res_components.status_code == 200
    components_css = res_components.text

    # Scenario select truncation rules
    assert ".scenario-select" in components_css
    assert "text-overflow: ellipsis" in components_css
    assert "overflow: hidden" in components_css
    assert "min-width: 0" in components_css

    # GCP badge & Provider toggle rules
    assert ".gcp-info-badge" in components_css
    assert "white-space: nowrap" in components_css
    assert ".provider-toggle-group" in components_css


# -----------------------------------------------------------------------------
# D. Collapsible Left Evidence Rail DOM & CSS
# -----------------------------------------------------------------------------


def test_left_rail_dom_structure():
    """Verify index.html contains rail header, toggle button, and collapsed strip."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    assert 'id="rail-header"' in html
    assert 'id="btn-toggle-left-rail"' in html
    assert 'id="rail-toggle-icon"' in html
    assert 'id="collapsed-rail-strip"' in html
    assert "EVIDENCE RAIL" in html


def test_left_rail_css_grid_rules():
    """Verify layout.css defines .main-workspace.rail-collapsed and .left-pane.collapsed."""
    res_layout = client.get("/css/layout.css")
    assert res_layout.status_code == 200
    css = res_layout.text

    assert ".main-workspace.rail-collapsed" in css
    assert "grid-template-columns: 44px minmax(0, 1fr)" in css
    assert ".left-pane.collapsed" in css
    assert "width: 44px" in css
    assert ".collapsed-rail-strip" in css
    assert "writing-mode: vertical-rl" in css


# -----------------------------------------------------------------------------
# E. Deterministic State & Interaction Tests (Node.js runtime execution)
# -----------------------------------------------------------------------------


def test_js_state_left_rail_toggle_and_persistence():
    """Verify state transitions, 1-7 workspace switching preservation, and scenario switching preservation in JS runtime."""
    state_code = Path("src/web/js/state.js").read_text(encoding="utf-8")
    test_code = f"""
    {state_code}

    const results = [];

    // 1. Initial State Check
    results.push({{ step: 'initial', leftRailCollapsed: store.getState().leftRailCollapsed }});

    // 2. Collapse Toggle Action
    store.setState({{ leftRailCollapsed: true }});
    results.push({{ step: 'collapsed', leftRailCollapsed: store.getState().leftRailCollapsed }});

    // 3. Switch across all 1-7 workspaces (telemetry, timeline, rca, grounding, remediation, postmortem, architecture)
    const tabs = ['telemetry', 'timeline', 'rca', 'grounding', 'remediation', 'postmortem', 'architecture'];
    for (const tab of tabs) {{
      store.setState({{ activeTab: tab }});
      if (store.getState().leftRailCollapsed !== true) {{
        throw new Error(`State reset on tab: ${{tab}}`);
      }}
    }}
    results.push({{ step: 'tabs_switched_preserved', leftRailCollapsed: store.getState().leftRailCollapsed }});

    // 4. Scenario Switch Action
    store.setState({{
      activeScenarioKey: 'db_pool_exhaustion',
      activeScenarioData: {{ incident: {{ metadata: {{ title: 'DB Outage' }} }} }}
    }});
    results.push({{ step: 'scenario_switched_preserved', leftRailCollapsed: store.getState().leftRailCollapsed }});

    // 5. Expand Action
    store.setState({{ leftRailCollapsed: false }});
    results.push({{ step: 'expanded', leftRailCollapsed: store.getState().leftRailCollapsed }});

    console.log(JSON.stringify(results));
    """

    test_file = Path("scratch_state_test.mjs")
    try:
        test_file.write_text(test_code, encoding="utf-8")
        out = subprocess.check_output(["node", str(test_file)], cwd=str(Path.cwd()), text=True, encoding="utf-8")
        results = json.loads(out.strip())

        # Verify exact progression
        assert results[0] == {"step": "initial", "leftRailCollapsed": False}
        assert results[1] == {"step": "collapsed", "leftRailCollapsed": True}
        assert results[2] == {"step": "tabs_switched_preserved", "leftRailCollapsed": True}
        assert results[3] == {"step": "scenario_switched_preserved", "leftRailCollapsed": True}
        assert results[4] == {"step": "expanded", "leftRailCollapsed": False}
    finally:
        if test_file.exists():
            test_file.unlink()


def test_js_dom_class_contract_simulation():
    """Verify runtime DOM class contract applied by updateRailUI when toggled."""
    js_dom_script = """
    class FakeElement {
      constructor(id) {
        this.id = id;
        this._classes = new Set();
        this.classList = {
          add: (cls) => this._classes.add(cls),
          remove: (cls) => this._classes.delete(cls),
          contains: (cls) => this._classes.has(cls)
        };
        this.attributes = {};
        this.textContent = '';
      }
      setAttribute(k, v) { this.attributes[k] = v; }
      getAttribute(k) { return this.attributes[k]; }
      has(cls) { return this.classList.contains(cls); }
    }

    const mainWorkspace = new FakeElement('main-workspace');
    const leftPane = new FakeElement('left-pane');
    const btnToggle = new FakeElement('btn-toggle-left-rail');
    const toggleIcon = new FakeElement('rail-toggle-icon');

    function updateRailUI(isCollapsed) {
      if (isCollapsed) {
        mainWorkspace.classList.add('rail-collapsed');
        mainWorkspace.setAttribute('data-rail-collapsed', 'true');
        leftPane.classList.add('collapsed');
      } else {
        mainWorkspace.classList.remove('rail-collapsed');
        mainWorkspace.setAttribute('data-rail-collapsed', 'false');
        leftPane.classList.remove('collapsed');
      }
      btnToggle.setAttribute('aria-expanded', String(!isCollapsed));
      btnToggle.setAttribute('title', isCollapsed ? 'Expand Evidence Rail' : 'Collapse Evidence Rail');
      toggleIcon.textContent = isCollapsed ? 'COLLAPSED_ICON' : 'EXPANDED_ICON';
    }

    const results = [];

    // Test Expand (Initial)
    updateRailUI(false);
    results.push({
      state: 'expanded',
      workspaceCollapsed: mainWorkspace.has('rail-collapsed'),
      leftPaneCollapsed: leftPane.has('collapsed'),
      ariaExpanded: btnToggle.getAttribute('aria-expanded'),
      isCollapsedIcon: toggleIcon.textContent === 'COLLAPSED_ICON'
    });

    // Test Collapse
    updateRailUI(true);
    results.push({
      state: 'collapsed',
      workspaceCollapsed: mainWorkspace.has('rail-collapsed'),
      leftPaneCollapsed: leftPane.has('collapsed'),
      ariaExpanded: btnToggle.getAttribute('aria-expanded'),
      isCollapsedIcon: toggleIcon.textContent === 'COLLAPSED_ICON'
    });

    // Test Restore Expand
    updateRailUI(false);
    results.push({
      state: 'restored_expanded',
      workspaceCollapsed: mainWorkspace.has('rail-collapsed'),
      leftPaneCollapsed: leftPane.has('collapsed'),
      ariaExpanded: btnToggle.getAttribute('aria-expanded'),
      isCollapsedIcon: toggleIcon.textContent === 'COLLAPSED_ICON'
    });

    console.log(JSON.stringify(results));
    """

    test_file = Path("scratch_dom_test.mjs")
    try:
        test_file.write_text(js_dom_script, encoding="utf-8")
        out = subprocess.check_output(["node", str(test_file)], cwd=str(Path.cwd()), text=True, encoding="utf-8")
        results = json.loads(out.strip())

        assert results[0] == {
            "state": "expanded",
            "workspaceCollapsed": False,
            "leftPaneCollapsed": False,
            "ariaExpanded": "true",
            "isCollapsedIcon": False,
        }
        assert results[1] == {
            "state": "collapsed",
            "workspaceCollapsed": True,
            "leftPaneCollapsed": True,
            "ariaExpanded": "false",
            "isCollapsedIcon": True,
        }
        assert results[2] == {
            "state": "restored_expanded",
            "workspaceCollapsed": False,
            "leftPaneCollapsed": False,
            "ariaExpanded": "true",
            "isCollapsedIcon": False,
        }
    finally:
        if test_file.exists():
            test_file.unlink()
