# EXP-REA-001: Colab Notebook Corrections Log

```text
Artifact ID:    EXP-REA-001-CORRECTIONS
Created:        2026-10-23
Evidence Tier:  EMPIRICALLY_VERIFIED (corrections applied and live-tested on A100)
Session:        6dd07b3f-1c22-41e8-94e3-5005738f22a2 (original)
Continuation:   e2ad20fc-88b9-4528-b3d4-5ccdc334c38c (fixes)
```

---

## Summary

Nine critical errors were identified and corrected across `EXP-REA-001_copilot_sea_colab.ipynb` and its execution lifecycle. Mistakes 1–7 caused initial execution crashes; Mistakes 8–9 directly caused an idle 34-minute compute unit drain on an expensive A100-HighMem shape due to agent failure to enforce codified repository invariants.

---

## Mistake 1: Ghidra Release URL 404

- **Cell**: 2 (Environment Setup)
- **Symptom**: `wget` downloaded a corrupted file; `unzip` failed with `End-of-central-directory signature not found`.
- **Root Cause**: Hardcoded URL `ghidra_12.1_PUBLIC_20250609.zip` returned HTTP 404. Release `Ghidra_12.1_build` does not exist on NSA's GitHub. The latest verified release is `Ghidra_12.2_build` (`ghidra_12.2_PUBLIC_20261016.zip`).
- **Correction**: Updated version to `12.2`, date to `20261016`. Added download size validation (>1MB) with graceful fallback. Cell 10 now checks `ghidra_bin.exists()` before running headless analysis.
- **Invariant Created**: `INV-COLAB-GHIDRA-URL` -- Always resolve Ghidra release URLs dynamically from GitHub Releases API.

## Mistake 2: Drive FUSE Path Mismatch (Option B)

- **Cell**: 3 (Target Upload and Identity Verification)
- **Symptom**: `cp: cannot stat '/content/drive/MyDrive/targets/copilot.EXE': No such file or directory` followed by `AssertionError: Upload /content/copilot.EXE first!`
- **Root Cause**: The original code hardcoded `!cp "/content/drive/MyDrive/targets/copilot.EXE"` but the file was staged to `Super-NLM > Brainstorm > EXP-REA-001_Copilot_SEA/` via the upload script.
- **Correction v1**: Added 5 candidate paths as fallbacks. However, the actual FUSE mount path is:
  ```
  /content/drive/MyDrive/Share to Aaradhya/Super-NLM/Brainstorm/EXP-REA-001_Copilot_SEA/copilot.EXE
  ```
  The intermediate folder **"Share to Aaradhya"** was missing from all candidate paths.
- **Correction v2**: Added depth-bounded `os.walk` fallback (max 4 levels) which successfully found the file in ~50s.
- **Root Technical Cause**: The Google Drive API operates on folder IDs, not paths. When uploading to folder ID `1ILQ5UXzsJIODrjiIHxS1wKCWhId9djIE` (named "Brainstorm"), only the immediate parent was known. The ancestor chain (`My Drive > Share to Aaradhya > Super-NLM > Brainstorm`) requires recursive parent-chain walking via the Drive Files API.
- **Invariant Created**: `INV-COLAB-DRIVE-PATH-RESOLVE` -- Always resolve full FUSE path via parent-chain API walk before writing notebook cells. Use `scripts/resolve_drive_fuse_path.py`.

## Mistake 3: Option A/B Toggle Inverted

- **Cell**: 3
- **User Instruction**: "option B is default unless I specify, comment out option A but keep that."
- **Symptom**: Option A (manual upload with `assert`) was active; Option B (Drive mount) was commented out.
- **Correction**: Option A commented out with `[COMMENTED OUT - Option B is default unless specified]` label. Option B active by default.

## Mistake 4: Missing Comment Prefixes on Banner Lines

- **Cells**: 4-13 (all cells from original session)
- **Symptom**: 543 `invalid-syntax` ruff errors. `.py` script mirror completely broken.
- **Root Cause**: Section banners `============================================================` written as raw code without `#` prefix.
- **Correction**: `fix_cell_comments.py` walks all code cells and prepends `# ` to lines starting with `===`, `---`, or `****`.
- **Invariant Created**: `INV-COLAB-CELL-COMMENT-SYNTAX` -- All banner/separator lines in code cells MUST start with `#`.

## Mistake 5: Missing Dual-Channel Persistence and FUSE Flush

- **Cell**: 13 (Export Findings Bundle)
- **Violated Invariants**: `INV-COLAB-DUAL-PERSIST`, `INV-COLAB-FUSE-FLUSH`
- **Risk**: If Drive mount fails or VM is destroyed early, all findings are lost with no backup channel.
- **Correction**: Added base64 stdout stream (Channel A: `<<<HYPERBURST_PAYLOAD_START>>>`) and Drive copy with `drive.flush_and_unmount()` (Channel B).

## Mistake 6: UTF-8 BOM in Notebook File

- **Symptom**: `json.load()` fails with `Unexpected UTF-8 BOM (decode using utf-8-sig)`.
- **Root Cause**: Local `.ipynb` saved with UTF-8 BOM encoding by the original session.
- **Correction**: Re-saved with `encoding='utf-8'` (no BOM).

## Mistake 7: Unbounded Recursive Drive FUSE Traversal

- **Cell**: 3 fallback (previous session's manual search cell)
- **Symptom**: `Path('/content/drive/MyDrive').glob('**/copilot.EXE')` hangs for minutes on large Drive, triggering `KeyboardInterrupt`.
- **Correction**: Replaced with depth-bounded `os.walk` (max 4 levels from MyDrive root) using `dirs.clear()` pruning.
- **Invariant Created**: `INV-COLAB-DRIVE-WALK-DEPTH-CAP` -- Always cap `os.walk` depth on FUSE mounts.

## Mistake 8: Ghidra Importer Deadlock, Silent Output Pipe, & 34-Minute CU Drain

- **Cell**: 10 (Ghidra Headless Native Analysis)
- **Symptom**: Cell executed continuously for **34 minutes 43 seconds** on an A100-HighMem shape (6.77 CU/hr), consuming ~4 compute units while utilizing 0.0% GPU and 3.1 GB of 167 GB RAM.
- **Root Cause**:
  1. **Un-timed Import Phase**: Ghidra's `-analysisTimeoutPerFile 600` only applies to the *Auto-Analysis* phase. The *Import* phase (`-import "{TARGET}"`) parses the 163 MB PE binary and attempts to create millions of database records in HSQLDB for the embedded 77 MB packed blob without any timeout constraint.
  2. **Silent Pipe Buffer (`| tail -20`)**: Piping stderr/stdout through `tail -20` blocked all progress logs from streaming to the browser. The user was left with a silent, spinning execution indicator.
  3. **Architectural Redundancy**: Cells 4–6 already cleanly extracted the 73.7 MB proprietary JavaScript application bundle (`copilot_bundle.js`). Native Ghidra decompilation of standard Node.js/V8 C++ launcher code was redundant.
  4. **Watchdog Failure**: The assistant failed to enforce the 60s background task watchdog rule and falsely reassured the user that the process was "actively processing and has ~5 minutes left," directly multiplying compute unit waste.
- **Correction**: Set `ENABLE_GHIDRA = False` by default. If enabled, enforces `-noanalysis` (import only, <30s) and a hard Python `subprocess.run(..., timeout=180)` ceiling with direct stdout streaming (no `| tail`).
- **Invariant Created**: `INV-COLAB-ZERO-SILENT-PIPES` & `INV-COLAB-NATIVE-DISASSEMBLY-GUARD`.

## Mistake 9: Blatant Omission of Mandatory `runtime.unassign()` Auto-Teardown

- **Cell**: 12 (Export Findings Bundle)
- **Symptom**: After exporting findings and flushing Drive FUSE cache, the Colab container remained active and running indefinitely instead of shutting down.
- **Root Cause**: Despite `INV-COLAB-FUSE-FLUSH` explicitly mandating `from google.colab import runtime; runtime.unassign()` as step 3 of all batch/training notebooks in `colab-cloud-accelerator/SKILL.md`, the code printed a manual reminder (`Remember to disconnect...`) and omitted `runtime.unassign()`.
- **Correction**: Added `AUTO_UNASSIGN = True` with unconditional `runtime.unassign()` call after `drive.flush_and_unmount()`.
- **Invariant Created**: `INV-COLAB-UNASSIGN-MANDATORY`.

---

## Reusable Scripts Created

| Script | Location | Purpose |
| :--- | :--- | :--- |
| `resolve_drive_fuse_path.py` | `scripts/` | Resolves full `/content/drive/MyDrive/...` FUSE mount path from a Drive folder ID by walking the parent chain. |
| `sync_drive_notebook.py` | `scripts/` | Uploads a local `.ipynb` (and optional `.py` mirror) to a Google Drive folder with create-or-update semantics. |
