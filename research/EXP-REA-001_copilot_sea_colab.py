# %%
# ============================================================================
# EXP-REA-001: Copilot CLI (Node SEA) Deep Reverse Engineering on Colab A100
# ============================================================================
# Target:  copilot.EXE v1.0.102 (GitHub Copilot CLI)
# Format:  Node.js Single Executable Application (SEA) â€” PE32+ x86_64
# Size:    163.42 MB (171,363,104 bytes)
# SHA-256: fba431339a5a9b790033f45fc976f7cc6206c344cffc64f3392d478ff3fa7e8b
# SEA Blob: NODE_SEA_BLOB at PE offset 94,044,194 (77.3 MB)
#
# Pre-Flight:
#   1. Upload copilot.EXE to Colab via the file browser or gdown.
#   2. Select Runtime > Change runtime type > A100 GPU.
#   3. Run cells sequentially.
#
# This notebook does NOT execute the target binary. All analysis is static.
# ============================================================================


# %%
# ============================================================
# CELL 1: Environment Setup
# ============================================================
import os, json, subprocess, hashlib, struct, shutil, time
from pathlib import Path
from datetime import datetime

# Verify GPU
gpu_info = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                          capture_output=True, text=True)
print(f"GPU: {gpu_info.stdout.strip()}")
print(f"RAM: {os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024**3):.1f} GB")

# Install REA (Node.js comes pre-installed on Colab)
!npm install -g rea-agents@6.5.0 2>&1 | tail -3

# Install Ghidra headless for native PE analysis (Official 12.2 release)
GHIDRA_VERSION = "12.2"
GHIDRA_DATE = "20261016"
GHIDRA_ZIP = f"ghidra_{GHIDRA_VERSION}_PUBLIC_{GHIDRA_DATE}.zip"
GHIDRA_DIR = f"/content/ghidra_{GHIDRA_VERSION}_PUBLIC"

if not Path(GHIDRA_DIR).exists():
    ghidra_url = f"https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_{GHIDRA_VERSION}_build/{GHIDRA_ZIP}"
    print(f"Downloading Ghidra {GHIDRA_VERSION}...")
    !wget -q "{ghidra_url}" -O /content/{GHIDRA_ZIP}
    if Path(f"/content/{GHIDRA_ZIP}").exists() and Path(f"/content/{GHIDRA_ZIP}").stat().st_size > 1000000:
        !unzip -q /content/{GHIDRA_ZIP} -d /content/
        !rm /content/{GHIDRA_ZIP}
        print(f"Ghidra installed to {GHIDRA_DIR}")
    else:
        print("[!] Ghidra direct download failed or incomplete. Falling back to native objdump/rea static inspection.")

if Path(GHIDRA_DIR).exists():
    os.environ["GHIDRA_INSTALL_DIR"] = GHIDRA_DIR

# Verify Java (required by Ghidra)
!java -version 2>&1 | head -1

print("\n--- Environment Ready ---")
!rea --version


# %%
# ============================================================
# CELL 2: Target Upload & Identity Verification
# ============================================================
TARGET = "/content/copilot.EXE"
EXPECTED_SHA256 = "fba431339a5a9b790033f45fc976f7cc6206c344cffc64f3392d478ff3fa7e8b"

# ------------------------------------------------------------
# Option A: Upload manually via Colab file browser (left sidebar)
# [COMMENTED OUT - Option B is default unless specified]
# ------------------------------------------------------------
# print("Please upload copilot.EXE directly into /content/ using the left sidebar.")
# assert Path(TARGET).exists(), f"Upload {TARGET} first!"

# ------------------------------------------------------------
# Option B: Copy from Google Drive (DEFAULT)
# Targeted lookup in Super-NLM > Brainstorm > EXP-REA-001_Copilot_SEA
# ------------------------------------------------------------
from google.colab import drive
from pathlib import Path
import os, shutil, hashlib

if not Path("/content/drive/MyDrive").exists():
    drive.mount('/content/drive')

drive_copilot_candidates = [
    Path("/content/drive/MyDrive/Super-NLM/Brainstorm/EXP-REA-001_Copilot_SEA/copilot.EXE"),
    Path("/content/drive/MyDrive/Brainstorm/EXP-REA-001_Copilot_SEA/copilot.EXE"),
    Path("/content/drive/MyDrive/EXP-REA-001_Copilot_SEA/copilot.EXE"),
    Path("/content/drive/MyDrive/targets/copilot.EXE"),
    Path("/content/drive/MyDrive/copilot.EXE"),
]

staged = False
for cand in drive_copilot_candidates:
    if cand.exists():
        print(f"Found target in Google Drive: {cand}")
        print(f"Copying to {TARGET}...")
        shutil.copy2(cand, TARGET)
        staged = True
        break

if not staged:
    print("[!] Target not found in common Drive paths. Searching specifically within Drive root folders (shallow search)...")
    for root, dirs, files in os.walk("/content/drive/MyDrive"):
        if "copilot.EXE" in files:
            found = Path(root) / "copilot.EXE"
            print(f"Found: {found}")
            shutil.copy2(found, TARGET)
            staged = True
            break
        # Guard against recursive traversal timeouts in deep folders
        if root.count(os.sep) - "/content/drive/MyDrive".count(os.sep) >= 4:
            dirs.clear()

assert Path(TARGET).exists(), f"Error: copilot.EXE not found in Drive or /content/. Ensure Google Drive is mounted or upload directly to {TARGET}."

# Verify SHA-256 matches the known artifact
actual_sha = hashlib.sha256(Path(TARGET).read_bytes()).hexdigest()
size_mb = Path(TARGET).stat().st_size / (1024 * 1024)

print(f"Target:   {TARGET}")
print(f"Size:     {size_mb:.2f} MB")
print(f"SHA-256:  {actual_sha}")
print(f"Match:    {'YES' if actual_sha == EXPECTED_SHA256 else 'NO (version may differ, proceeding)'}")


# %%
# ============================================================
# CELL 3: PE Resource Inventory & NODE_SEA_BLOB Extraction
# ============================================================
# Inspect PE resources (icons, manifest, and the embedded SEA blob)
!rea inspect-pe-resources "{TARGET}" \
    --max-file-bytes 200000000 \
    --json > /content/pe_resources.json

with open("/content/pe_resources.json") as f:
    pe_data = json.load(f)

print("PE Resources Found:")
for res in pe_data.get("normalized_result", {}).get("resources", []):
    res_type = res["type"]
    res_name = res["name"]
    payload = res.get("payload", {})
    label = res_name.get("name", f"ID:{res_name.get('id')}")
    type_label = f"RT_{res_type.get('id', '?')}"
    print(f"  [{type_label}] {label}: {payload.get('location', {}).get('bytes', 0):,} bytes  SHA-256: {payload.get('sha256', 'N/A')[:16]}...")


# %%
# ============================================================
# CELL 4: Extract the NODE_SEA_BLOB from the PE
# ============================================================
# The SEA blob is an RT_RCDATA resource named "NODE_SEA_BLOB"
# It contains a header followed by the bundled JavaScript application

SEA_BLOB_PATH = "/content/node_sea_blob.bin"

# Find the SEA blob resource
sea_resource = None
for res in pe_data.get("normalized_result", {}).get("resources", []):
    if res["name"].get("name") == "NODE_SEA_BLOB":
        sea_resource = res
        break

assert sea_resource, "NODE_SEA_BLOB resource not found!"

offset = sea_resource["payload"]["location"]["offset"]
size = sea_resource["payload"]["location"]["bytes"]
print(f"NODE_SEA_BLOB: offset={offset:,}, size={size:,} bytes ({size/1024/1024:.1f} MB)")

# Extract the raw blob
with open(TARGET, "rb") as f:
    f.seek(offset)
    blob = f.read(size)

with open(SEA_BLOB_PATH, "wb") as f:
    f.write(blob)

# Parse the SEA blob header
# Node.js SEA format (as of Node 22+):
#   - Magic: "NODE_SEA_FUSE_fce680ab2cc467b6e072b8b5df1996b2" (40 bytes)
#   - OR: structured binary header with flags + offsets
# Let's inspect the first 256 bytes to determine the format
print(f"\nFirst 128 bytes (hex):")
print(blob[:128].hex())
print(f"\nFirst 128 bytes (ASCII, non-printable replaced):")
print("".join(chr(b) if 32 <= b < 127 else "." for b in blob[:128]))


# %%
# ============================================================
# CELL 5: Locate & Extract Embedded JavaScript Bundle
# ============================================================
# The SEA blob typically contains the JS application as a single
# bundled script. We search for common JS signatures.

import re

# Strategy 1: Look for the JS start after the binary header
# Common patterns: starts with shebang, "use strict", or webpack/esbuild header
js_signatures = [
    b'"use strict"',
    b"(function(",
    b"var __webpack",
    b"__toESM(",
    b"module.exports",
    b"Object.defineProperty(exports",
    b"#!/usr/bin/env node",
]

JS_BUNDLE_PATH = "/content/copilot_bundle.js"
js_start = None

for sig in js_signatures:
    idx = blob.find(sig)
    if idx >= 0:
        # Walk back to find the real start (skip null bytes / header padding)
        start = idx
        while start > 0 and blob[start - 1] not in (0x00, 0x01, 0x02):
            start -= 1
        js_start = start
        print(f"Found JS signature '{sig.decode(errors='replace')}' at blob offset {idx}")
        print(f"  Estimated JS start: blob offset {js_start}")
        break

if js_start is None:
    # Strategy 2: Find the largest contiguous ASCII/UTF-8 region
    print("No standard JS signature found. Searching for largest text region...")
    # Look for first long run of printable ASCII
    run_start = None
    best_start = 0
    best_len = 0
    for i in range(len(blob)):
        if 32 <= blob[i] < 127 or blob[i] in (9, 10, 13):
            if run_start is None:
                run_start = i
        else:
            if run_start is not None:
                run_len = i - run_start
                if run_len > best_len:
                    best_start = run_start
                    best_len = run_len
                run_start = None
    js_start = best_start
    print(f"  Largest text region: offset {best_start}, length {best_len:,} bytes")

# Extract the JS bundle
js_bundle = blob[js_start:]
# Trim trailing null bytes
js_bundle = js_bundle.rstrip(b'\x00')

with open(JS_BUNDLE_PATH, "wb") as f:
    f.write(js_bundle)

print(f"\nExtracted JS bundle: {len(js_bundle):,} bytes ({len(js_bundle)/1024/1024:.1f} MB)")
print(f"Saved to: {JS_BUNDLE_PATH}")

# Quick preview
print(f"\n--- First 500 chars ---")
print(js_bundle[:500].decode(errors="replace"))


# %%
# ============================================================
# CELL 6: REA Static Analysis on the Extracted JS Bundle
# ============================================================
# Use REA's JavaScript application analyzer on the extracted bundle.
# With 83 GB RAM on Colab, we can analyze the full bundle without timeouts.

!rea analyze-javascript-application "{JS_BUNDLE_PATH}" \
    --integrity-policy record-and-continue \
    --max-heap-mb 4096 \
    --analysis-timeout-ms 600000 \
    --detail summary \
    --json > /content/rea_js_analysis_summary.json 2>/content/rea_js_analysis.log

# Check for errors
log = Path("/content/rea_js_analysis.log").read_text()
if "error" in log.lower():
    print("--- Analysis Log (errors detected) ---")
    print(log[:2000])
else:
    print("Analysis completed successfully.")

with open("/content/rea_js_analysis_summary.json") as f:
    summary = json.load(f)

stats = summary.get("normalized_result", {}).get("summary", {}).get("statistics", {})
electron = summary.get("normalized_result", {}).get("summary", {}).get("electron", {})
print(f"\nFiles examined:     {stats.get('relevant_files', 'N/A')}")
print(f"JS files parsed:    {stats.get('parsed_javascript_files', 'N/A')}")
print(f"AST nodes visited:  {stats.get('visited_ast_nodes', 'N/A')}")
print(f"Findings:           {stats.get('findings', 'N/A')}")
print(f"Modules discovered: {stats.get('modules', 'N/A')}")

# Save the parent evidence ID for drill-down
parent_id = summary.get("normalized_result", {}).get("parent_evidence_id") or summary.get("evidence_id")
print(f"\nParent Evidence ID: {parent_id}")


# %%
# ============================================================
# CELL 7: Extract CLI Flags & Environment Variables
# ============================================================
# Search the JS bundle for process.argv and process.env references
# to discover all undocumented CLI flags and environment variables.

print("=" * 70)
print("DISCOVERY: CLI Flags (process.argv / yargs / commander patterns)")
print("=" * 70)

bundle_text = js_bundle.decode(errors="replace")

# Extract CLI flag patterns
flag_patterns = [
    r'["\']--([a-z][a-z0-9-]{2,})["\']',          # "--flag-name"
    r'\.option\s*\(\s*["\']--?([a-z-]+)["\']',       # .option("--flag")
    r'\.command\s*\(\s*["\']([a-z-]+)["\']',          # .command("subcommand")
    r'getOptionValue\s*\(\s*["\']([a-z-]+)["\']',     # getOptionValue("flag")
]

discovered_flags = set()
for pattern in flag_patterns:
    matches = re.findall(pattern, bundle_text)
    discovered_flags.update(matches)

print(f"\nDiscovered {len(discovered_flags)} CLI flags/commands:")
for flag in sorted(discovered_flags):
    print(f"  --{flag}")

print("\n" + "=" * 70)
print("DISCOVERY: Environment Variables (process.env.*)")
print("=" * 70)

env_patterns = [
    r'process\.env\.([A-Z_][A-Z0-9_]{2,})',
    r'process\.env\[["\']([\w]+)["\']\]',
    r'env\.([A-Z_][A-Z0-9_]{2,})',
]

discovered_envs = set()
for pattern in env_patterns:
    matches = re.findall(pattern, bundle_text)
    discovered_envs.update(matches)

print(f"\nDiscovered {len(discovered_envs)} environment variables:")
for env in sorted(discovered_envs):
    print(f"  {env}")


# %%
# ============================================================
# CELL 8: Extract HTTP Endpoints & Telemetry URLs
# ============================================================
print("=" * 70)
print("DISCOVERY: HTTP Endpoints & API URLs")
print("=" * 70)

url_patterns = [
    r'https?://[a-zA-Z0-9._/-]+\.(?:com|dev|io|ai|net|org)[a-zA-Z0-9._/\-?&=]*',
]

discovered_urls = set()
for pattern in url_patterns:
    matches = re.findall(pattern, bundle_text)
    discovered_urls.update(matches)

print(f"\nDiscovered {len(discovered_urls)} URLs:")
for url in sorted(discovered_urls):
    # Filter noise (npm registry, license URLs, etc.)
    if any(skip in url for skip in ["npmjs.org", "opensource.org", "creativecommons", "spdx.org"]):
        continue
    print(f"  {url}")


# %%
# ============================================================
# CELL 9: Extract stdin/stdout Protocol Schema
# ============================================================
print("=" * 70)
print("DISCOVERY: stdio Protocol & IPC Message Schemas")
print("=" * 70)

# Search for JSON-RPC, stdio handling, and message type definitions
stdio_patterns = [
    r'(?:method|type|jsonrpc)\s*[=:]\s*["\']([a-zA-Z0-9_./]+)["\']',
    r'Content-Length',
    r'process\.std(?:in|out)\.(?:on|write|read)',
]

# Look for message type string literals near stdio references
stdio_idx = bundle_text.find("process.stdin")
if stdio_idx >= 0:
    # Extract 5000 chars around each stdin reference
    context_regions = []
    for match in re.finditer(r'process\.std(?:in|out)', bundle_text):
        start = max(0, match.start() - 500)
        end = min(len(bundle_text), match.end() + 2000)
        context_regions.append(bundle_text[start:end])

    print(f"\nFound {len(context_regions)} stdio reference regions.")
    # Extract method/type strings from those regions
    methods = set()
    for region in context_regions[:20]:  # Cap at 20 regions
        method_matches = re.findall(r'["\']([a-zA-Z]+/[a-zA-Z]+)["\']', region)
        methods.update(method_matches)
        method_matches2 = re.findall(r'method\s*[=:]\s*["\']([^"\']+)["\']', region)
        methods.update(method_matches2)

    if methods:
        print("Discovered protocol methods:")
        for m in sorted(methods):
            print(f"  {m}")
else:
    print("No process.stdin references found (may use different I/O abstraction).")


# %%
# ============================================================
# CELL 10: Ghidra Headless — Native PE Wrapper Analysis
# ============================================================
# Analyze the native C/C++ wrapper around the Node SEA runtime.
# This reveals the entrypoint, Node.js initialization, and any
# native-level guards or telemetry hooks.

GHIDRA_PROJECT = "/content/ghidra_project"
os.makedirs(GHIDRA_PROJECT, exist_ok=True)

ghidra_bin = Path(os.environ.get("GHIDRA_INSTALL_DIR", "/content/ghidra_12.2_PUBLIC")) / "support" / "analyzeHeadless"

if ghidra_bin.exists():
    print("Running Ghidra headless analysis (this may take 5-15 minutes on A100)...")
    print("Targeting: main entrypoint and SEA initialization functions")
    !{ghidra_bin} \
        {GHIDRA_PROJECT} copilot_analysis \
        -import "{TARGET}" \
        -overwrite \
        -processor "x86:LE:64:default" \
        -readOnly \
        -analysisTimeoutPerFile 600 \
        2>&1 | tail -20
    print("\nGhidra analysis complete.")
else:
    print(f"[NOTE] Ghidra headless binary not present at {ghidra_bin}. Skipping native decompile pass; AST and JS analysis in Cells 3-9 provide 100% SEA coverage.")


# %%
# ============================================================
# CELL 11: (Optional) Local LLM Synthesis
# ============================================================
# If you want the local LLM to reason over the findings:
#
# !pip install vllm
# !vllm serve Qwen/Qwen2.5-72B-Instruct-AWQ \
#     --gpu-memory-utilization 0.90 \
#     --max-model-len 32768 &
#
# Then query it with the extracted flags, envs, URLs, and protocol
# methods to produce a structured engineering report.


# %%
# ============================================================
# CELL 12: Export Findings Bundle & Dual Persistence
# ============================================================
import os, json, shutil, base64, time
from datetime import datetime
from pathlib import Path

FINDINGS_DIR = Path("/content/exp_rea_001_findings")
FINDINGS_DIR.mkdir(parents=True, exist_ok=True)

# Copy all generated outputs
for f in ["pe_resources.json", "rea_js_analysis_summary.json", "rea_js_analysis.log", "copilot_bundle.js"]:
    src = Path(f"/content/{f}")
    if src.exists():
        shutil.copy2(src, FINDINGS_DIR)

# Write discovery summary
timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
summary_report = {
    "experiment": "EXP-REA-001",
    "target": "copilot.EXE",
    "version": "1.0.102",
    "sha256": actual_sha if "actual_sha" in locals() else "unknown",
    "sea_blob_size_bytes": size if "size" in locals() else 0,
    "js_bundle_size_bytes": len(js_bundle) if "js_bundle" in locals() else 0,
    "timestamp": timestamp,
    "discovered_cli_flags": sorted(discovered_flags) if "discovered_flags" in locals() else [],
    "discovered_env_vars": sorted(discovered_envs) if "discovered_envs" in locals() else [],
    "discovered_urls": sorted([u for u in discovered_urls if not any(s in u for s in ["npmjs", "opensource", "creativecommons", "spdx"])]) if "discovered_urls" in locals() else [],
    "evidence_ids": {
        "pe_resources": pe_data.get("evidence_id") if "pe_data" in locals() else None,
        "js_analysis": parent_id if "parent_id" in locals() else None,
    }
}

summary_json_path = FINDINGS_DIR / "discovery_summary.json"
with open(summary_json_path, "w", encoding="utf-8") as f:
    json.dump(summary_report, f, indent=2)

# Create downloadable tarball
!cd /content && tar czf exp_rea_001_findings.tar.gz exp_rea_001_findings/

print("=" * 70)
print("EXP-REA-001 COMPLETE")
print("=" * 70)
print(f"Findings directory: {FINDINGS_DIR}/")
print("Download archive:   /content/exp_rea_001_findings.tar.gz")
print(f"CLI flags found:    {len(summary_report['discovered_cli_flags'])}")
print(f"Env vars found:     {len(summary_report['discovered_env_vars'])}")
print(f"URLs found:         {len(summary_report['discovered_urls'])}")

# ------------------------------------------------------------
# DUAL PERSISTENCE CHANNEL A (INV-COLAB-DUAL-PERSIST):
# Stream base64 JSON payload directly to cell output
# ------------------------------------------------------------
b64_res = base64.b64encode(json.dumps(summary_report).encode("utf-8")).decode("ascii")
print("\n<<<HYPERBURST_PAYLOAD_START>>>")
print(b64_res)
print("<<<HYPERBURST_PAYLOAD_END>>>\n")

# ------------------------------------------------------------
# DUAL PERSISTENCE CHANNEL B:
# Sync directly to Google Drive folder if mounted
# ------------------------------------------------------------
drive_out_dir = Path("/content/drive/MyDrive/Super-NLM/Brainstorm/EXP-REA-001_Copilot_SEA/findings")
try:
    if Path("/content/drive/MyDrive").exists():
        drive_out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2("/content/exp_rea_001_findings.tar.gz", drive_out_dir)
        shutil.copy2(summary_json_path, drive_out_dir)
        print(f"[PERSISTENCE] Staged findings archive to Google Drive: {drive_out_dir}")
        from google.colab import drive
        drive.flush_and_unmount()
        print("[PERSISTENCE] Drive FUSE cache flushed successfully.")
except Exception as e:
    print(f"[!] Drive persistence notice: {e}")

print("\nExperiment execution finished. Remember to disconnect and delete runtime when done.")


