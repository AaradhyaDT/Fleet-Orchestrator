# Batch baseline locking script for Aaradhya's repositories
$ErrorActionPreference = "Continue"

$targetRepos = @(
    # --- Flagship Ecosystem Repositories ---
    "Aaradhya-Dev-Tamrakar/brainstorm",
    "AaradhyaDT/Fleet-Orchestrator",
    "Aaradhya-Dev-Tamrakar/super-nlm",
    "Aaradhya-Dev-Tamrakar/SPARK",
    "AaradhyaDT/SPARK",
    "Aaradhya-Dev-Tamrakar/Agent-Customization-Sync",
    "AaradhyaDT/AaradhyaDT.github.io",
    "Aaradhya-Dev-Tamrakar/AaradhyaDT.github.io",
    "Aaradhya-Dev-Tamrakar/omnivault",
    "AaradhyaDT/Nexus",
    "Aaradhya-Dev-Tamrakar/windows-pilot",
    "AaradhyaDT/Problem-Dissector",
    "Aaradhya-Dev-Tamrakar/Claude-Desktop",
    "Aaradhya-Dev-Tamrakar/Competitive-Programming",

    # --- Standalone Security & OS Tools ---
    "Aaradhya-Dev-Tamrakar/Win-Vault",
    "Aaradhya-Dev-Tamrakar/Cyber-Forensics",
    "Aaradhya-Dev-Tamrakar/yt-dlp-live",
    "Aaradhya-Dev-Tamrakar/screen-qa-extension",
    "Aaradhya-Dev-Tamrakar/md2pdf-desktop",
    "Aaradhya-Dev-Tamrakar/system-optimizer",
    "AaradhyaDT/SysOptimizer",
    "Aaradhya-Dev-Tamrakar/localsend-mcp",
    "Aaradhya-Dev-Tamrakar/google-classroom-mcp",
    "AaradhyaDT/typora-mcp",
    "Aaradhya-Dev-Tamrakar/downloader-scripts",
    "Aaradhya-Dev-Tamrakar/nepali-ocr-ai",

    # --- Hardware, Robotics & AI Systems ---
    "AaradhyaDT/Gesture-Controlled-Self-Balancing-Robot",
    "AaradhyaDT/stability-ai-system",
    "AaradhyaDT/gesture-ai-system",
    "AaradhyaDT/crypto_arithmetic_solver",
    "AaradhyaDT/quantum-computation",

    # --- Academic Templates & Competitions ---
    "Aaradhya-Dev-Tamrakar/latex-engineering-report-template",
    "AaradhyaDT/IEEEXtreme19_ShadowXTR",
    "AaradhyaDT/react-workshop-ieeekecktm",

    # --- AEC-MCP CAD / BIM Suite (13 Repos) ---
    "Aaradhya-Dev-Tamrakar/autodesk-mcp",
    "Aaradhya-Dev-Tamrakar/revit-mcp",
    "Aaradhya-Dev-Tamrakar/autocad-mcp",
    "Aaradhya-Dev-Tamrakar/3dsmax-mcp",
    "Aaradhya-Dev-Tamrakar/maya-mcp",
    "Aaradhya-Dev-Tamrakar/fusion360-mcp",
    "Aaradhya-Dev-Tamrakar/rhino-mcp",
    "Aaradhya-Dev-Tamrakar/sketchup-mcp",
    "Aaradhya-Dev-Tamrakar/etabs-mcp",
    "Aaradhya-Dev-Tamrakar/sap2000-mcp",
    "Aaradhya-Dev-Tamrakar/staad-mcp",
    "Aaradhya-Dev-Tamrakar/epanet-mcp",
    "Aaradhya-Dev-Tamrakar/qgis-mcp",

    # --- Fuse AI Fellowship Milestones & Coursework ---
    "AaradhyaDT/fuseAiF_wk1_data_wrangling",
    "AaradhyaDT/fuseAiF_wk2_customer_api_app",
    "AaradhyaDT/fuseAiF_wk3_text2sql",
    "AaradhyaDT/fuseAiF_wk4_linear_models",
    "AaradhyaDT/fuseAiF_wk5_telco_churn_ensembles",
    "AaradhyaDT/fuseAiF_wk6_probabilistic_models",
    "AaradhyaDT/fuseAiF_wk7_customer_segmentation",
    "AaradhyaDT/fuseAiF_wk8_sp500_forecasting",
    "AaradhyaDT/fuseAiF_wk9_neu_defect_cnn",
    "AaradhyaDT/fuseAiF_wk10_image_processing",
    "AaradhyaDT/fuseAiF_wk11_vision_transformers",
    "AaradhyaDT/fuseAiF_wk12_ner_customer_support",
    "AaradhyaDT/fuseAiF_wk13_lstm_text_classification",
    "AaradhyaDT/fuseAiF_wk14_agentic_routing",
    "AaradhyaDT/fuseAiF_wk15_ai_assistant_rag",
    "AaradhyaDT/fuseAiF_wk16_agentic_assistant",
    "AaradhyaDT/fuseAiF_wk17_telco_churn_mlops",
    "AaradhyaDT/fuseAiF_wk17_agentic_mlops",
    "AaradhyaDT/fuseAiF_wk18_trustworthy_ai",
    "AaradhyaDT/ONM-Casestudy-Fusemachines",
    "AaradhyaDT/FuseAIF2026M1",
    "Aaradhya-Dev-Tamrakar/FuseAIF2026"
)

Write-Host "Starting ecosystem baseline release locking ($($targetRepos.Count) repositories)..." -ForegroundColor Cyan

$successCount = 0
$skippedCount = 0
$errorCount = 0

foreach ($repo in $targetRepos) {
    Write-Host "`nProcessing: $repo" -ForegroundColor Yellow
    # Check if v1.0.0 release already exists
    $relCheck = gh release view v1.0.0 -R $repo 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  -> Release v1.0.0 already exists on $repo. Skipping." -ForegroundColor Green
        $skippedCount++
        continue
    }

    $title = "v1.0.0 — Functional Baseline (2026-10-15)"
    $notes = "Verified operational baseline release locking repository functionality and architecture as of October 15, 2026."

    $output = gh release create v1.0.0 -R $repo --title $title --notes $notes 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Released v1.0.0: $output" -ForegroundColor Green
        $successCount++
    } else {
        Write-Host "  ✗ Failed: $output" -ForegroundColor Red
        $errorCount++
    }
}

Write-Host "`n=== Baseline Locking Summary ===" -ForegroundColor Cyan
Write-Host "Successfully Created: $successCount" -ForegroundColor Green
Write-Host "Already Existed / Skipped: $skippedCount" -ForegroundColor Yellow
Write-Host "Errors: $errorCount" -ForegroundColor Red
