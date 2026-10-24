# Incubator RFC: I need to restore the navigation of my portfolio site on index and pro

> **Raw Thought**: *"I need to restore the navigation of my portfolio site on index and project page for the mobile version, the swipe to go to next page function doesn't seem to work after commit 9f674d160a3515915c4239befff95fc04b115fa9."*
> **Captured At**: `2026-10-24T12:02:01.098531+00:00`
> **Vault ID**: `VLT-20261024120156`

---

## 1. Executive Summary & Problem Formulation
Commit `9f674d160a3515915c4239befff95fc04b115fa9` introduced a regression in the mobile viewport touch-event lifecycle, specifically neutralizing the horizontal swipe gesture handlers required for pagination between the root index and project sub-pages. This RFC formulates the diagnostic protocol and UI event-listener isolation strategy required to restore touch-driven navigation fidelity across mobile viewport matrices.

## 2. Target Ecosystem Module & Universe Mapping
- **Primary Repository / Module**: `Portfolio-Core / Mobile-Touch-Engine`
- **Universe Lobe**: `U10 Edge AI & Human-Computer Interface`
- **Architectural Layer**: `Client-Side DOM Event Subsystem & Viewport Router`

## 3. Theoretical Invariant & Mathematical Model
Let $T(t)$ be the set of touch events (`touchstart`, `touchmove`, `touchend`) registered on the viewport document root. Let $\Delta x = x_{\text{end}} - x_{\text{start}}$ represent the net horizontal displacement vector, and $\Delta t = t_{\text{end}} - t_{\text{start}}$ be the elapsed gesture duration. The navigation invariant for state transition $S_i \to S_{i+1}$ requires:
$$\mathcal{I}_{\text{swipe}} := \left( |\Delta x| > \tau_x \right) \land \left( \frac{|\Delta x|}{\Delta t} > v_{\min} \right) \land \left( |\Delta y| < |\Delta x| \cdot \tan(\theta_{\max}) \right)$$
where $\tau_x$ is the minimum pixel threshold, $v_{\min}$ is the minimum velocity, and $\theta_{\max}$ restricts vertical scrolling interference. Commit `9f674d160a3515915c4239befff95fc04b115fa9` violated $\mathcal{I}_{\text{swipe}}$ by either unbinding passive touch listeners or causing event bubbling collision with underlying DOM elements.

## 4. Falsifiable Hypothesis & Empirical Benchmark
- **Hypothesis**: The failure of mobile swipe navigation is caused by either a missing `passive: false` declaration preventing `preventDefault()` execution on `touchmove`, or an unhandled pointer-events CSS blocking rule introduced in commit `9f674d160a3515915c4239befff95fc04b115fa9`.
- **Verification Metric**: 100% successful route transition state mutations across 50 consecutive simulated swipe gestures on mobile device emulation (iOS Safari / Android Chrome).
- **Baseline Comparison**: Current state (0% navigation success via mobile swipe) vs. Target state ($\ge 95\%$ trigger accuracy with $<100\text{ms}$ latency).

## 5. Failure Modes & Boundary Conditions
- **Edge Case 1**: Native browser elastic scrolling/overscroll-behavior capturing horizontal gestures on iOS Safari.
- **Edge Case 2**: Event target collision where interactive UI elements (such as links or buttons within project cards) swallow the touch event before the router listener evaluates $\mathcal{I}_{\text{swipe}}$.

## 6. Immediate Next Step
- [ ] Run `git diff 9f674d160a3515915c4239befff95fc04b115fa9^ 9f674d160a3515915c4239befff95fc04b115fa9` to audit touch-listener bindings and CSS pointer-event updates in the viewport router module.
