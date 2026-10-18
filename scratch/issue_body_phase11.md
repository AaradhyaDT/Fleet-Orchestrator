## Overview
Implement the **Azmuth Neuromorphic Command Center & Phylogenetic Gene Evolution GUI** (`tools/azmuth_gui.py`) embodying the ADT Signature GUI Design System (`design-taste-gui`). The system delivers a standalone native desktop application with 60FPS Win32 canvas animations, High-DPI screen resolution adaptation, an interactive zoom ladder, dynamic Light/Dark theme switching, and zero browser RAM bloat.

## Key Capabilities & Architectural Deliverables

### 1. Mission Control Layout & Top Telemetry Bar
- Live Gear Selector (`Whisper` / `Balanced` / `Turbo`) wired to `orchestrator-state/azmuth_gear.json`.
- 60FPS RAM Oscilloscope sparkline with dynamically scaled circuit-breaker ceiling.
- Orbital 30-PAT Token Ring indicator reflecting active, cooldown, and exhausted keys.
- Real-time Thalamic $|Z|$-score threshold tuner slider ($0.5\sigma$ - $2.5\sigma$).

### 2. Interactive Switchable Views
- **View [1] End-to-End Pipeline & PAT Flow**: Full 4-stream sensory schematic $\to$ 30-PAT orbital radar ring $\to$ Thalamic Sieve ($|Z| \ge \theta\sigma$) $\to$ U0-U5 Cortical Brain $\to$ Ultimatrix Gene Sequencer $\to$ Arena & SSOT Ledgers.
- **View [2] U0-U5 Neuromorphic Causal DAG**: Dynamic 6-cartridge mounting (`U0`..`U5`), homeostatic Z-score node coloring, directed axonal synapses with weights & lag days, First-Person View (FPV) gut avoidance inspection, and interactive **Multi-Hop Shock Wave (+2.0σ)** simulation.
- **View [3] Phylogenetic Gene Evolution Tree & Allele Arena**: Genomic taxonomy explorer across 349+ sequenced genes (Tiers 0-5); renders live branching phylogenetic trees (`Wild-Type` $\to$ `Mutator Operator Edge` $\to$ `Daughter Alleles` $\to$ `Ultimatrix Arena PRIMARY Champion`), with net speedup % and live **"⚡ Mutate & Race Selected Gene"** execution trigger.

### 3. Right-Hand Capability & Code Diff Inspector
- Time & Space Big-O complexity bounds.
- Environmental Triggers (`N<=2e5`, `avx2`, `codeforces`).
- Mathematical Invariants & Epistemic Tiers.
- Empirical Fitness (`runtime_ms` & `ram_kb`) dual comparison bars.
- Syntax-styled Code Template / Mutation Diff viewer with unified dark/light syntax palettes.

### 4. High-DPI Adaptation, Interactive Zoom Ladder & Theme Toggling
- **System DPI Awareness**: Detects display DPI via Win32 `GetDpiForWindow` / `tk scaling`, applying dynamic scaling factor `self.scale`.
- **Center-Bounded Canvas Geometry**: Eliminates node scatter on ultra-wide / 4K displays by bounding layout widths (`min(w * 0.90, 1050 * self.scale)`).
- **Interactive Zoom Ladder**:
  - `Ctrl + =` / `Ctrl + +`: Zoom in
  - `Ctrl + -` / `Ctrl + _`: Zoom out
  - `Ctrl + 0`: Reset zoom (100%)
  - `Ctrl + MouseWheel`: Interactive zooming
- **Dynamic Theme Engine (Dark & Light)**:
  - `Ctrl + T` keybinding and top header toggle button.
  - Switches between Dark Mode (`#090b0e`) and Light Mode (`#f8fafc` / `#ffffff`).
  - Synchronizes Windows 11 DWM titlebar frames via `DwmSetWindowAttribute`.

### 5. Zero-Friction Desktop & Tray Integration
- Added `"Open Azmuth Command Center"` to `tools/azmuth_tray.ps1` and `tools/azmuth_tray.py` with double-click launch.
- Created standalone `launch_azmuth_gui.bat` using `pythonw.exe` for silent startup.

## Acceptance Tasks
- [x] Implement native 60FPS Command Center GUI and Phylogenetic Gene Explorer (`tools/azmuth_gui.py`)
- [x] Implement High-DPI resolution scaling and center-bounded canvas geometry
- [x] Implement interactive zoom ladder (`Ctrl+=`, `Ctrl+-`, `Ctrl+0`, `Ctrl+MouseWheel`)
- [x] Implement dynamic Light Mode and Dark Mode toggle engine (`Ctrl+T`)
- [x] Integrate with Azmuth system tray and silent `pythonw.exe` batch launcher
- [x] Create comprehensive unit test suite `tests/test_azmuth_gui.py` covering views, phylogeny, tray, zoom, and theme
- [x] Enforce 100% test pass rate across full regression suite (588/588 passing)

## Verification Proof
- `pytest tests/test_azmuth_gui.py -v`: 5/5 passed (100%).
- Full regression suite: 588 passed in 136s.
- `brainstorm/audit.bat`: 694 files, 67 tests, 12 Z3 SMT invariants certified.
